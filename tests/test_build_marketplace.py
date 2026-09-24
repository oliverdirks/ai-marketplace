"""Tests für scripts/build_marketplace.py – ausführen mit: python3 -m unittest discover -s tests"""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_marketplace as bm  # noqa: E402


def file_response(text: str) -> dict:
    return {"type": "file", "encoding": "base64", "content": base64.b64encode(text.encode()).decode()}


def skill_md(name: str, description: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\nInhalt\n"


# Minimaler Ausschnitt der GitHub-REST-API mit zwei Plugin-Repos.
FAKE_API = {
    "/search/repositories": {"items": [
        {"full_name": "acme-ai/terraform-plugin", "default_branch": "main", "description": "Terraform"},
    ]},
    "/repos/acme-ai/terraform-plugin/releases/latest": {"tag_name": "v2.0.0"},
    "/repos/acme-ai/terraform-plugin/contents/.claude-plugin/plugin.json": file_response(json.dumps(
        {"name": "terraform-standards", "description": "Terraform-Konventionen", "version": "2.0.0"})),
    "/repos/acme-ai/terraform-plugin/contents": [
        {"name": ".claude-plugin", "type": "dir"}, {"name": "skills", "type": "dir"}],
    "/repos/acme-ai/terraform-plugin/contents/skills": [{"name": "terraform-module", "type": "dir"}],
    "/repos/acme-ai/terraform-plugin/contents/skills/terraform-module/SKILL.md": file_response(
        skill_md("terraform-module", "Erstellt Terraform-Module nach Hausstandard")),
    "/repos/acme-data/data-tools/releases/latest": {"tag_name": "v0.5.0"},
    "/repos/acme-data/data-tools/contents/ai-plugin/.claude-plugin/plugin.json": file_response(json.dumps(
        {"name": "data-quality", "description": "Datenqualitäts-Checks", "version": "0.4.1"})),
    "/repos/acme-data/data-tools/contents/ai-plugin": [
        {"name": ".claude-plugin", "type": "dir"}, {"name": "skills", "type": "dir"}, {"name": ".mcp.json", "type": "file"}],
    "/repos/acme-data/data-tools/contents/ai-plugin/skills": [{"name": "data-quality-check", "type": "dir"}],
    "/repos/acme-data/data-tools/contents/ai-plugin/skills/data-quality-check/SKILL.md": file_response(
        skill_md("data-quality-check", "Prüft Datensätze auf Vollständigkeit")),
}


class FakeGitHub(BaseHTTPRequestHandler):
    requests: list[tuple[str, str | None]] = []

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        FakeGitHub.requests.append((self.path, self.headers.get("Authorization")))
        body = FAKE_API.get(path)
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body if body is not None else {"message": "Not Found"}).encode())

    def log_message(self, *args) -> None:
        pass


def make_root(extra_registry: dict[str, str] | None = None) -> Path:
    root = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "marketplace.toml", root)
    shutil.copytree(ROOT / "plugins", root / "plugins")
    shutil.copytree(ROOT / "registry", root / "registry")
    for name, content in (extra_registry or {}).items():
        (root / "registry" / name).write_text(content, encoding="utf-8")
    return root


def write_outputs(root: Path, outputs: dict[str, str]) -> None:
    for relative, content in outputs.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(content, encoding="utf-8")


class RepositoryTest(unittest.TestCase):
    def test_committed_files_are_current(self) -> None:
        outputs, report = bm.build(ROOT)
        self.assertEqual(report.errors, [])
        for relative, content in outputs.items():
            self.assertEqual((ROOT / relative).read_text(encoding="utf-8"), content, relative)


class SourceFormatTest(unittest.TestCase):
    def test_external_sources_per_client(self) -> None:
        root = make_root({
            "root-plugin.toml": 'name = "root-plugin"\nrepo = "acme-ai/root-plugin"\nref = "v1.0.0"\ndescription = "x"\n',
            "sub-plugin.toml": 'name = "sub-plugin"\nrepo = "acme-ai/mono"\npath = "tools/ai"\nsha = "' + "a" * 40 + '"\ndescription = "x"\n',
        })
        outputs, report = bm.build(root)
        self.assertEqual(report.errors, [])
        claude = {p["name"]: p["source"] for p in json.loads(outputs[bm.OUT_CLAUDE])["plugins"]}
        copilot = {p["name"]: p["source"] for p in json.loads(outputs[bm.OUT_COPILOT])["plugins"]}

        self.assertEqual(claude["engineering-standards"], "./plugins/engineering-standards")
        self.assertEqual(copilot["engineering-standards"], "./plugins/engineering-standards")
        self.assertEqual(claude["root-plugin"], {"source": "url", "url": "https://acme.ghe.com/acme-ai/root-plugin.git", "ref": "v1.0.0"})
        self.assertEqual(copilot["root-plugin"], {"source": "url", "url": "https://acme.ghe.com/acme-ai/root-plugin.git", "ref": "v1.0.0"})
        self.assertEqual(claude["sub-plugin"], {
            "source": "git-subdir", "url": "https://acme.ghe.com/acme-ai/mono.git", "path": "tools/ai", "sha": "a" * 40})
        self.assertEqual(copilot["sub-plugin"], {
            "source": "url", "url": "https://acme.ghe.com/acme-ai/mono.git", "path": "tools/ai", "sha": "a" * 40})


class ValidationTest(unittest.TestCase):
    def test_skill_name_must_match_directory(self) -> None:
        root = make_root()
        skill = root / "plugins/engineering-standards/skills/conventional-commits/SKILL.md"
        skill.write_text(skill_md("commits", "x"), encoding="utf-8")
        _, report = bm.build(root)
        self.assertTrue(any("muss dem Ordnernamen" in e for e in report.errors), report.errors)

    def test_unregistered_plugin_directory(self) -> None:
        root = make_root()
        (root / "plugins/orphan").mkdir()
        _, report = bm.build(root)
        self.assertTrue(any("plugins/orphan: nicht registriert" in e for e in report.errors), report.errors)

    def test_manifests_must_agree(self) -> None:
        root = make_root()
        portable = root / "plugins/engineering-standards/plugin.json"
        data = json.loads(portable.read_text(encoding="utf-8")) | {"version": "9.9.9"}
        portable.write_text(json.dumps(data), encoding="utf-8")
        _, report = bm.build(root)
        self.assertTrue(any("'version'" in e for e in report.errors), report.errors)

    def test_folded_description(self) -> None:
        fields = bm.parse_frontmatter("---\nname: a\ndescription: >-\n  erste Zeile\n  zweite Zeile\nmetadata:\n  k: v\n---\n")
        self.assertEqual(fields["description"], "erste Zeile zweite Zeile")
        self.assertEqual(fields["name"], "a")


class OnlineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        FakeGitHub.requests = []
        env = {
            "MARKETPLACE_API_URL": f"http://127.0.0.1:{self.server.server_port}",
            "GH_TOKEN": "test-token",
            "NO_PROXY": "127.0.0.1",
            "no_proxy": "127.0.0.1",
        }
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()

    def test_discovery_and_enrichment_are_reproducible_offline(self) -> None:
        root = make_root({
            "data-quality.toml": 'name = "data-quality"\nrepo = "acme-data/data-tools"\npath = "ai-plugin"\nref = "v0.4.1"\ntrack = "releases"\n',
        })
        outputs, report = bm.build(root, online=True)
        self.assertEqual(report.errors, [])

        discovered = (root / "registry/terraform-standards.toml").read_text(encoding="utf-8")
        self.assertIn('repo = "acme-ai/terraform-plugin"', discovered)
        self.assertIn('ref = "v2.0.0"', discovered)
        self.assertIn('track = "releases"', discovered)

        # track = "releases" hebt den Pin auf das neueste Release (Freigabe über den Bot-PR).
        self.assertIn('ref = "v0.5.0"', (root / "registry/data-quality.toml").read_text(encoding="utf-8"))
        copilot = {p["name"]: p["source"] for p in json.loads(outputs[bm.OUT_COPILOT])["plugins"]}
        self.assertEqual(copilot["data-quality"]["ref"], "v0.5.0")

        catalog = {p["name"]: p for p in json.loads(outputs[bm.OUT_CATALOG_JSON])["plugins"]}
        self.assertEqual([s["name"] for s in catalog["terraform-standards"]["skills"]], ["terraform-module"])
        self.assertEqual(catalog["data-quality"]["description"], "Datenqualitäts-Checks")
        self.assertIn("mcp", catalog["data-quality"]["components"])
        self.assertTrue(all(auth == "Bearer test-token" for _, auth in FakeGitHub.requests))
        self.assertTrue(any("ref=v0.5.0" in url for url, _ in FakeGitHub.requests))

        # Ein anschließender Offline-Lauf (wie --check in CI) muss exakt dieselben Dateien erzeugen.
        write_outputs(root, outputs)
        offline, report = bm.build(root)
        self.assertEqual(report.errors, [])
        self.assertEqual(offline, outputs)


if __name__ == "__main__":
    unittest.main()
