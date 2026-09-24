# AI Marketplace

Hausweiter Marketplace und Katalog für KI-Plugins, Agent Skills und MCP-Konfigurationen, betrieben auf
GitHub Enterprise Cloud mit Data Residency (GHE.com). Ein Repository dient als **Index**. Die Plugins selbst
können zentral hier oder **verteilt in den Repos der Teams** liegen.

| Client | Anbindung |
| --- | --- |
| GitHub Copilot (CLI, VS Code, Copilot-App, Cloud Agent, JetBrains) | nativ über `.github/plugin/marketplace.json` |
| Claude Code | nativ über `.claude-plugin/marketplace.json` |
| OpenCode und andere Skill-Clients | `scripts/sync_skills.py` kopiert Skills nach `~/.agents/skills` |

Die Übersicht aller Plugins steht in [`catalog/CATALOG.md`](catalog/CATALOG.md), maschinenlesbar in
[`catalog/catalog.json`](catalog/catalog.json).

## Architektur

```text
 Team-Repos (internal, Topic "ai-plugin")          acme-ai/ai-marketplace
 ┌──────────────────────────────┐        ┌────────────────────────────────────────────────────────────┐
 │ acme-platform/terraform-...  │─┐      │ registry/*.toml   ← ein Eintrag je Plugin (Repo, Ref, Team)│
 │ acme-data/data-tools/ai-...  │─┼────► │ plugins/*         ← zentral gepflegte Plugins              │
 │ …                            │─┘      │ marketplace.toml  ← Name, GHE.com-Host, Discovery          │
 └──────────────────────────────┘        │            │                                               │
        ▲  Clients klonen die            │            ▼  scripts/build_marketplace.py (CI)            │
        │  Plugins direkt aus            │  .github/plugin/marketplace.json   → Copilot               │
        │  den Team-Repos                │  .claude-plugin/marketplace.json   → Claude Code           │
        └────────────────────────────────│  catalog/catalog.json + CATALOG.md → Übersicht, Sync       │
                                         └────────────────────────────────────────────────────────────┘
```

### Zentral oder verteilt?

Beides funktioniert, und dieses Repo kombiniert es:

- **Der Marketplace ist nur eine Datei** (`marketplace.json`). Jeder Eintrag darin zeigt über `source` auf ein
  Plugin. Das kann ein Ordner in diesem Repo sein (`"./plugins/x"`) oder ein **beliebiges anderes Git-Repo**,
  auf Wunsch mit Unterordner und gepinntem Tag oder Commit. GitHub macht es mit
  [`github/awesome-copilot`](https://github.com/github/awesome-copilot) genauso: ein Teil der Plugins liegt im
  Repo, rund 60 kommen aus fremden Repos.
- **Zentral (`plugins/`)** eignet sich für hausweite Standards, die ein Plattform-Team pflegt.
- **Verteilt (`registry/` → Team-Repo)** eignet sich für fachliche Plugins. Das Team behält Code, Reviews und
  Releases in seinem Repo. Hier liegt nur ein kleiner Registry-Eintrag, der auf einen Tag zeigt.

Voraussetzungen für verteilte Plugins:

- Wer installiert, braucht Lesezugriff auf das Plugin-Repo. Deshalb Sichtbarkeit `internal`.
- Weil wir auf GHE.com arbeiten, verwenden die generierten Dateien immer die **volle Git-URL**
  (`https://acme.ghe.com/org/repo.git`). Die Kurzform `"source": "github"` mit `owner/repo` meint github.com.
- Die Clients klonen per `git`. Die Anmeldung läuft daher über den Git-Credential-Helper (siehe unten).

## Verzeichnisstruktur

```text
ai-marketplace/
├── marketplace.toml                  # Konfiguration: Name, Owner, GHE.com-Host, Discovery
├── registry/                         # ein TOML je Plugin (zentral und extern) – Quelle der Wahrheit
├── plugins/                          # zentral gepflegte Plugins
│   └── engineering-standards/
│       ├── .claude-plugin/plugin.json
│       ├── plugin.json               # Agent Plugins 1.0 (portabel), synchron zum obigen Manifest
│       └── skills/<skill>/SKILL.md
├── .github/plugin/marketplace.json   # GENERIERT – GitHub Copilot
├── .claude-plugin/marketplace.json   # GENERIERT – Claude Code
├── catalog/                          # GENERIERT – Übersicht (Markdown + JSON)
├── scripts/
│   ├── build_marketplace.py          # validiert, entdeckt Repos, generiert alle Dateien
│   └── sync_skills.py                # Skills für OpenCode & Co. lokal installieren
├── templates/plugin-repo/            # Vorlage für Team-Repos
├── config-examples/                  # Managed Settings und Repo-Settings für die Clients
├── tests/
└── .github/workflows/marketplace.yml # CI: Validierung, nächtliche Discovery mit Bot-PR
```

Warum zwei Marketplace-Dateien? Copilot sucht zuerst `.github/plugin/marketplace.json`, Claude Code liest nur
`.claude-plugin/marketplace.json`. Beide Clients verstehen relative Pfade und `url`-Quellen. Für Plugins in
einem Unterordner eines fremden Repos brauchen sie aber verschiedene Schreibweisen: Copilot `url` + `path`,
Claude Code `git-subdir`. Das Skript erzeugt deshalb aus derselben Registry beide Varianten.

## Plugin-Format: portabel aufbauen

| Baustein | Ort im Plugin | Wer liest es |
| --- | --- | --- |
| Skills ([Agent Skills](https://agentskills.io)) | `skills/<name>/SKILL.md` | Copilot, Claude Code, OpenCode, Codex, Cursor, … |
| Manifest Claude Code | `.claude-plugin/plugin.json` | Claude Code, Copilot (Legacy-Format) |
| Manifest [Agent Plugins 1.0](https://github.com/agentplugins/agent-plugins-spec) | `plugin.json` | Copilot und weitere Clients, die den Standard umsetzen |
| MCP-Server | `.mcp.json` (Claude Code) und `mcp.json` (Agent Plugins) | jeweiliger Client |
| Copilot-spezifisch (Agents, Hooks, Commands) | `com.github.copilot/…` | nur Copilot |
| Claude-spezifisch (Agents, Hooks, Commands) | `agents/`, `hooks/`, `commands/` | nur Claude Code |

Der kleinste gemeinsame Nenner sind **Skills**. Sie funktionieren in allen Tools. Baut Plugins deshalb
„skills first“ und legt tool-spezifische Teile nur zusätzlich in die dafür vorgesehenen Ordner. Das
Build-Skript prüft, dass beide Manifeste in `name`, `version` und `description` übereinstimmen und dass
Skill-Namen hausweit eindeutig sind. OpenCode verlangt eindeutige Namen, Copilot nimmt bei Dubletten
stillschweigend den ersten Treffer.

## Clients anbinden

### Anmeldung an GHE.com (einmalig pro Rechner)

```bash
gh auth login --hostname acme.ghe.com
gh auth setup-git --hostname acme.ghe.com   # Git-Credential-Helper für alle git-Klone
copilot login --host https://acme.ghe.com    # Copilot CLI
```

Hintergrund-Updates der Clients laufen ohne Rückfrage. Der Credential-Helper muss daher ohne interaktive Eingabe
funktionieren.

### GitHub Copilot

Manuell:

```bash
copilot plugin marketplace add https://acme.ghe.com/acme-ai/ai-marketplace.git
copilot plugin marketplace browse acme-ai
copilot plugin install engineering-standards@acme-ai
```

Unternehmensweit über **Enterprise Managed Settings**: Legt [`config-examples/managed-settings.json`](config-examples/managed-settings.json)
im `.github-private`-Repo der Governance-Organisation unter `copilot/managed-settings.json` ab. Das Repo muss in
den Enterprise-Einstellungen als Quelle ausgewählt sein. Unterstützt werden Copilot CLI, VS Code, die
Copilot-App, der Cloud Agent und JetBrains. Die Datei

- registriert den Marketplace für alle (`extraKnownMarketplaces`, mit `autoUpdate`),
- installiert Pflicht-Plugins automatisch (`enabledPlugins`),
- lässt mit `strictKnownMarketplaces` nur Marketplaces auf `acme.ghe.com` zu. Achtung: Das sperrt auch
  öffentliche Marketplaces wie `awesome-copilot`. Entfernt den Block, wenn das nicht gewollt ist.

Die GitHub-Doku zu Managed Settings nennt keine Einschränkung für GHE.com. Prüft die Verfügbarkeit für euren
Tenant trotzdem mit einer Testgruppe. Als Alternative lassen sich die Settings per MDM oder als lokale Datei
verteilen.

Pro Repository: [`config-examples/consumer-repo/.github/copilot/settings.json`](config-examples/consumer-repo/.github/copilot/settings.json)
aktiviert Plugins nur in diesem Repo. Die Datei wirkt für die Copilot CLI und den Cloud Agent.

### Claude Code (optional)

```bash
claude plugin marketplace add https://acme.ghe.com/acme-ai/ai-marketplace.git
claude plugin install engineering-standards@acme-ai
```

Zentral verteilen: Dieselbe `config-examples/managed-settings.json` funktioniert auch als Claude-Code-Datei
`managed-settings.json`. Pfade: `/etc/claude-code/` unter Linux,
`/Library/Application Support/ClaudeCode/` unter macOS, `C:\Program Files\ClaudeCode\` unter Windows.
Pro Repo: [`config-examples/consumer-repo/.claude/settings.json`](config-examples/consumer-repo/.claude/settings.json).
Die Copilot CLI liest diese Datei ebenfalls.

### OpenCode und weitere Skill-Clients

OpenCode hat keinen Plugin-Marketplace. Skills lädt es aus `.opencode/skills/`, `.claude/skills/` und
`.agents/skills/`, jeweils im Projekt und im Home-Verzeichnis. Das Sync-Skript nutzt den Katalog und installiert
Skills nach `~/.agents/skills`. Diesen Ordner liest auch die Copilot CLI.

```bash
git clone https://acme.ghe.com/acme-ai/ai-marketplace.git && cd ai-marketplace
python3 scripts/sync_skills.py --list
python3 scripts/sync_skills.py --plugins engineering-standards   # Auswahl = Soll-Zustand
```

Das Skript klont externe Plugin-Repos genau auf den registrierten Ref oder SHA. Eigene Skills im Zielordner
überschreibt es nicht. Ausgerollt wird es z. B. per Devcontainer, Onboarding-Skript oder MDM-Job.
OpenCode-*Plugins* (JS/TS-Module mit Hooks) sind ein eigenes Konzept. Sie werden als npm-Pakete über eine
interne Registry verteilt und in `opencode.json` unter `plugin` eingetragen.

Für weitere Tools mit eigenem Marketplace-Format genügt eine zusätzliche Ausgabefunktion in
`build_marketplace.py` (analog zu `copilot_source`/`claude_source`). Registry und Katalog bleiben gleich.

## Plugin veröffentlichen

**Zentral:** Ordner unter `plugins/<name>/` anlegen (Aufbau wie `engineering-standards`), dazu
`registry/<name>.toml` mit `name`, `category`, `team`. Dann `python3 scripts/build_marketplace.py` ausführen und
alles per PR einreichen.

**Verteilt:** Team-Repo nach [`templates/plugin-repo`](templates/plugin-repo) aufsetzen und Topic `ai-plugin`
vergeben. Der nächtliche Lauf schlägt den Registry-Eintrag per PR vor. Alternativ legt das Team
`registry/<name>.toml` selbst an:

```toml
name = "terraform-standards"
repo = "acme-platform/terraform-ai-plugin"  # org/repo auf acme.ghe.com
ref = "v1.2.0"                              # Tag/Branch, oder sha = "<40-stelliger Commit>"
track = "releases"                          # optional: neue Releases per Bot-PR übernehmen
# path = "ai-plugin"                        # falls das Plugin in einem Unterordner liegt
description = "Terraform-Konventionen und Modul-Generator"
category = "infrastructure"
team = "Plattform"
```

**Versionierung und Freigabe:** Clients installieren genau den Stand aus `ref` bzw. `sha`. Neue Versionen
kommen erst in den Marketplace, wenn der Registry-Eintrag per PR angehoben wird. Bei `track = "releases"`
erstellt der Bot diesen PR selbst. So bleibt jede Änderung reviewbar, auch bei verteilten Repos.

## Übersicht aller Plugin-Repos (Discovery)

`python3 scripts/build_marketplace.py --online` (läuft werktags per Workflow):

1. sucht in den Organisationen aus `marketplace.toml` alle Repos mit dem Topic `ai-plugin`,
2. legt für neue Repos einen Registry-Eintrag an (gepinnt auf das neueste Release),
3. hebt bei `track = "releases"` den Ref auf das neueste Release,
4. liest Manifest, Skills und Komponenten jedes externen Plugins über die API
   (`https://api.acme.ghe.com`) und schreibt sie in den Katalog,
5. öffnet einen PR mit allen Änderungen. Im PR wird freigegeben.

Soll statt Topics eine strengere Kennzeichnung gelten, eignen sich **Custom Properties** der Organisation
(z. B. `ai-plugin = true`). Die legen nur Org-Admins fest. Dafür muss in `discover()` die Suche durch
`GET /orgs/{org}/properties/values` ersetzt werden.

## Einrichtung

1. Dieses Repo in der Governance-Organisation anlegen, Sichtbarkeit `internal`.
2. In `marketplace.toml` Host, Repository, Organisationen und Marketplace-Namen setzen. Die Platzhalter
   `acme.ghe.com` bzw. `acme-ai` auch in `config-examples/` und `templates/` ersetzen. Danach
   `python3 scripts/build_marketplace.py` ausführen.
3. **GitHub App** für den Workflow anlegen. Rechte: *Metadata: read*, *Contents: read & write*,
   *Pull requests: write*. In der Marketplace-Organisation und allen Organisationen mit Plugin-Repos installieren.
   `MARKETPLACE_APP_ID` als Variable und `MARKETPLACE_APP_PRIVATE_KEY` als Secret hinterlegen. Weitere
   Organisationen erhalten im Workflow je einen eigenen Token (`GH_TOKEN__<ORG>`, siehe Kommentar in
   `.github/workflows/marketplace.yml`).
4. Branch-Protection auf `main` mit Pflicht-Check `validate` und Reviews. Per `CODEOWNERS` können Teams ihre
   eigenen Einträge freigeben:

   ```text
   *                              @acme-ai/ai-platform
   /registry/terraform-*.toml     @acme-platform/terraform-team
   /plugins/engineering-standards/ @acme-ai/ai-platform
   ```

5. Managed Settings ausrollen (siehe oben), zuerst für eine Testgruppe.

## Lokale Entwicklung

```bash
python3 scripts/build_marketplace.py            # generierte Dateien aktualisieren
python3 scripts/build_marketplace.py --check    # wie CI: validieren und Aktualität prüfen
python3 scripts/build_marketplace.py --plugin ./plugins/engineering-standards
python3 -m unittest discover -s tests
```

Benötigt nur Python ≥ 3.11 ohne zusätzliche Pakete.
