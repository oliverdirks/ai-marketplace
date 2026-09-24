#!/usr/bin/env python3
"""Generiert die Marketplace-Dateien und den Katalog aus plugins/ und registry/.

  python3 scripts/build_marketplace.py           # neu generieren (offline)
  python3 scripts/build_marketplace.py --check   # CI: validieren und prüfen, ob die generierten Dateien aktuell sind
  python3 scripts/build_marketplace.py --online  # zusätzlich Plugin-Repos per Topic finden, bei track = "releases"
                                                 # auf neue Releases heben und Metadaten externer Plugins über die
                                                 # GitHub-API lesen (Token: GH_TOKEN)
  python3 scripts/build_marketplace.py --plugin ../mein-plugin  # ein einzelnes Plugin-Verzeichnis validieren

Erzeugte Dateien:
  .claude-plugin/marketplace.json  Claude Code (Copilot liest sie nur, wenn die nächste Datei fehlt)
  .github/plugin/marketplace.json  GitHub Copilot (CLI, VS Code, Copilot-App, Cloud Agent)
  catalog/catalog.json             maschinenlesbarer Gesamtkatalog (Portale, scripts/sync_skills.py)
  catalog/CATALOG.md               menschenlesbare Übersicht

Nur Python-Standardbibliothek (>= 3.11), damit das Skript überall ohne Installation läuft.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
REGISTRY_KEYS = {"name", "repo", "path", "ref", "sha", "track", "description", "version", "category", "team", "keywords", "homepage"}
# Manifest-Orte in der Reihenfolge, in der Clients sie finden (Claude Code, Agent Plugins 1.0, Copilot-Legacy).
MANIFEST_PATHS = [".claude-plugin/plugin.json", "plugin.json", ".github/plugin/plugin.json"]

OUT_CLAUDE = ".claude-plugin/marketplace.json"
OUT_COPILOT = ".github/plugin/marketplace.json"
OUT_CATALOG_JSON = "catalog/catalog.json"
OUT_CATALOG_MD = "catalog/CATALOG.md"


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


# --------------------------------------------------------------------------- Parsing und Validierung


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Liest die Top-Level-Felder eines YAML-Frontmatters (ausreichend für SKILL.md, ohne PyYAML)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    block, fields, i = lines[1:end], {}, 0
    while i < len(block):
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", block[i])
        i += 1
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value[:1] in ("|", ">"):
            parts = []
            while i < len(block) and (block[i][:1] in (" ", "\t") or not block[i].strip()):
                parts.append(block[i].strip())
                i += 1
            value = (" " if value.startswith(">") else "\n").join(p for p in parts if p)
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


def validate_skill(frontmatter: dict[str, str] | None, dirname: str, where: str, report: Report, strict: bool) -> None:
    """Regeln der Agent-Skills-Spezifikation, die alle Clients (inkl. OpenCode) durchsetzen."""
    problem = report.error if strict else report.warn
    if frontmatter is None:
        problem(f"{where}: SKILL.md hat kein YAML-Frontmatter")
        return
    name, description = frontmatter.get("name", ""), frontmatter.get("description", "")
    if not name:
        problem(f"{where}: Frontmatter-Feld 'name' fehlt")
    elif name != dirname:
        problem(f"{where}: name '{name}' muss dem Ordnernamen '{dirname}' entsprechen")
    elif not NAME_RE.match(name) or len(name) > 64:
        problem(f"{where}: name '{name}' muss kebab-case sein (max. 64 Zeichen)")
    if not description:
        problem(f"{where}: Frontmatter-Feld 'description' fehlt")
    elif len(description) > 1024:
        problem(f"{where}: description ist länger als 1024 Zeichen")


def detect_components(names: set[str]) -> list[str]:
    found = []
    if "skills" in names:
        found.append("skills")
    if "agents" in names:
        found.append("agents")
    if "commands" in names:
        found.append("commands")
    if "hooks" in names or "hooks.json" in names:
        found.append("hooks")
    if ".mcp.json" in names or "mcp.json" in names:
        found.append("mcp")
    if "com.github.copilot" in names:
        found.append("copilot-extensions")
    return found


def load_registry(root: Path, report: Report) -> list[dict]:
    entries, seen = [], set()
    for file in sorted((root / "registry").glob("*.toml")):
        where = file.relative_to(root).as_posix()
        try:
            entry = tomllib.loads(file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            report.error(f"{where}: ungültiges TOML ({exc})")
            continue
        entry["_file"] = where
        name = entry.get("name", "")
        if not NAME_RE.match(name) or len(name) > 64:
            report.error(f"{where}: name '{name}' muss kebab-case sein (max. 64 Zeichen)")
            continue
        if name in seen:
            report.error(f"{where}: Plugin-Name '{name}' ist mehrfach registriert")
            continue
        seen.add(name)
        for key in sorted(set(entry) - REGISTRY_KEYS - {"_file"}):
            report.warn(f"{where}: unbekanntes Feld '{key}' wird ignoriert")
        if "repo" in entry:
            if not REPO_RE.match(entry["repo"]):
                report.error(f"{where}: repo muss im Format 'org/repo' angegeben werden")
            path = entry.get("path", "")
            if path.startswith("/") or ".." in path.split("/"):
                report.error(f"{where}: path muss relativ zum Repo-Root sein")
            if "sha" in entry and not SHA_RE.match(entry["sha"]):
                report.error(f"{where}: sha muss ein vollständiger 40-stelliger Commit-SHA sein")
            if "ref" not in entry and "sha" not in entry:
                report.warn(f"{where}: weder ref noch sha gesetzt – Clients installieren den Default-Branch")
            if entry.get("track", "releases") != "releases":
                report.error(f"{where}: track kennt nur den Wert \"releases\"")
            if "track" in entry and "sha" in entry:
                report.error(f"{where}: track und sha schließen sich aus – ref verwenden")
        elif not (root / "plugins" / name).is_dir():
            report.error(f"{where}: kein 'repo' angegeben und plugins/{name}/ existiert nicht")
        elif "track" in entry:
            report.error(f"{where}: track gilt nur für externe Plugins mit repo")
        entries.append(entry)

    registered = {e["name"] for e in entries if "repo" not in e}
    for plugin_dir in sorted(p for p in (root / "plugins").glob("*") if p.is_dir()):
        if plugin_dir.name not in registered:
            report.error(f"plugins/{plugin_dir.name}: nicht registriert – registry/{plugin_dir.name}.toml anlegen")
    return entries


def read_local_plugin(plugin_dir: Path, where: str, report: Report, name: str | None = None) -> dict:
    manifest: dict = {}
    manifest_file = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest_file.is_file():
        report.error(f"{where}: .claude-plugin/plugin.json fehlt")
    else:
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(f"{where}/.claude-plugin/plugin.json: ungültiges JSON ({exc})")
        if manifest and name and manifest.get("name") != name:
            report.error(f"{where}: name im plugin.json muss '{name}' lauten")
        elif manifest and not NAME_RE.match(str(manifest.get("name", ""))):
            report.error(f"{where}: name im plugin.json muss kebab-case sein")

    # Optionales zweites Manifest nach Agent Plugins 1.0 (Copilot, Cursor, Codex …) muss synchron bleiben.
    portable_file = plugin_dir / "plugin.json"
    if portable_file.is_file():
        try:
            portable = json.loads(portable_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(f"{where}/plugin.json: ungültiges JSON ({exc})")
            portable = {}
        if portable and portable.get("$schema") != AGENT_PLUGINS_SCHEMA:
            report.error(f"{where}/plugin.json: $schema muss '{AGENT_PLUGINS_SCHEMA}' sein")
        for key in ("name", "version", "description"):
            if portable and manifest and portable.get(key) != manifest.get(key):
                report.error(f"{where}: '{key}' in plugin.json und .claude-plugin/plugin.json weicht ab")
        if (plugin_dir / ".mcp.json").is_file() and not (plugin_dir / "mcp.json").is_file():
            report.warn(f"{where}: .mcp.json ohne mcp.json – Agent-Plugins-Clients laden die MCP-Server nicht")

    skills = []
    for skill_file in sorted(plugin_dir.glob("skills/*/SKILL.md")):
        frontmatter = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        skill_where = f"{where}/skills/{skill_file.parent.name}/SKILL.md"
        validate_skill(frontmatter, skill_file.parent.name, skill_where, report, strict=True)
        frontmatter = frontmatter or {}
        skills.append({"name": frontmatter.get("name", skill_file.parent.name), "description": frontmatter.get("description", "")})
    names = {p.name for p in plugin_dir.iterdir()} if plugin_dir.is_dir() else set()
    return {"manifest": manifest, "skills": skills, "components": detect_components(names)}


# --------------------------------------------------------------------------- GitHub-API (nur --online)


def api_base(host: str) -> str:
    if os.environ.get("MARKETPLACE_API_URL"):  # z. B. für Tests oder einen API-Proxy
        return os.environ["MARKETPLACE_API_URL"].rstrip("/")
    if host == "github.com":
        return "https://api.github.com"
    if host.endswith(".ghe.com"):
        return f"https://api.{host}"  # GitHub Enterprise Cloud mit Data Residency
    return f"https://{host}/api/v3"  # GitHub Enterprise Server


def token_for(org: str) -> str | None:
    """GH_TOKEN__<ORG> erlaubt je Organisation eigene GitHub-App-Tokens, sonst GH_TOKEN/GITHUB_TOKEN."""
    specific = "GH_TOKEN__" + re.sub(r"[^A-Z0-9]", "_", org.upper())
    return os.environ.get(specific) or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


class ApiError(Exception):
    pass


class GitHub:
    def __init__(self, host: str) -> None:
        self.base = api_base(host)

    def get(self, path: str, org: str):
        request = urllib.request.Request(self.base + path, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-marketplace-builder",
        })
        token = token_for(org)
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            hint = " – Token fehlt oder hat keinen Zugriff (GH_TOKEN / GH_TOKEN__<ORG>)" if exc.code in (401, 403) else ""
            raise ApiError(f"GitHub-API {exc.code} für {self.base}{path}{hint}") from exc

    def contents(self, repo: str, path: str, ref: str | None):
        url = f"/repos/{repo}/contents" + (f"/{urllib.parse.quote(path)}" if path else "")
        if ref:
            url += f"?ref={urllib.parse.quote(ref, safe='')}"
        return self.get(url, repo.split("/")[0])

    def file(self, repo: str, path: str, ref: str | None) -> str | None:
        data = self.contents(repo, path, ref)
        if not isinstance(data, dict) or data.get("encoding") != "base64":
            return None
        return base64.b64decode(data["content"]).decode("utf-8")

    def listing(self, repo: str, path: str, ref: str | None) -> list[dict]:
        data = self.contents(repo, path, ref)
        return data if isinstance(data, list) else []


def join(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts if p and p.strip("/"))


def fetch_manifest(gh: GitHub, repo: str, path: str, ref: str | None) -> dict | None:
    for candidate in MANIFEST_PATHS:
        text = gh.file(repo, join(path, candidate), ref)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None
    return None


def fetch_external(gh: GitHub, entry: dict, report: Report) -> dict | None:
    repo, path, where = entry["repo"], entry.get("path", ""), entry["_file"]
    ref = entry.get("sha") or entry.get("ref")
    try:
        manifest = fetch_manifest(gh, repo, path, ref)
        if manifest is None:
            report.warn(f"{where}: kein plugin.json in {repo}/{path or ''}@{ref or 'default'} gefunden")
            return None
        if manifest.get("name") != entry["name"]:
            report.warn(f"{where}: Plugin heißt im Repo '{manifest.get('name')}', registriert als '{entry['name']}'")
        names = {item["name"] for item in gh.listing(repo, path, ref)}
        skills = []
        for item in gh.listing(repo, join(path, "skills"), ref):
            if item.get("type") != "dir":
                continue
            text = gh.file(repo, join(path, "skills", item["name"], "SKILL.md"), ref)
            if text is None:
                continue
            frontmatter = parse_frontmatter(text)
            validate_skill(frontmatter, item["name"], f"{repo}/{join(path, 'skills', item['name'])}", report, strict=False)
            frontmatter = frontmatter or {}
            skills.append({"name": frontmatter.get("name", item["name"]), "description": frontmatter.get("description", "")})
    except (ApiError, urllib.error.URLError, TimeoutError) as exc:
        report.warn(f"{where}: {repo} nicht lesbar ({exc}) – verwende Daten aus dem letzten Lauf")
        return None
    return {
        "description": manifest.get("description", ""),
        "version": manifest.get("version"),
        "ref": ref,
        "skills": skills,
        "components": detect_components(names),
    }


def toml_value(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)  # JSON-Strings sind gültige TOML-Basic-Strings


def discover(root: Path, gh: GitHub, cfg: dict, entries: list[dict], report: Report) -> None:
    """Findet Repos mit dem Discovery-Topic und legt dafür Registry-Einträge zur Prüfung per PR an."""
    discovery = cfg.get("discovery", {})
    topic = discovery.get("topic")
    if not topic:
        return
    known_repos = {e["repo"].lower() for e in entries if "repo" in e}
    known_names = {e["name"] for e in entries}
    for org in discovery.get("orgs", []):
        page = 1
        while True:
            query = urllib.parse.quote(f"org:{org} topic:{topic} archived:false")
            result = gh.get(f"/search/repositories?q={query}&per_page=100&page={page}", org) or {}
            items = result.get("items", [])
            for repo in items:
                full_name = repo["full_name"]
                if full_name.lower() in known_repos:
                    continue
                release = gh.get(f"/repos/{full_name}/releases/latest", org)
                ref = release["tag_name"] if release else repo["default_branch"]
                manifest = fetch_manifest(gh, full_name, "", ref)
                if not manifest or not NAME_RE.match(manifest.get("name", "")):
                    report.warn(f"{full_name}: Topic '{topic}' gesetzt, aber kein gültiges plugin.json im Repo-Root")
                    continue
                name = manifest["name"]
                if name in known_names or (root / "registry" / f"{name}.toml").exists():
                    report.warn(f"{full_name}: Plugin-Name '{name}' ist bereits vergeben – bitte manuell registrieren")
                    continue
                lines = [
                    "# Automatisch per Discovery gefunden – bitte prüfen (Kategorie, Team, Ref) und per PR freigeben.",
                    f"name = {toml_value(name)}",
                    f"repo = {toml_value(full_name)}",
                    f"ref = {toml_value(ref)}",
                    f"description = {toml_value(manifest.get('description') or repo.get('description') or '')}",
                    f"team = {toml_value(org)}",
                ]
                if release:
                    lines.append('track = "releases"  # neue Releases werden per Bot-PR übernommen')
                (root / "registry" / f"{name}.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
                entry = tomllib.loads("\n".join(lines))
                entry["_file"] = f"registry/{name}.toml"
                entries.append(entry)
                known_repos.add(full_name.lower())
                known_names.add(name)
                print(f"Neu gefunden: {full_name} -> registry/{name}.toml")
            if len(items) < 100:
                break
            page += 1


def bump_refs(root: Path, gh: GitHub, entries: list[dict], report: Report) -> None:
    """Hebt ref bei track = "releases" auf das neueste Release; freigegeben wird über den Bot-PR."""
    for entry in entries:
        if entry.get("track") != "releases" or "repo" not in entry:
            continue
        try:
            release = gh.get(f"/repos/{entry['repo']}/releases/latest", entry["repo"].split("/")[0])
        except ApiError as exc:
            report.warn(f"{entry['_file']}: neuestes Release nicht lesbar ({exc})")
            continue
        if not release or release["tag_name"] == entry.get("ref"):
            continue
        file = root / entry["_file"]
        line = f"ref = {toml_value(release['tag_name'])}"
        text, count = re.subn(r"(?m)^ref\s*=.*$", line, file.read_text(encoding="utf-8"), count=1)
        file.write_text(text if count else text.rstrip("\n") + f"\n{line}\n", encoding="utf-8")
        print(f"{entry['name']}: ref {entry.get('ref', '-')} -> {release['tag_name']}")
        entry["ref"] = release["tag_name"]


# --------------------------------------------------------------------------- Generierung


def build_records(root: Path, cfg: dict, entries: list[dict], report: Report, gh: GitHub | None) -> list[dict]:
    host = cfg["github"]["host"]
    cache = {}
    cache_file = root / OUT_CATALOG_JSON
    if cache_file.is_file():
        cache = {p["name"]: p.get("upstream") for p in json.loads(cache_file.read_text(encoding="utf-8"))["plugins"]}

    records = []
    for entry in sorted(entries, key=lambda e: e["name"]):
        name = entry["name"]
        record, manifest = {"name": name}, {}
        if "repo" not in entry:
            info = read_local_plugin(root / "plugins" / name, f"plugins/{name}", report, name)
            manifest = info["manifest"]
            record.update({
                "kind": "local",
                "description": entry.get("description") or manifest.get("description", ""),
                "version": entry.get("version") or manifest.get("version"),
                "path": f"plugins/{name}",
                "repository": f"https://{host}/{cfg['github']['repository']}",
                "skills": info["skills"],
                "components": info["components"],
            })
        else:
            upstream = (fetch_external(gh, entry, report) if gh else None) or cache.get(name) or {}
            pinned = entry.get("sha") or entry.get("ref")
            if upstream and upstream.get("ref") != pinned:
                report.warn(f"{entry['_file']}: Katalog-Metadaten stammen von '{upstream.get('ref')}', "
                            f"registriert ist '{pinned}' – mit --online aktualisieren")
            record.update({
                "kind": "external",
                "description": entry.get("description") or upstream.get("description", ""),
                "version": entry.get("version") or upstream.get("version"),
                "repository": f"https://{host}/{entry['repo']}",
                "path": entry.get("path", "").strip("/"),
                "ref": entry.get("ref"),
                "sha": entry.get("sha"),
                "skills": upstream.get("skills", []),
                "components": upstream.get("components", []),
                "upstream": upstream or None,
            })
            if not record["description"]:
                report.warn(f"{entry['_file']}: keine Beschreibung – im Registry-Eintrag oder plugin.json ergänzen")
        record.update({
            "category": entry.get("category"),
            "team": entry.get("team"),
            "keywords": entry.get("keywords") or manifest.get("keywords", []),
            "homepage": entry.get("homepage"),
        })
        records.append({k: v for k, v in record.items() if v not in (None, "", [])})

    owners: dict[str, list[str]] = {}
    for record in records:
        for skill in record.get("skills", []):
            owners.setdefault(skill["name"], []).append(record["name"])
    for skill, plugins in sorted(owners.items()):
        if len(plugins) > 1:
            # OpenCode verlangt eindeutige Skill-Namen, Copilot nimmt stillschweigend den ersten Treffer.
            report.error(f"Skill-Name '{skill}' kommt in mehreren Plugins vor: {', '.join(plugins)}")
    return records


def claude_source(host: str, record: dict):
    if record["kind"] == "local":
        return f"./{record['path']}"
    # Die Kurzform {"source": "github"} gilt nur für github.com – für GHE.com immer die volle Git-URL.
    if record.get("path"):
        source = {"source": "git-subdir", "url": record["repository"] + ".git", "path": record["path"]}
    else:
        source = {"source": "url", "url": record["repository"] + ".git"}
    return source | {k: record[k] for k in ("ref", "sha") if k in record}


def copilot_source(host: str, record: dict):
    if record["kind"] == "local":
        return f"./{record['path']}"
    source = {"source": "url", "url": record["repository"] + ".git"}
    if record.get("path"):
        source["path"] = record["path"]
    return source | {k: record[k] for k in ("ref", "sha") if k in record}


def marketplace_json(cfg: dict, records: list[dict], source_fn) -> str:
    meta, host = cfg["marketplace"], cfg["github"]["host"]
    plugins = []
    for record in records:
        entry = {"name": record["name"], "source": source_fn(host, record)}
        for key in ("description", "version", "category", "keywords", "homepage"):
            if key in record:
                entry[key] = record[key]
        if record["kind"] == "external":
            entry["repository"] = record["repository"]
        plugins.append(entry)
    document = {
        "name": meta["name"],
        "owner": meta["owner"],
        "metadata": {"description": meta.get("description", ""), "version": meta.get("version", "1.0.0")},
        "plugins": plugins,
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def catalog_json(cfg: dict, records: list[dict]) -> str:
    document = {
        "marketplace": {
            "name": cfg["marketplace"]["name"],
            "description": cfg["marketplace"].get("description", ""),
            "git_url": f"https://{cfg['github']['host']}/{cfg['github']['repository']}.git",
        },
        "plugins": records,
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def catalog_md(cfg: dict, records: list[dict]) -> str:
    name = cfg["marketplace"]["name"]
    url = f"https://{cfg['github']['host']}/{cfg['github']['repository']}.git"
    lines = [
        f"# Plugin-Katalog `{name}`",
        "",
        "> Automatisch generiert von `scripts/build_marketplace.py` – nicht von Hand bearbeiten.",
        "",
        "## Marketplace einbinden",
        "",
        "| Client | Befehl |",
        "| --- | --- |",
        f"| GitHub Copilot CLI | `copilot plugin marketplace add {url}` |",
        f"| Claude Code | `claude plugin marketplace add {url}` |",
        "| OpenCode und andere Skill-Clients | `python3 scripts/sync_skills.py` (kopiert Skills nach `~/.agents/skills`) |",
        "",
        "## Übersicht",
        "",
        "| Plugin | Beschreibung | Kategorie | Team | Quelle | Version | Skills | Komponenten |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        if record["kind"] == "local":
            source = f"zentral: `{record['path']}`"
        else:
            where = record["repository"].split("/", 3)[-1] + (f"/{record['path']}" if record.get("path") else "")
            pin = record.get("sha", "")[:7] or record.get("ref", "Default-Branch")
            source = f"[{where}]({record['repository']}) @ `{pin}`"
        lines.append("| " + " | ".join([
            f"[{record['name']}](#{record['name']})",
            cell(record.get("description", "")),
            cell(record.get("category", "")),
            cell(record.get("team", "")),
            source,
            cell(record.get("version", "")),
            str(len(record.get("skills", []))),
            ", ".join(record.get("components", [])),
        ]) + " |")
    for record in records:
        lines += [
            "",
            f"## {record['name']}",
            "",
            record.get("description", "_Keine Beschreibung._"),
            "",
            f"- Installation Copilot: `copilot plugin install {record['name']}@{name}`",
            f"- Installation Claude Code: `claude plugin install {record['name']}@{name}`",
        ]
        if record.get("skills"):
            lines.append("- Skills:")
            lines += [f"  - `{s['name']}` – {cell(s['description'])}" for s in record["skills"]]
        elif record["kind"] == "external":
            lines.append("- Skills: noch nicht erfasst (wird beim nächsten `--online`-Lauf ergänzt)")
    return "\n".join(lines) + "\n"


def build(root: Path, online: bool = False) -> tuple[dict[str, str], Report]:
    report = Report()
    cfg = tomllib.loads((root / "marketplace.toml").read_text(encoding="utf-8"))
    entries = load_registry(root, report)
    gh = None
    if online:
        gh = GitHub(cfg["github"]["host"])
        discover(root, gh, cfg, entries, report)
        bump_refs(root, gh, entries, report)
    records = build_records(root, cfg, entries, report, gh)
    outputs = {
        OUT_CLAUDE: marketplace_json(cfg, records, claude_source),
        OUT_COPILOT: marketplace_json(cfg, records, copilot_source),
        OUT_CATALOG_JSON: catalog_json(cfg, records),
        OUT_CATALOG_MD: catalog_md(cfg, records),
    }
    return outputs, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="nur validieren; Fehler, wenn generierte Dateien veraltet sind")
    mode.add_argument("--online", action="store_true", help="Discovery und Metadaten über die GitHub-API (GH_TOKEN)")
    mode.add_argument("--plugin", type=Path, metavar="PFAD", help="nur ein einzelnes Plugin-Verzeichnis validieren")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.plugin:
        report = Report()
        info = read_local_plugin(args.plugin, args.plugin.as_posix(), report)
        if not info["skills"] and "mcp" not in info["components"]:
            report.warn(f"{args.plugin}: enthält weder Skills noch MCP-Server")
        for warning in report.warnings:
            print(f"WARNUNG: {warning}", file=sys.stderr)
        for error in report.errors:
            print(f"FEHLER: {error}", file=sys.stderr)
        if not report.errors:
            print(f"OK: {info['manifest'].get('name')} mit {len(info['skills'])} Skills")
        return 1 if report.errors else 0

    try:
        outputs, report = build(args.root, online=args.online)
    except (ApiError, urllib.error.URLError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    for relative, content in outputs.items():
        target = args.root / relative
        if target.is_file() and target.read_text(encoding="utf-8") == content:
            continue
        if args.check:
            report.error(f"{relative} ist veraltet – 'python3 scripts/build_marketplace.py' ausführen und committen")
        elif not report.errors:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"aktualisiert: {relative}")

    for warning in report.warnings:
        print(f"WARNUNG: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"FEHLER: {error}", file=sys.stderr)
    if report.errors:
        return 1
    print(f"OK: {len(json.loads(outputs[OUT_CATALOG_JSON])['plugins'])} Plugins im Katalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
