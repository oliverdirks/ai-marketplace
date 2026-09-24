# Plugin-Katalog `acme-ai`

> Automatisch generiert von `scripts/build_marketplace.py` – nicht von Hand bearbeiten.

## Marketplace einbinden

| Client | Befehl |
| --- | --- |
| GitHub Copilot CLI | `copilot plugin marketplace add https://acme.ghe.com/acme-ai/ai-marketplace.git` |
| Claude Code | `claude plugin marketplace add https://acme.ghe.com/acme-ai/ai-marketplace.git` |
| OpenCode und andere Skill-Clients | `python3 scripts/sync_skills.py` (kopiert Skills nach `~/.agents/skills`) |

## Übersicht

| Plugin | Beschreibung | Kategorie | Team | Quelle | Version | Skills | Komponenten |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [engineering-standards](#engineering-standards) | Hausweite Engineering-Konventionen: Commit-Messages und Pull-Request-Beschreibungen | conventions | Platform Engineering | zentral: `plugins/engineering-standards` | 1.0.0 | 2 | skills |

## engineering-standards

Hausweite Engineering-Konventionen: Commit-Messages und Pull-Request-Beschreibungen

- Installation Copilot: `copilot plugin install engineering-standards@acme-ai`
- Installation Claude Code: `claude plugin install engineering-standards@acme-ai`
- Skills:
  - `conventional-commits` – Formuliert Commit-Messages nach der hausweiten Conventional-Commits-Konvention. Verwenden, wenn ein Commit erstellt oder eine Commit-Message vorgeschlagen werden soll.
  - `pull-request-description` – Erstellt Pull-Request-Beschreibungen nach der hausweiten Vorlage (Kontext, Änderungen, Tests, Risiken). Verwenden, wenn ein Pull Request erstellt oder beschrieben werden soll.
