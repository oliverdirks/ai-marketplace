# Vorlage: Plugin-Repo eines Teams

Diese Vorlage zeigt, wie ein Team ein eigenes Repository als Plugin-Quelle für den Marketplace `acme-ai` aufsetzt.
Das Plugin liegt dabei im **Repo-Root** (für einen Unterordner siehe `path` weiter unten).

```text
mein-plugin/
├── .claude-plugin/plugin.json   # Manifest für Claude Code (Copilot liest es ebenfalls)
├── plugin.json                  # Manifest nach Agent Plugins 1.0 (Copilot, weitere Clients) – synchron halten
├── skills/
│   └── <skill-name>/SKILL.md    # portabel: Copilot, Claude Code, OpenCode, Codex, Cursor …
├── mcp.json / .mcp.json         # optional: MCP-Server (Agent-Plugins- bzw. Claude-Format)
└── .github/workflows/notify-marketplace.yml   # optional: Refresh nach Release
```

## So wird das Repo Teil des Marketplaces

1. Vorlage kopieren, `example-plugin` und `example-skill` umbenennen. Regeln für Namen: nur Kleinbuchstaben,
   Ziffern und Bindestriche. Der Skill-Name muss dem Ordnernamen entsprechen und hausweit eindeutig sein.
2. Sichtbarkeit **internal**, damit alle Mitarbeitenden das Plugin installieren können.
3. Topic `ai-plugin` setzen. Der nächtliche Lauf im Marketplace findet das Repo und schlägt per Pull Request
   einen Eintrag in `registry/` vor. Alternativ den Eintrag selbst per PR anlegen:

   ```toml
   # registry/mein-plugin.toml im Marketplace-Repo
   name = "mein-plugin"
   repo = "acme-team/mein-plugin"
   ref = "v1.0.0"          # Tag oder Branch; alternativ sha = "<40-stelliger Commit>"
   track = "releases"      # optional: neue Releases automatisch per Bot-PR übernehmen
   # path = "ai-plugin"    # nur, wenn das Plugin in einem Unterordner liegt
   category = "infrastructure"
   team = "Team Plattform"
   ```

4. Releases als Git-Tags (`v1.2.0`) veröffentlichen und `version` in beiden Manifesten mitziehen.

## Lokal prüfen

```bash
# Validierung wie im Marketplace (Manifeste, SKILL.md-Frontmatter, Namen)
python3 <pfad-zum>/ai-marketplace/scripts/build_marketplace.py --plugin .

# Mit den echten Clients testen
copilot plugin install ./
claude plugin validate .
```
