# Fahrplan: Software Factory mit Cloud Agents

Stand: Oktober 2026. Funktionen der Anbieter ändern sich schnell. Alles, was mit „prüfen“ markiert ist, vor der
Umsetzung auf dem eigenen GHE.com-Tenant testen.

## Kurzfassung

- **GitHub ist das Rückgrat, der Agent ist austauschbar.** Der Prozess (Anforderung → Architektur → Umsetzung →
  Test → Release) läuft über Issues, Pull Requests, Rulesets und Actions. Coding Agents sind Arbeiter in diesem
  Prozess, keine Plattform. Dann lässt sich der Agent wechseln, ohne den Prozess neu zu bauen.
- **Copilot Cloud Agent als Standard-Engine.** Er ist in der Copilot-Lizenz enthalten, läuft auf GHE.com mit Data
  Residency und lässt sich aus Microsoft Teams starten. Mindestens eine zweite Engine (z. B. Claude Code oder
  OpenCode) wird von Anfang an mitgeführt. So bleibt der Wechsel möglich und wird regelmäßig geübt.
- **Das Wissen der Fachteams liegt in offenen Formaten.** Skills (`SKILL.md`), `AGENTS.md` und MCP-Server
  funktionieren in Copilot, Claude Code, Codex, OpenCode und weiteren Tools. Verteilt werden sie über diesen
  Marketplace. Er ist bereits gebaut.
- **Menschen entscheiden an festen Toren.** Agenten schreiben Anforderungen, Code und Tests. Freigaben (Spezifikation,
  Architektur, Merge, Produktion) erteilt ein Mensch. Was sich prüfen lässt, prüft die Pipeline und nicht der
  Prompt.
- **„Jeder kann Pro-Code-Anwendungen erstellen“ braucht ein Ownership-Modell.** Jeder kann eine Anwendung anstoßen
  und steuern. Betrieb, Sicherheit und Wartung brauchen aber ein verantwortliches Team. Ohne Risikoklassen und
  Owner entsteht Schatten-IT im großen Maßstab.
- **Realistischer Zeitrahmen: 12 bis 18 Monate** bis zum Self-Service über Teams für unkritische Anwendungen. Erste
  produktive Ergebnisse (Issue → Agent → Pull Request) gibt es nach 2 bis 3 Monaten.

## 1. Zielbild

```text
 Teams / Slack / Portal          GitHub Enterprise Cloud (acme.ghe.com)                           Laufzeit
 ┌──────────────────┐ Intake  ┌────────────────────────────────────────────────────────────────┐ ┌──────────┐
 │ „Wir brauchen    │───────► │ 1 Anforderung (Issue)                                          │ │          │
 │  ein Tool für …“ │         │     BA-Agent: Rückfragen, User Stories, Akzeptanzkriterien     │ │          │
 └──────────────────┘         │     EA-Agent: Architektur-Check, ADR-Entwurf, Risikoklasse     │ │          │
        ▲                     │   ◆ Freigabe Spezifikation (Product Owner)                     │ │          │
        │ Status, Rückfragen  │ 2 Repo aus Golden Path (Template, CI/CD, Infrastruktur)        │ │  Dev     │
        └─────────────────────│ 3 Coding-Agent: Implementierung → Pull Request                 │ │  Test    │
                              │     Test-Agent, Review-Agent, Integrations-Checks              │ │  Prod    │
                              │     CI-Gates: Tests, CodeQL, Policies, API-Linting, SBOM       │ │          │
                              │   ◆ Review und Merge (Mensch, CODEOWNERS)                      │ │          │
                              │ 4 CD über Environments    ◆ Freigabe Produktion                │►│          │
                              │ 5 Betrieb: Alerts/Incidents → Issue → Agent-Fix                │ │          │
                              └────────────────────────────────────────────────────────────────┘ └──────────┘
                                      ▲ Skills, Custom Agents, MCP-Server aus dem Marketplace (dieses Repo)
```

`◆` markiert menschliche Freigaben. Wie viele davon nötig sind, hängt von der Risikoklasse ab (siehe Abschnitt 6).

### Stufen der Autonomie

| Stufe | Bezeichnung | Was passiert | Phase im Fahrplan |
| --- | --- | --- | --- |
| 1 | Assistenz | Copilot in der IDE und CLI, Skills aus dem Marketplace | 0 |
| 2 | Delegation | Issue an Agent zuweisen, Agent liefert Pull Request | 1 |
| 3 | Orchestrierter Prozess | Mehrere spezialisierte Agenten durchlaufen den Prozess mit Gates | 2 |
| 4 | Self-Service | Fachbereiche starten Anwendungen über Teams | 3 |
| 5 | Kontinuierliche Wartung | Agenten übernehmen Updates, CI-Fehler und Incidents | 4 |

## 2. Architektur in Schichten

Die Schichten sind so geschnitten, dass jede einzeln ersetzt werden kann. Darin liegt der Schutz vor Vendor-Lock-in.

| # | Schicht | Inhalt | Standard-Wahl | Austauschbar durch | Lock-in |
| --- | --- | --- | --- | --- | --- |
| 1 | Interaktion | Chat, Portal, IDE, CLI | Teams (GitHub-App), VS Code | Slack, Backstage, Web-Portal | gering (dünner Adapter) |
| 2 | Prozess und Orchestrierung | Zustände, Übergaben, Trigger | Issues, Projects, Labels, Actions, Agentic Workflows | GitLab, Azure DevOps (mit Aufwand) | mittel (GitHub) |
| 3 | Agent-Laufzeit | führt Aufgaben im Repo aus | Copilot Cloud Agent | Claude Code, Codex, OpenCode, OpenHands | gering, wenn 2 und 4 offen sind |
| 4 | Wissen und Fähigkeiten | Skills, `AGENTS.md`, Custom Agents, MCP | dieser Marketplace | – (offene Standards) | gering |
| 5 | Golden Paths | Templates, Reusable Workflows, IaC-Module | eigene Template-Repos | – (eigener Code) | gering |
| 6 | Qualitäts- und Sicherheits-Gates | Tests, Policies, Scans, Freigaben | Rulesets, CodeQL, Dependabot, Environments | Sonar, Snyk, OPA/Conftest | gering bis mittel |
| 7 | Modelle | LLMs hinter den Agenten | Modellauswahl in Copilot | LLM-Gateway für eigene Agenten | gering bei Multi-Modell |
| 8 | Governance und Beobachtung | Audit, Kosten, Metriken | Audit-Log-Streaming, Copilot-Metriken | SIEM, OpenTelemetry | gering |

Zwei Regeln halten die Schichten sauber:

1. **Keine Prozesslogik im Agenten.** Der Agent bekommt eine Aufgabe (Issue, Spezifikation) und liefert ein Ergebnis
   (Kommentar, Pull Request). Welcher Schritt als Nächstes kommt, entscheidet der Prozess in Schicht 2.
2. **Keine Fachlogik im Chat-Adapter.** Der Teams-Bot übersetzt nur zwischen Chat und Issues. Dieselbe Intake-Logik
   ist dann auch aus Slack, einem Portal oder der GitHub-Oberfläche erreichbar.

## 3. GitHub Copilot oder andere Coding Agents?

### Vergleich

| | Copilot Cloud Agent | Claude Code | OpenAI Codex | OpenCode / OpenHands (Open Source) |
| --- | --- | --- | --- | --- |
| Ausführung | gemanagt in GitHub Actions | CLI und Agent SDK; in CI per GitHub Action; als Third-Party-Agent über Agent HQ | Codex Cloud, CLI, GitHub Action | selbst betrieben (CLI, GitHub Action, Plattform) |
| GHE.com mit Data Residency | ja (seit 08/2025) | im eigenen Runner ja; Agent HQ auf GHE.com prüfen | Codex Cloud nein (nur github.com); CLI im eigenen Runner ja | ja |
| Start aus Teams | ja (GitHub-App bzw. GHEC-App) | eigener Bot nötig | eigener Bot nötig | eigener Bot nötig |
| Modelle | mehrere Anbieter (OpenAI, Anthropic, Google) | Claude (Anthropic-API oder Cloud-Anbieter) | OpenAI | beliebig, auch selbst gehostet |
| Offene Formate | `AGENTS.md`, Skills, MCP | Skills, MCP, `CLAUDE.md` (kann `AGENTS.md` importieren) | `AGENTS.md`, Skills, MCP | `AGENTS.md`, Skills, MCP |
| Kosten | Copilot-Lizenz + Premium Requests + Actions-Minuten | Lizenz oder nutzungsbasiert | Lizenz oder API | Infrastruktur + Modellkosten |
| Stärken | tiefste GitHub-Integration, zentrale Policies, kein Betrieb | sehr gute Agentenqualität, SDK für eigene Agenten | Ökosystem rund um `AGENTS.md` | volle Souveränität, keine Anbieterbindung |
| Schwächen | an GitHub gebunden | eine Modellfamilie | GHE.com nur mit Selbstbetrieb | eigener Betrieb, Sicherheit und Updates |

### Empfehlung

1. **Copilot Cloud Agent als Standard.** Ihr arbeitet auf GHE.com, habt den Marketplace für Copilot gebaut und wollt
   Teams als Einstieg. Copilot deckt das ohne eigenen Betrieb ab. Die Modellauswahl in Copilot verringert die
   Bindung an einen Modellanbieter.
2. **Claude Code als Zweit-Engine.** Über Agent HQ (falls auf GHE.com verfügbar), über GitHub Agentic Workflows oder
   über die GitHub Action im eigenen Runner. Einsatz: Vergleich auf denselben Aufgaben, Fallback und Bau eigener
   Agenten mit dem Agent SDK.
3. **OpenCode als Souveränitätspfad.** Einmal im Quartal läuft eine Referenzaufgabe mit OpenCode und einem anderen
   bzw. selbst gehosteten Modell. Das belegt, dass der Ausstieg funktioniert.
4. **Keine eigene Orchestrierungsplattform bauen.** Issues, Labels, Actions und Agentic Workflows reichen für die
   ersten Phasen. Eigener Code entsteht nur dort, wo GitHub nichts bietet: im Intake-Bot und in eigenen
   Fach-Agenten.

## 4. Fahrplan

Die Phasen überlappen. Die Monate sind Richtwerte für eine Organisation mit mehreren Entwicklungsteams.

### Phase 0: Fundament und Governance (Monat 0 bis 3)

Ziel: Rahmen, Plattform und erste Golden Paths stehen. Copilot läuft in der IDE.

| Thema | Ergebnis |
| --- | --- |
| Organisation | Factory-Team benannt (Produktverantwortung, Plattform-Engineering, AI-Engineering). Sponsor im Management. |
| Mitbestimmung und Recht | Betriebsrat früh einbinden (Agent-Metriken können Leistungsdaten sein). Leitlinie zur KI-Nutzung, Datenklassifizierung, Nachweis der KI-Kompetenz nach Art. 4 EU AI Act. Je nach Branche DORA bzw. NIS2 prüfen. |
| Copilot-Policies | Lizenzen, Modell-Allowlist, MCP-Policy, Cloud Agent zunächst nur für die Pilot-Organisation. Managed Settings aus diesem Repo ausrollen. |
| Marketplace | Dieses Repo produktiv: Registry, Discovery, Managed Settings. |
| Repo-Baseline | Rulesets für alle Repos: Pull Request mit Review, Pflicht-Checks, CODEOWNERS, Secret Scanning mit Push Protection, CodeQL, Dependabot. |
| Golden Path | Ein bis zwei Template-Repos für die häufigsten Stacks, inklusive `AGENTS.md`, CI/CD über Reusable Workflows, Devcontainer, Infrastruktur-Modul, OIDC zur Cloud. |
| Runner | GitHub-hosted Runner mit privatem Netzwerk oder Self-hosted Runner (Actions Runner Controller), damit Agenten interne Systeme erreichen können. |
| Messung | Ausgangswerte erheben: Durchlaufzeit, Deployment-Frequenz, Change Failure Rate, Review-Dauer. |

Abschlusskriterium: Ein neues Repo aus dem Template baut, testet und deployt ohne Handarbeit in eine
Testumgebung.

### Phase 1: Delegation an Agenten (Monat 2 bis 6)

Ziel: Pilot-Teams geben Issues an Agenten ab und mergen deren Pull Requests regelmäßig.

- Copilot Cloud Agent für zwei bis drei Pilot-Teams freischalten. Umgebung des Agenten pro Repo über
  `.github/workflows/copilot-setup-steps.yml` festlegen. Firewall-Allowlist des Agenten pflegen.
- **Erster Skill je Fachteam** im Marketplace, z. B. `user-story-refinement` (Business Analyse),
  `adr-writing` (Unternehmensarchitektur), `openapi-guidelines` (Integration), `test-strategy` (Testing),
  `threat-modeling` (Security). Format und Ablauf sind in [`templates/plugin-repo`](../templates/plugin-repo)
  beschrieben.
- **Custom Agents je Rolle** als `.agent.md` im `.github-private`-Repo der Organisation. Sie gelten dann für alle
  Repos der Organisation.
- **MCP-Server für interne Systeme**, z. B. Architektur-Repository, API-Katalog, Wiki, Ticketsystem. Freigabe über
  eine Allowlist.
- **Agenten-Review**: Copilot Code Review für jeden Pull Request, optional eine Zweit-Engine.
- **Evals für Skills**: Je Skill einige Referenzaufgaben mit erwartetem Ergebnis, die bei jeder Änderung im
  Plugin-Repo laufen (z. B. mit promptfoo). Skills sind Produkte mit Version, Owner und Tests.

Abschlusskriterium: Mehr als 30 % der Issues eines Pilot-Teams werden von Agenten umgesetzt und ohne größere
Nacharbeit gemergt.

### Phase 2: Orchestrierter Prozess (Monat 5 bis 10)

Ziel: Der gesamte Weg von der Anforderung bis zum Release ist als Prozess mit Agenten und Gates abgebildet.

- **Prozess als Zustandsmaschine** auf Issues und Projects:

  ```text
  factory:intake → factory:refine → factory:architecture → factory:approved → factory:build → factory:verify → factory:release
     (Mensch)        (BA-Agent)        (EA-Agent)            ◆ Freigabe        (Coding-Agent)   (Test-Agent, CI)   ◆ Freigabe
  ```

  Jeder Label-Wechsel löst einen Workflow aus. Der Workflow startet den passenden Agenten mit dem passenden Custom
  Agent und den passenden Skills.
- **Spezifikation vor Code (Spec-driven Development)**: `spec.md`, `plan.md` und `tasks.md` liegen im Repo und werden
  per Pull Request freigegeben. Werkzeuge wie GitHub Spec Kit sind agentenunabhängig.
- **GitHub Agentic Workflows** (technische Vorschau) für die agentischen Schritte: Workflows in Markdown, Engine
  wählbar (Copilot, Claude Code, Codex u. a.), Schreibrechte nur über eng begrenzte „Safe Outputs“. Verfügbarkeit
  auf GHE.com prüfen. Alternative: Reusable Workflow `run-agent.yml` mit Input `engine`.
- **App-Bootstrap-Workflow**: Legt aus einer freigegebenen Anforderung ein Repo aus dem Golden Path an, setzt
  Owner-Team, Risikoklasse (Custom Property), Environments, OIDC-Zugänge und einen Katalogeintrag.
- **Pipeline-Gates der Fachteams** (siehe Abschnitt 5) als Pflicht-Checks in Rulesets.

Abschlusskriterium: Eine neue interne Anwendung der Risikoklasse T1 läuft vom Issue bis zur Testumgebung durch.
Menschen greifen nur an den Freigabepunkten ein.

### Phase 3: Self-Service über Teams (Monat 9 bis 14)

Ziel: Fachbereiche stoßen Anwendungen und Änderungen aus Teams an.

- **Schnellstart:** Die GitHub-App für Teams (auf GHE.com die GHEC-App) startet Cloud-Agent-Sessions aus Threads und
  Meetings heraus. Das genügt für Personen mit Schreibrechten auf dem Repo, also vor allem für Entwicklungsteams.
- **Intake für alle:** Ein eigener, schlanker Teams-Bot (Microsoft 365 Agents SDK) führt das Anforderungsgespräch.
  Er nutzt dieselben BA-Skills aus dem Marketplace. Gebaut wird er mit einem Agent-Framework, z. B. Copilot SDK,
  Claude Agent SDK oder Microsoft Agent Framework. Am Ende legt er über eine GitHub App ein Issue im Intake-Repo an.
  Ab dort übernimmt der Prozess aus Phase 2. Status und Rückfragen spiegelt der Bot in den Chat zurück.
- **Leitplanken für Fachbereiche**: Risikoklassen erzwingen, Sandbox-Umgebungen für Prototypen, automatischer Ablauf
  von T0-Anwendungen, kein Weg in Produktion ohne Owner-Team.
- **Enablement**: Schulung „Anforderungen für Agenten formulieren“, Champions-Netzwerk in den Fachbereichen.

Abschlusskriterium: Fachbereiche bringen T0- und T1-Anwendungen ohne Ticket an ein Entwicklungsteam bis in die
Testumgebung.

### Phase 4: Skalierung und kontinuierliche Wartung (ab Monat 12)

- Agenten beheben fehlgeschlagene CI-Läufe, übernehmen Dependency- und Framework-Updates und erzeugen Fix-PRs aus
  Incidents.
- Mehrere Engines parallel auf dieselbe Aufgabe ansetzen und das beste Ergebnis übernehmen.
- FinOps für Agenten: Budget je Organisation, Kosten je gemergtem Pull Request, Kontingente.
- Regelmäßige Auswertung: Welche Skills wirken, welche Gates schlagen an, wo entsteht Nacharbeit?

## 5. Was die Fachteams beitragen

Jedes Fachteam liefert drei Dinge: **Skills** (Wissen und Vorgehen), einen **Custom Agent** (Rolle im Prozess) und
**Gates** (deterministische Prüfungen in der Pipeline). Grundsatz: Was sich automatisch prüfen lässt, wird ein Gate.
Skills sind für Urteile und Entwürfe da.

| Team | Skills (Beispiele) | Custom Agent | MCP / Werkzeuge | Gate in der Pipeline |
| --- | --- | --- | --- | --- |
| Business Analyse | Anforderungserhebung, User Stories mit Akzeptanzkriterien (Gherkin), Fachglossar | `requirements-analyst` | Ticketsystem, Wiki | Definition of Ready (Pflichtfelder, Akzeptanzkriterien vorhanden) |
| Unternehmensarchitektur | ADRs, Technologie-Radar, Architekturprinzipien, Capability-Zuordnung | `architecture-reviewer` | Architektur-Repository (z. B. LeanIX), Tech-Radar | erlaubte Stacks und Abhängigkeiten (Policy as Code), Architekturtests |
| Integration | API-Design (OpenAPI, AsyncAPI), Event-Schemas, Integrationsmuster | `integration-designer` | API-Katalog, Schema-Registry | API-Linting (z. B. Spectral), Erkennung von Breaking Changes, Contract-Tests |
| Testing / QA | Teststrategie, Testgenerierung (Unit, Contract, E2E), Testdaten | `test-engineer` | Testmanagement, Testdaten-Service | Testabdeckung, E2E-Suite, Mutationstests für kritische Module |
| Security | Threat Modeling, Secure Coding, Umgang mit Secrets | `security-reviewer` | Schwachstellen-Datenbank | CodeQL, Dependency Review, Secret Scanning, Container-Scan |
| Plattform / Betrieb | Golden Paths, IaC-Module, Observability, Deployment | `platform-engineer` | Cloud-APIs, Monitoring | IaC-Scan, Policies für Cloud-Ressourcen, SBOM und Artefakt-Attestierung |

Die Teams arbeiten im InnerSource-Modell: Plugins liegen im eigenen Team-Repo, Releases erscheinen über die
Registry im Marketplace, Änderungen laufen per Pull Request mit CODEOWNERS.

## 6. Risikoklassen und Ownership

| Klasse | Beispiele | Wer darf starten | Zusätzliche Gates | Betrieb |
| --- | --- | --- | --- | --- |
| T0 Prototyp | Klick-Dummy, Auswertungsskript | alle | automatische Checks, nur Sandbox, Ablauf nach 90 Tagen | kein Produktivbetrieb |
| T1 Internes Werkzeug | Team-Tool ohne personenbezogene Daten | alle mit Sponsor | Review durch ein Entwicklungsteam, Security-Scans | Plattform-Standardbetrieb, benanntes Owner-Team |
| T2 Geschäftsrelevant | Integrationen, personenbezogene Daten | Produktteams | Architektur- und Security-Freigabe, vollständige Tests | Produktteam mit Rufbereitschaft |
| T3 Kritisch | Kernsysteme, regulierte Prozesse | Produktteams | alle Gates, Agent nur mit enger Aufgabenstellung | Produktteam, erweiterte Kontrollen |

Die Risikoklasse steht als Custom Property am Repo. Rulesets und Deployment-Regeln lesen sie aus.

## 7. Konkretes Setup mit GitHub Copilot

### Enterprise und Organisation

1. Copilot Business oder Enterprise für alle, die Agenten anstoßen. Kosten entstehen zusätzlich über Premium
   Requests und Actions-Minuten des Cloud Agents.
2. Enterprise-Policies: Cloud Agent, MCP-Server, erlaubte Modelle, Third-Party-Agents (Agent HQ), Copilot Code
   Review. Zuerst nur für die Pilot-Organisation aktivieren.
3. Managed Settings aus [`config-examples/managed-settings.json`](../config-examples/managed-settings.json) ausrollen.
   Damit kommen Marketplace und Pflicht-Plugins automatisch zu allen Clients.
4. Im `.github-private`-Repo der Organisation: organisationsweite Custom Agents (`agents/*.agent.md`) und
   Custom Instructions.
5. Audit-Log-Streaming ins SIEM und Copilot-Metriken aktivieren.

### Golden-Path-Template-Repo

```text
app-template/
├── AGENTS.md                                 # Build, Test, Konventionen – liest jeder Agent
├── .github/
│   ├── copilot-instructions.md               # optional, kurz: verweist auf AGENTS.md
│   ├── instructions/*.instructions.md        # pfadbezogene Regeln (applyTo), z. B. für Tests oder IaC
│   ├── agents/*.agent.md                     # repo-spezifische Custom Agents (falls nötig)
│   ├── copilot/settings.json                 # Plugins aus dem Marketplace für Copilot CLI und Cloud Agent
│   ├── ISSUE_TEMPLATE/feature.yml            # strukturierte Anforderung (Ziel, Nutzer, Akzeptanzkriterien)
│   └── workflows/
│       ├── copilot-setup-steps.yml           # Umgebung des Cloud Agents (Tools, Abhängigkeiten, Testdaten)
│       ├── ci.yml                            # ruft zentrale Reusable Workflows auf
│       └── cd.yml                            # Deployment über Environments mit Freigaben
├── .devcontainer/                            # gleiche Umgebung für Menschen und Agenten
├── docs/adr/                                 # Architekturentscheidungen
├── specs/                                    # spec.md, plan.md, tasks.md je Feature
└── infra/                                    # IaC aus den Modulen der Plattform
```

MCP-Server für den Cloud Agent werden in den Repo-Einstellungen hinterlegt oder in der Frontmatter eines Custom
Agents definiert. Secrets dafür kommen aus dem Environment `copilot`.

### Beispiel: Custom Agent der Business Analyse

```markdown
---
name: requirements-analyst
description: Verfeinert eine Anforderung zu umsetzbaren User Stories mit Akzeptanzkriterien und Rückfragen.
tools: ["read", "search", "edit"]
---

Du bist Business Analyst. Arbeite nur an der Spezifikation, nicht am Code.

1. Lies das Issue und vorhandene Dateien unter `specs/`.
2. Nutze den Skill `user-story-refinement`.
3. Fehlen Informationen, stelle höchstens fünf konkrete Rückfragen als Kommentar.
4. Sonst schreibe `specs/<feature>/spec.md` und öffne einen Pull Request zur Freigabe.
```

Der Agent ist dünn, das Wissen steckt im Skill. Der Skill funktioniert damit auch in Claude Code, OpenCode und im
Teams-Bot.

### Beispiel: Agentischer Prozessschritt mit wählbarer Engine

Skizze für GitHub Agentic Workflows. Die Datei wird mit `gh aw compile` in einen normalen Actions-Workflow übersetzt.

```markdown
---
on:
  issues:
    types: [labeled]
engine: copilot          # Wechsel auf claude oder codex ohne weitere Änderungen
permissions:
  contents: read
  issues: read
safe-outputs:
  add-comment:
  add-labels:
    allowed: [factory:architecture, factory:needs-info]
---

# Anforderung verfeinern

Reagiere nur, wenn das Label `factory:refine` gesetzt wurde. Verfeinere die Anforderung mit dem Skill
`user-story-refinement`. Sind die Akzeptanzkriterien vollständig, setze `factory:architecture`.
Sonst setze `factory:needs-info` und stelle Rückfragen.
```

In der Praxis den Trigger zusätzlich auf das Label filtern, damit der Agent nicht bei jedem Label-Wechsel startet.

## 8. Vendor-Lock-in begrenzen

| Prinzip | Umsetzung |
| --- | --- |
| Wissen in offenen Formaten | `AGENTS.md`, `SKILL.md`, MCP, OpenAPI. Tool-spezifische Dateien nur als dünne Adapter. Dieser Marketplace erzeugt die Formate für Copilot und Claude Code aus einer Quelle. |
| Prozess außerhalb des Agenten | Zustände in Issues und Labels, Logik in Workflows und Skripten. Agenten sind austauschbare Ausführende. |
| Eine Schnittstelle zum Agenten | Agentic Workflows mit `engine:` oder ein eigener Reusable Workflow `run-agent.yml`. Eine neue Engine braucht nur einen neuen Adapter. |
| Modellzugang über Gateway | Eigene Agenten (Intake-Bot, Fach-Agenten) sprechen Modelle über ein LLM-Gateway an (z. B. LiteLLM oder ein API-Management-Gateway). Modellwechsel ist dann Konfiguration. |
| Dünner Chat-Adapter | Der Teams-Bot erzeugt nur Issues und spiegelt den Status. Slack oder ein Portal sind weitere Adapter. |
| Ausstieg regelmäßig üben | Referenzaufgaben laufen quartalsweise mit einer zweiten Engine und einem zweiten Modell. Ergebnisse fließen in die Skill-Evals. |
| Logik portabel halten | Pipeline-Schritte als Skripte oder Container, Actions nur als Hülle. Das erleichtert einen Wechsel der CI-Plattform. |
| Verträge | EU-Datenverarbeitung, kein Training auf eigenen Daten, Exportrechte für Logs und Metriken. |

GitHub selbst bleibt eine bewusste Plattformentscheidung. Diese Bindung ist akzeptabel, weil Code, Issues und
Workflows exportierbar sind und Git als Format offen ist.

## 9. Sicherheit und Governance

- **Prompt Injection ernst nehmen.** Wenn „jeder“ Anforderungen einreichen kann, liest der Agent nicht
  vertrauenswürdigen Text. Deshalb: wenige Werkzeuge je Agent, Schreibzugriffe nur über Safe Outputs bzw. Pull
  Requests, keine Produktions-Secrets in der Agent-Umgebung, Firewall-Allowlist.
- **Identitäten:** GitHub Apps statt persönlicher Tokens, OIDC statt langlebiger Cloud-Secrets, minimale Rechte.
- **Unabhängiges Review:** Wer einen Agenten beauftragt, gibt dessen Pull Request nicht selbst frei. Durchsetzen über
  Rulesets und CODEOWNERS.
- **Nachvollziehbarkeit:** Agenten-PRs sind gekennzeichnet, Spezifikation und Entscheidung liegen im Repo, das
  Audit-Log geht ins SIEM.
- **Lieferkette:** SBOM, Artefakt-Attestierung, Dependency Review und Code-Referenz-Filter für generierten Code.

## 10. Kennzahlen

| Kennzahl | Zweck |
| --- | --- |
| Durchlaufzeit Idee bis Produktion | Wirkung der Factory insgesamt |
| Anteil gemergter Agenten-PRs, Nacharbeit je PR | Qualität von Skills, Spezifikationen und Agenten |
| Review-Dauer und offene Agenten-PRs | Engpass Review erkennen (Agenten schreiben schneller, als Menschen prüfen) |
| Change Failure Rate, entkommene Fehler | Wirksamkeit der Gates |
| Kosten je gemergtem PR | Wirtschaftlichkeit, Vergleich der Engines |
| Nutzung je Skill, Eval-Ergebnisse | Wirkung der Beiträge der Fachteams |

Kennzahlen auf Team- und Prozessebene auswerten, nicht auf Personenebene. Das mit dem Betriebsrat vereinbaren.

## 11. Die nächsten 90 Tage

1. Factory-Team und Sponsor benennen, Betriebsrat und Datenschutz einbinden.
2. Auf dem eigenen Tenant prüfen: Cloud Agent, GHEC-App für Teams, Agent HQ (Third-Party-Agents),
   GitHub Agentic Workflows, Copilot-Metriken.
3. Marketplace produktiv nehmen, Managed Settings für eine Testgruppe ausrollen.
4. Ein Golden-Path-Template für den häufigsten Stack bauen, inklusive `AGENTS.md` und `copilot-setup-steps.yml`.
5. Jedes Fachteam liefert einen ersten Skill mit Evals in den Marketplace.
6. Zwei Pilot-Teams starten mit „Issue an Agent zuweisen“. Prozesszustände und Labels für Phase 2 festlegen.
7. Ausgangswerte der Kennzahlen erheben.

## Quellen

- [Copilot coding agent in GitHub Enterprise Cloud with data residency (Changelog, 08/2025)](https://github.blog/changelog/2025-08-27-copilot-coding-agent-is-now-available-in-github-enterprise-cloud-with-data-residency/)
- [Integrating GitHub with Teams (GHEC-Doku, inkl. Data Residency)](https://docs.github.com/en/enterprise-cloud@latest/integrations/how-tos/teams/integrate-github-with-teams)
- [Shared agentic work with GitHub Copilot in Microsoft Teams (Changelog, 08/2026)](https://github.blog/changelog/2026-08-21-shared-agentic-work-with-github-copilot-in-microsoft-teams/)
- [About third-party coding agents (GitHub-Doku)](https://docs.github.com/en/copilot/concepts/agents/about-third-party-coding-agents)
- [Claude and Codex now available for Copilot Business & Pro users (Changelog, 02/2026)](https://github.blog/changelog/2026-02-26-claude-and-codex-now-available-for-copilot-business-pro-users/)
- [About custom agents (GitHub-Doku)](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-custom-agents)
- [GitHub Agentic Workflows (technische Vorschau, Changelog 02/2026)](https://github.blog/changelog/2026-02-13-github-agentic-workflows-are-now-in-technical-preview/) und [Engines](https://github.github.com/gh-aw/reference/engines/)
- [Copilot SDK GA (Changelog, 06/2026)](https://github.blog/changelog/2026-06-02-copilot-sdk-is-now-generally-available/)
- [Codex Cloud: Support für GHE.com (offenes Issue)](https://github.com/openai/codex/issues/12691)
- [Agentic AI Foundation: MCP, AGENTS.md, goose](https://www.prnewswire.com/news-releases/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation-aaif-anchored-by-new-project-contributions-including-model-context-protocol-mcp-goose-and-agentsmd-302636897.html)
- [Agent Skills (offener Standard)](https://agentskills.io)
