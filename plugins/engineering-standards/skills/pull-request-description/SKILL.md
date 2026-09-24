---
name: pull-request-description
description: Erstellt Pull-Request-Beschreibungen nach der hausweiten Vorlage (Kontext, Änderungen, Tests, Risiken). Verwenden, wenn ein Pull Request erstellt oder beschrieben werden soll.
---

# Pull-Request-Beschreibung

Gliedere jede PR-Beschreibung in genau diese Abschnitte:

## Kontext
Warum ist die Änderung nötig? Verlinke Ticket oder Issue.

## Änderungen
Stichpunkte, was sich geändert hat – aus Sicht von Reviewer:innen, nicht als Datei-Liste.

## Tests
Wie wurde die Änderung geprüft (automatisierte Tests, manuelle Schritte)?

## Risiken und Rollback
Was kann schiefgehen, wie wird zurückgerollt? Bei Datenbank-Migrationen immer ausfüllen.

Halte die Beschreibung knapp. Wiederhole nicht den Diff.
