---
name: conventional-commits
description: Formuliert Commit-Messages nach der hausweiten Conventional-Commits-Konvention. Verwenden, wenn ein Commit erstellt oder eine Commit-Message vorgeschlagen werden soll.
---

# Commit-Messages nach Conventional Commits

Format:

```
<type>(<scope>): <kurze Zusammenfassung im Imperativ>

<optionaler Body: Was und warum, nicht wie>

<optionaler Footer: BREAKING CHANGE: …, Refs: TICKET-123>
```

Regeln:

1. `type` ist einer von `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `perf`.
2. `scope` ist der betroffene Service oder das Modul in Kleinbuchstaben, z. B. `billing-api`.
3. Die Zusammenfassung hat höchstens 72 Zeichen und endet ohne Punkt.
4. Ticket-Referenzen stehen im Footer als `Refs: <TICKET-ID>`.
5. Breaking Changes werden mit `!` nach dem Typ **und** einem `BREAKING CHANGE:`-Footer markiert.

Beispiel:

```
fix(billing-api): Rundungsfehler bei Teilbeträgen beheben

Beträge wurden vor der Währungsumrechnung gerundet, dadurch
entstanden Differenzen im Cent-Bereich.

Refs: BILL-482
```
