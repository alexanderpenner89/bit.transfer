# OpenAlex Query Prompt Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite `_build_user_prompt` in `OrchestratorAgent` to force recipe-style query construction and a mandatory self-check step, so generated boolean queries consistently use wildcards, proximity operators, and synonym clustering.

**Architecture:** Single method rewrite in `backend/agents/orchestrator.py`. The Chain-of-Thought gains a per-query construction recipe (steps 2–3) and a new self-verification step (step 4) that forces the LLM to review and fix any non-compliant query before returning output. No schema, skill, or test changes needed.

**Tech Stack:** Python, pydantic-ai, OpenAlex Elasticsearch query syntax

---

### Task 1: Add test asserting user prompt contains recipe structure

**Files:**
- Modify: `backend/tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `TestSystemPrompt` class in `backend/tests/test_orchestrator.py`:

```python
def test_user_prompt_contains_recipe_instructions(self, maurer_profil):
    orchestrator = OrchestratorAgent()
    prompt = orchestrator._build_user_prompt(maurer_profil)
    assert "Synonym-Cluster" in prompt or "Cluster" in prompt
    assert "Wildcard" in prompt or "*" in prompt
    assert "Proximity" in prompt or "~" in prompt
    assert "Selbstprüfung" in prompt or "Selbst" in prompt
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_orchestrator.py::TestSystemPrompt::test_user_prompt_contains_recipe_instructions -v
```

Expected: `FAILED` — current prompt lacks these elements.

---

### Task 2: Rewrite `_build_user_prompt` with recipe CoT + self-check

**Files:**
- Modify: `backend/agents/orchestrator.py` — `_build_user_prompt` method only

**Step 1: Replace the method body**

Replace the `return f"""..."""` block in `_build_user_prompt` with:

```python
return f"""Analysiere das folgende Handwerksgewerk und generiere eine präzise OpenAlex-Suchstrategie.

**Gewerk:** {profil.gewerk_name} (ID: {profil.gewerk_id}, HWO-Anlage: {profil.hwo_anlage})

**Kernkompetenzen:** {kernkompetenzen}

**Techniken:** {techniken}

**Werkstoffe:** {werkstoffe}

**Software/Digitale Werkzeuge:** {software}

**Aufgabe (Chain-of-Thought):**

Schritt 1 – Semantic Queries (EN):
  Formuliere 1–2 englische Absätze (50–100 Wörter). Kein Boolean. Akademisches Vokabular.

Schritt 2 – Deutsche Boolean-Queries (2–3 Stück):
  Für jede Query:
    a) Wähle ein zentrales Konzept (Werkstoff, Technik oder Anwendungsfeld).
    b) Baue einen Synonym-Cluster: ("Begriff A" OR "Begriff B" OR Stamm*).
    c) Verbinde maximal 2 Cluster mit AND.
    d) Setze gezielt Wildcards (mind. 3 Zeichen vor *) ODER einen Proximity-Operator (~3).
  Beispiel: ("Mauerwerk" OR "Ziegel" OR Mauer*) AND ("Mörtel Verarbeitung"~3)

Schritt 3 – Englische Boolean-Queries (2–3 Stück):
  Gleiche Rezeptur wie Schritt 2, auf Englisch.
  Beispiel: ("masonry" OR "brickwork" OR mason*) AND ("mortar application"~3)

Schritt 4 – Selbstprüfung (PFLICHT, vor dem finalen Output):
  Prüfe jede boolean Query gegen diese Checkliste:
  ✓ Operatoren UPPERCASE (AND, OR, NOT)?
  ✓ Synonyme in runden Klammern gruppiert?
  ✓ Mindestens ein Wildcard (*) oder Proximity-Operator (~N) enthalten?
  ✓ Maximal 2–3 AND-verbundene Cluster?
  Wenn eine Prüfung fehlschlägt → überarbeite die Query jetzt, bevor du antwortest.

Lade den Skill 'openalex-query-generation' für weitere Syntaxregeln.
Antworte NUR mit dem strukturierten SearchStrategyModel-Output."""
```

**Step 2: Run the new test**

```bash
uv run pytest tests/test_orchestrator.py::TestSystemPrompt::test_user_prompt_contains_recipe_instructions -v
```

Expected: `PASSED`

**Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All previous tests pass + new test green. Only the pre-existing `test_cli.py` failure (Langfuse env missing) is acceptable.

**Step 4: Commit**

```bash
git add backend/agents/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: prescriptive CoT recipe + self-check for OpenAlex query generation"
```
