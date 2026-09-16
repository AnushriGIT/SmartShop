# Phase 4a — Streamlit UI Implementation Plan

**Status:** ✅ Implemented and verified (2026-09-16) — 25/25 contract tests passing (7 client, 10 components, 8 pages), 141/141 in the full fast suite (zero regressions), plus real end-to-end verification (real `uvicorn` + `AppTest`-driven interactions against the live server, real OpenAI API) covering the chat assistant, review summaries, and recommendations with form widgets.
**Governing spec:** [smartshop-coordinator-agent-spec.md](smartshop-coordinator-agent-spec.md) Section 13 (Phase 4 row), Section 8 (Cognitive Features — streaming's trigger condition); `specs/smartshop-project-requirements.md` Section 7 (UI Requirements — the 5 required workflows), Section 10 (Week 7 delivery slot).
**Precedes:** Phase 4b (backend hardening — rate limiting, caching, cost/telemetry monitoring), a separate plan not yet drafted. Split confirmed with the user: 2 plans, UI first.
**Test generation log:** [.agents/memory-bank/testGenerationLog.md](../../.agents/memory-bank/testGenerationLog.md) (`v10` entry)

## Implementation Notes (added post-implementation)

- **Built exactly as designed** — no architecture changes during implementation. All findings below were test-tooling discoveries, not design flaws.
- **`AppTest.from_file`'s relative-path resolution is against the *calling* file's directory, not the cwd** — `AppTest.from_file("app/ui/streamlit_app.py")` called from `tests/ui/test_pages.py` resolved to `tests/ui/app/ui/streamlit_app.py` and failed with `FileNotFoundError`. Caught immediately by running the tests (Rule 9), not assumed from the docstring. Fixed with a small `_app_test()` helper building absolute paths from the project root.
- **`st.write(str)` renders as a `Markdown` element in `AppTest`, not a separate `Text` element** — an initial assumption (`at.text[0].value`) was wrong; verified by running the test and reading the actual `ElementList` contents, not by reading Streamlit's source. Fixed to assert against `at.markdown[-1].value` instead.
- **A stray, unrelated `uvicorn` process was already listening on port 8000** (a different project's server, running since 2026-08-22, unrelated Python install) — discovered while running the first real-verification smoke test, when a health check against the default port succeeded suspiciously easily. Not touched (not this session's process to kill); the real verification instead used an explicit non-default port (8123, matching Phase 3b's own smoke-test convention) so results couldn't be confused with that unrelated server.
- **Real end-to-end verification needed a longer `AppTest` timeout than the 3s default** — a genuine OpenAI round-trip through the full stack (Streamlit → `httpx` → FastAPI → `handle_query` → coordinator → sub-agent) legitimately takes longer than 3 seconds; the mocked contract-test suite never hits this since `FakeClient` returns instantly. Used `at.run(timeout=30)` for the real checks only — no code change, this was purely a verification-script detail.
- One already-known, unrelated residual behavior surfaced again during real verification (not a new bug, not investigated further): `review_summary_agent` occasionally still classifies `SP0001`'s 2 borderline reviews (3.5/5, 4.5/5) as `sentiment="mixed"` — the same non-100%-eliminated LLM non-determinism already documented in the Phase 3a Part 2 implementation plan's own notes.

## Context

Phase 4 ("Production Readiness" — spec Section 13) bundles UI work, streaming, and backend hardening (rate limiting, caching, cost/telemetry monitoring) into one row. Per your scoping decision, this splits into **2 plans, UI first**: this plan (Phase 4a) covers the UI; a separate Phase 4b plan (backend hardening — rate limiting, caching, cost/telemetry logging) comes after, not built now.

`smartshop-project-requirements.md` Section 7 requires "modular navigation" for 5 workflows: product recommendations/search, product comparison, review summaries/sentiment, policy/FAQ assistant, and a conversational shopping assistant — "usable workflows rather than only a marketing or explanatory screen." Section 10's Week 7 slot names this explicitly.

Verified via Explore agent (2026-09-16): `streamlit==1.63.0` is already in `requirements.txt` (unpinned) with zero existing UI code anywhere in the repo — genuinely greenfield. `streamlit.testing.v1.AppTest` (headless test harness, no browser needed) is available in this version — confirmed importable.

**Architecture decision**: the UI calls `app/api/`'s `POST /query`/`GET /health` over HTTP (via `httpx`, already transitively installed, now made a direct dependency) — it does **not** import `app.agents`/`app.api` in-process. That's the entire reason Phase 3b built an API layer; bypassing it here would duplicate the singleton-building logic and defeat its purpose. Running the full stack means 2 processes: `uvicorn app.api.main:app` and `streamlit run app/ui/streamlit_app.py`.

**Git scope (confirmed with you):** unlike `app/api/`, this has no import coupling to the untracked `app/agents/` — `app/ui/` and `tests/ui/` will be tracked and pushed once built.

---

## Design

### Module layout — Streamlit's own multi-page convention, satisfying "modular navigation" directly

```
app/ui/
├── streamlit_app.py   # Entry point AND the "conversational shopping assistant" workflow (st.chat_input/st.chat_message)
├── client.py           # SmartshopAPIClient — thin httpx.Client wrapper: query(text), health()
├── components.py       # render_coordinator_response(data: dict) — one dispatcher for all 7 response shapes
└── pages/
    ├── 1_🎯_Recommendations.py
    ├── 2_⚖️_Compare_Products.py
    ├── 3_⭐_Review_Summaries.py
    └── 4_📋_Policy_FAQ.py
```

Streamlit auto-generates sidebar nav from `pages/` — the conversational assistant (most general workflow) is the natural entry point; the other 4 are targeted forms that still compose a natural-language query and hit the *same* `POST /query` (there's only one query endpoint — no dedicated per-sub-agent route was built in Phase 3b, matching the spec's singular "a customer query endpoint").

### Response rendering — dispatch by shape, since the client only ever sees JSON

`CoordinatorResponse` is a 7-member union with no discriminator field; `components.py::render_coordinator_response` dispatches on which keys are present (`sentiment` → review summary, `rationale` → recommendation, `differences` → comparison, `policy`/`answer` → policy, `question` only → clarification, `message` only → fallback, `error` → error envelope — each of the 7 shapes is unambiguous by its field signature). One shared function, not one per page, so all 5 workflows render a given response type identically.

### Conversational history is client-side display only — not agent memory

`st.session_state.messages` keeps a growing transcript for the chat UI's own continuity; each turn still calls the stateless `handle_query()` with no prior-turn context passed (spec Section 5 already marks long-term/multi-turn memory out of scope). This is a UI convenience, not a new backend capability — stated explicitly in the code comment where the session state is built, so it's not mistaken for real conversation memory later.

### Error handling

`client.py` catches `httpx.ConnectError` (backend not running) and non-2xx responses, raising one clear exception type the UI layer catches and renders as a friendly banner — never a raw traceback. A small sidebar health indicator (`GET /health`) shows backend connectivity at a glance.

### Tests — `tests/ui/`, same mocking policy as everywhere else

```
tests/ui/
├── conftest.py         # monkeypatches SmartshopAPIClient so no real HTTP call happens
├── test_client.py      # connection-error and non-2xx handling
├── test_components.py  # render_coordinator_response dispatches correctly for all 7 shapes
└── test_pages.py       # AppTest-based: each page loads without exception; submitting triggers the (mocked) client call; response renders
```

Uses `streamlit.testing.v1.AppTest` — runs each page script headlessly, no browser, fits the existing default fast suite (no new pytest marker).

### Manual real end-to-end verification (Rule 9 — not a permanent automated suite)

Start both processes for real (`uvicorn app.api.main:app`, `streamlit run app/ui/streamlit_app.py`) and exercise all 5 workflows with real queries against the real OpenAI API — same reasoning as Phase 3b's manual `curl` check: a permanent `eval`-marked UI suite would just add another hop on top of what `tests/agents/eval`/`tests/api` already cover, for no real additional coverage.

---

## Files

```
app/ui/streamlit_app.py
app/ui/client.py
app/ui/components.py
app/ui/pages/1_🎯_Recommendations.py
app/ui/pages/2_⚖️_Compare_Products.py
app/ui/pages/3_⭐_Review_Summaries.py
app/ui/pages/4_📋_Policy_FAQ.py
tests/ui/conftest.py
tests/ui/test_client.py
tests/ui/test_components.py
tests/ui/test_pages.py
requirements.txt      # add httpx as an explicit direct dependency (already transitively installed)
```
No new pytest marker. `app/ui/`/`tests/ui/` are **not** added to `.gitignore` — tracked per the confirmed scope.

---

## Verification

```bash
# Fast suite includes the new UI tests, still no real API calls
.venv/bin/python -m pytest -q -m "not integration and not eval"

# Real manual smoke test — 2 processes
uvicorn app.api.main:app --reload &
streamlit run app/ui/streamlit_app.py
# exercise all 5 workflows with real queries in the browser
```

---

## After implementation — update in place (established convention)

- `smartshop-coordinator-agent-spec.md`: Section 13's Phase 4 row → UI portion ✅; Section 8's streaming row stays "Phase 4" but now genuinely triggerable (a UI exists) — note this explicitly rather than silently leaving it stale; Appendix A gains rows for the HTTP-client-not-in-process and response-dispatch-by-shape decisions.
- `.agents/memory-bank/testGenerationLog.md`: append a `v10` entry.
- `Reference/Learning/coordinator-agent/`: add a "UI Layer" section to the reference doc and a 5th diagram (Browser → Streamlit → FastAPI → `handle_query`) to the sequence-flow artifact.
- `git add`/commit/push `app/ui/`, `tests/ui/`, and `requirements.txt` — all tracked per the confirmed scope.

## Out of scope

**Streaming responses (SSE/WebSocket)** — Section 8's trigger condition ("a UI consumes this agent directly") becomes technically true once this ships, but actually building streaming is a separate, materially different technical concern (a streaming endpoint + a streaming-aware widget) — not needed for a functional UI, and not bundled into this plan; revisit as its own follow-up if response latency turns out to warrant it. Backend hardening (rate limiting, caching, cost/telemetry, circuit breaker) — Phase 4b, separate plan. Any change to `app/agents/`/`app/api/` themselves — this plan only adds a new client of the existing `POST /query`, nothing about the backend changes. Multi-turn agent memory — explicitly out of scope per spec Section 5; the chat UI's history is display-only.
