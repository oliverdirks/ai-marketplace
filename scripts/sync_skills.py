#!/usr/bin/env python3
"""Synchronisiert Skills aus dem Marketplace in ein lokales Skills-Verzeichnis.

Für Clients ohne Plugin-Marketplace (z. B. OpenCode) oder zum Vorbefüllen von Entwickler-Rechnern.
Das Standardziel ~/.agents/skills lesen u. a. OpenCode und die GitHub Copilot CLI.

  python3 scripts/sync_skills.py --list
  python3 scripts/sync_skills.py                                   # Skills aller Plugins
  python3 scripts/sync_skills.py --plugins engineering-standards   # nur ausgewählte Plugins
  python3 scripts/sync_skills.py --target ~/.config/opencode/skills

Die Auswahl beschreibt den Soll-Zustand: Skills, die das Skript früher installiert hat und die nicht mehr
ausgewählt sind, werden entfernt. Eigene Skills im Zielordner werden nie überschrieben oder gelöscht.
Externe Plugin-Repos werden mit git geklont – die Anmeldung läuft über den normalen Git-Credential-Helper
(z. B. `gh auth login --hostname <host>` und `gh auth setup-git --hostname <host>`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ".ai-marketplace-sync.json"


def checkout(plugin: dict, cache: Path) -> Path:
    """Holt genau den registrierten Stand (sha > ref > Default-Branch) eines externen Plugin-Repos."""
    repo_dir = cache / plugin["name"]
    url = plugin["repository"] + ".git"
    if not (repo_dir / ".git").is_dir():
        repo_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "remote", "add", "origin", url], check=True)
    else:
        subprocess.run(["git", "-C", str(repo_dir), "remote", "set-url", "origin", url], check=True)
    wanted = plugin.get("sha") or plugin.get("ref") or "HEAD"
    subprocess.run(["git", "-C", str(repo_dir), "fetch", "-q", "--depth", "1", "origin", wanted], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "checkout", "-q", "--force", "FETCH_HEAD"], check=True)
    return repo_dir / plugin.get("path", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plugins", help="kommagetrennte Plugin-Namen (Standard: alle)")
    parser.add_argument("--target", type=Path, default=Path.home() / ".agents" / "skills")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "ai-marketplace")
    parser.add_argument("--catalog", type=Path, default=ROOT / "catalog" / "catalog.json")
    parser.add_argument("--list", action="store_true", help="verfügbare Plugins und Skills anzeigen")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    plugins = {p["name"]: p for p in catalog["plugins"]}
    if args.list:
        for plugin in plugins.values():
            print(f"{plugin['name']}: {plugin.get('description', '')}")
            for skill in plugin.get("skills", []):
                print(f"    {skill['name']}")
        return 0

    selected = [name.strip() for name in args.plugins.split(",")] if args.plugins else list(plugins)
    unknown = [name for name in selected if name not in plugins]
    if unknown:
        print(f"Unbekannte Plugins: {', '.join(unknown)} (siehe --list)", file=sys.stderr)
        return 1

    target = args.target.expanduser()
    target.mkdir(parents=True, exist_ok=True)
    state_path = target / STATE_FILE
    managed: dict[str, str] = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}

    installed: dict[str, str] = {}
    for name in selected:
        plugin = plugins[name]
        source = ROOT / plugin["path"] if plugin["kind"] == "local" else checkout(plugin, args.cache.expanduser())
        for skill_file in sorted(source.glob("skills/*/SKILL.md")):
            skill = skill_file.parent.name
            destination = target / skill
            if destination.exists() and skill not in managed:
                print(f"übersprungen: {skill} existiert bereits in {target} und wird nicht von diesem Skript verwaltet")
                continue
            if skill in installed:
                print(f"übersprungen: {skill} aus {name} – bereits aus {installed[skill]} installiert")
                continue
            shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(skill_file.parent, destination)
            installed[skill] = name
            print(f"installiert: {skill} ({name})")

    for skill in sorted(set(managed) - set(installed)):
        shutil.rmtree(target / skill, ignore_errors=True)
        print(f"entfernt: {skill}")
    state_path.write_text(json.dumps(installed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(installed)} Skills in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
