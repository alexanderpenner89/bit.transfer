# Design: OpenAlex Query Prompt Optimization

**Date:** 2026-03-08
**Scope:** Purely prompt-engineering — no model, schema, or test changes

---

## Problem

The agent already knows OpenAlex syntax rules (system prompt + SKILL.md), but the Chain-of-Thought in `_build_user_prompt` only says "generate 2–3 queries". This open-ended instruction allows the LLM to produce generic AND/OR queries without wildcards or proximity operators.

## Approach

**Approach B: Prescriptive user prompt + self-verification step**

Two targeted changes to `_build_user_prompt` in `backend/agents/orchestrator.py`.

---

## Change 1 — Recipe-style query construction

Replace the open-ended query instruction with a per-query recipe for both German and English:

```
Schritt 2 – 2–3 deutsche Boolean-Queries:
  Für jede Query:
    a) Wähle ein zentrales Konzept (z.B. Werkstoff, Technik, Anwendungsfeld).
    b) Baue einen Synonym-Cluster: ("Begriff A" OR "Begriff B" OR Stamm*).
    c) Verbinde maximal 2 Cluster mit AND.
    d) Setze gezielt Wildcards (mind. 3 Zeichen vor *) ODER einen Proximity-Operator (~3).
```

Same recipe for English (Schritt 3).

## Change 2 — Mandatory self-check step (new CoT step 4)

```
Schritt 4 – Selbstprüfung (PFLICHT):
  Prüfe jede boolean Query:
  ✓ Operatoren UPPERCASE (AND, OR, NOT)?
  ✓ Synonyme in Klammern gruppiert?
  ✓ Mindestens ein Wildcard (*) oder Proximity (~N) pro Query?
  ✓ Maximal 2–3 AND-verbundene Cluster?
  Wenn eine Prüfung fehlschlägt → überarbeite die Query, bevor du antwortest.
```

---

## Files Changed

| File | Change |
|------|--------|
| `backend/agents/orchestrator.py` | Rewrite `_build_user_prompt` only |

## Files Unchanged

- `backend/agents/skills/openalex-query/SKILL.md`
- `backend/schemas/search_strategy.py`
- All test files

---

## Success Criteria

Generated boolean queries consistently contain at least one of:
- A wildcard (`Mauer*`, `mason*`)
- A proximity operator (`"term1 term2"~3`)
- Synonym clusters with OR in parentheses
