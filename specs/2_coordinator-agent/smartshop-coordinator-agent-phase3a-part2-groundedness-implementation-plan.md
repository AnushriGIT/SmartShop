# Phase 3a Part 2 — Groundedness Evaluation Implementation Plan

**Status:** 📋 Approved, not yet implemented (2026-09-14)
**Governing spec:** [smartshop-coordinator-agent-phase3a-part2-groundedness-spec.md](smartshop-coordinator-agent-phase3a-part2-groundedness-spec.md) (the BDD spec this plan implements) and [smartshop-coordinator-agent-spec.md](smartshop-coordinator-agent-spec.md) Section 12/Appendix A (the evaluation-strategy analysis both derive from)
**Extends:** The Phase 3a eval harness (`tests/agents/eval/`) — additional assertions on the existing golden Q&A cases, not a parallel eval set
**Test generation log:** [.agents/memory-bank/testGenerationLog.md](../../.agents/memory-bank/testGenerationLog.md) (will land as the `v7` entry)

## Context

`specs/2_coordinator-agent/smartshop-coordinator-agent-phase3a-part2-groundedness-spec.md` (drafted and approved earlier this session) is the BDD spec this plan implements. It resolves the one gap the governing spec's Section 12 evaluation-strategy analysis found: every sub-agent's *structured* response fields are hallucination-proof by construction (the reference-only output pattern), but the **free-text fields** — `ReviewSummaryResponse.summary`, `RecommendationResponse.rationale`, `ComparisonResponse.differences`, `PolicyResponse.answer` — are LLM-synthesized prose nothing currently checks against the real source records the sub-agent was shown. Correctness/Relevance/Retrieval-relevance were evaluated and rejected as redundant or inapplicable (Appendix A); only Groundedness is being added, and it's added as extra assertions on the 6 existing golden Q&A cases, not a parallel eval set.

**Real bug discovered while re-verifying current state for this plan (Rule 9 — verify against reality):** `tests/agents/eval/conftest.py` is currently corrupted — its first two lines are `-+` and `+ ` before the module docstring, which is invalid Python syntax (`ast.parse` confirms a `SyntaxError`). This breaks pytest collection for the **entire** `tests/agents/eval/` package, not just the new groundedness work — none of the existing 7 eval tests can currently run. The rest of the file (from the docstring onward) is intact and matches what was verified working earlier this session, so this is fixed by simply removing those two garbage lines, not by rebuilding the fixtures. This is step 1 of implementation, a prerequisite unrelated to the groundedness feature itself.

---

## Design

**One shared judge, module-local, same idiom as every other agent** (`app/agents/review_agent.py` etc. — a `build_*_agent()` returning an `Agent[None, <output type>]`, `openai:gpt-4o-mini` default matching every other sub-agent's default rather than switching models). Lives in `tests/agents/eval/groundedness.py`, not `app/agents/` — it's an evaluation tool, never called from a production dispatch path.

```python
class GroundednessGrade(SmartshopModel):
    explanation: str
    grounded: bool

def build_groundedness_judge(model=...) -> Agent[None, GroundednessGrade]: ...

async def judge_groundedness(agent, facts: str, answer: str) -> GroundednessGrade: ...
```

`judge_groundedness` calls the agent via `app.agents.retry.call_with_retry` (same retry-with-backoff wrapper every other real-API call in this codebase uses, per Rule 12) with a prompt containing `facts` (the real source text the sub-agent was actually shown) and `answer` (the specific free-text field being checked), and a system prompt instructing the model to judge whether `answer` contains any claim not supported by `facts`.

**Extends the 6 existing golden Q&A cases — no parallel case list.** Each test in `test_golden_qa.py` gains one additional assertion using data it already has:

| Case | Free-text field | `facts` built from |
| :--- | :--- | :--- |
| `test_review_summary_for_a_known_product` | `response.summary` | `reviews_for_product(eval_catalog, REVIEW_PRODUCT_ID)` (`app.agents.data`) |
| `test_recommendation_for_a_cheap_speaker_resolves_the_plural_category` | `response.rationale` | `response.products`' real name/category/price/description |
| `test_recommendation_respects_a_max_price_filter` | `response.rationale` | `response.products`' real name/category/price/description |
| `test_comparison_of_two_known_products` | `"; ".join(response.differences)` | `products_by_ids(eval_catalog, COMPARE_PRODUCT_IDS)`'s full real fields |
| `test_policy_faq_laptop_return_timeframe_matches_the_catalog` | `response.answer` | `response.policy`'s real description/conditions/timeframe (already resolved by the existing assertions) |
| `test_policy_faq_warranty_question_answers_from_the_matching_policy` | `response.answer` | `response.policy`'s real fields — **guarded**: only checked `if response.policy is not None`, per the spec's "no matched policy" scenario |

New session-scoped `eval_groundedness_judge` fixture in `conftest.py`, built the same way as `eval_coordinator_agent` (`_require_api_key()` guard, built once).

No new pytest marker, no `pyproject.toml` change, no `app/` change — stays inside the existing `eval` marker (spec's explicit scope).

---

## Files

```
tests/agents/eval/conftest.py       # fix: drop the 2 corrupted lines; add eval_groundedness_judge fixture
tests/agents/eval/groundedness.py   # new: GroundednessGrade, build_groundedness_judge(), judge_groundedness()
tests/agents/eval/test_golden_qa.py # each of the 6 existing tests gains one groundedness assertion
```

---

## Verification

```bash
# Confirm the conftest.py fix first — collection alone must succeed
.venv/bin/python -c "import ast; ast.parse(open('tests/agents/eval/conftest.py').read())"

# Fast suite still unaffected (no app/ or non-eval test changes)
.venv/bin/python -m pytest -q -m "not integration and not eval"

# Real run — costs real OpenAI calls (6 sub-agent queries + up to 6 judge calls)
.venv/bin/python -m pytest tests/agents/eval -m eval -v

# Clean skip still works
OPENAI_API_KEY= .venv/bin/python -m pytest tests/agents/eval -m eval -v
```

Expect: all 6 golden Q&A tests pass both their existing structured-field assertions and the new groundedness assertion; the warranty case's groundedness check runs only when a policy was actually matched on that run.

---

## After implementation — update in place (established convention)

- This file's Status header → "✅ Implemented and verified", with an Implementation Notes section (the conftest.py corruption found/fixed, any real groundedness-judge behavior observed).
- `smartshop-coordinator-agent-phase3a-part2-groundedness-spec.md`: Status header → "✅ Implemented and verified".
- `smartshop-coordinator-agent-spec.md`: Section 12's "Phase 3a Part 2" bullet → ✅ implemented; the fixed corruption isn't a spec-level change, just mentioned in this plan's Implementation Notes.
- `.agents/memory-bank/testGenerationLog.md`: append a `v7` entry, same format as `v5`/`v6` (including the conftest.py bug as a Triage entry — a real defect caught, not a test-authoring one).
- `Reference/Learning/coordinator-agent/coordinator-agent-reference.md`: Section 7 "Evaluation Harness" gains a short groundedness mention.
- `git add`/commit/push only the trackable files per the existing policy: this implementation-plan file (and nothing else — `tests/agents/eval/`, the spec, and the reference doc all stay local-only).

## Out of scope (per the spec)

Relevance/Retrieval-relevance evaluators, a standalone Correctness LLM-judge, any production code path, and an aggregate groundedness percentage (6 named cases stay explicit, matching the existing golden Q&A style).
