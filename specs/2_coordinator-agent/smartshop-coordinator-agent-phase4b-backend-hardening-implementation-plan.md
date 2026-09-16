# Phase 4b — Backend Hardening Implementation Plan

**Status:** 📋 Approved, not yet implemented (2026-09-16)
**Governing spec:** [smartshop-coordinator-agent-spec.md](smartshop-coordinator-agent-spec.md) Section 9 (Resiliency), Section 11 (Telemetry/Cost optimization strategy), Section 13 (Phase 4 row); `specs/smartshop-project-requirements.md` Section 8 (Reliability and Security Requirements).
**Precedes:** Nothing further planned yet within Phase 4 — this is the last named piece (4a shipped the UI, this is 4b).
**Test generation log:** [.agents/memory-bank/testGenerationLog.md](../../.agents/memory-bank/testGenerationLog.md) (will land as the `v11` entry)

## Context

Phase 4 splits into 2 plans (confirmed earlier): Phase 4a (UI) shipped; this is Phase 4b — the backend half named in spec Section 13's Phase 4 row: rate limiting, caching, cost/telemetry monitoring. Section 11's applicability analysis (2026-09-15) already concluded caching and continuous cost monitoring are the 2 real, applicable gaps; `smartshop-project-requirements.md` Section 8 separately requires "add rate limiting and abuse controls before public deployment" and "bound LLM calls by timeout, retry, token, and cost policies."

Verified via Explore agent (2026-09-16), 3 things change this plan's scope from what Section 13's row names:

1. **A real, confirmed gap beyond the named 3**: Section 9's own "Phase 1 minimum" — a 10s per-call timeout on every LLM call — was **never actually implemented**. `call_with_retry` only retries; nothing anywhere sets a timeout. Closing this belongs naturally in a "hardening" pass, the same way the earlier `review-fix-loop` pass closed Section 10's similarly promised-but-unbuilt sanitization gap.
2. **PydanticAI already gives real cost data for free**: `AgentRunResult.usage` (a property) returns a `RunUsage` with `input_tokens`/`output_tokens`/`total_tokens`/`requests`/`cost` (a best-effort USD figure via PydanticAI's own `genai-prices` integration) — no hand-rolled pricing table needed.
3. **No trace-ID requirement actually exists anywhere in either spec** (grepped both files for "trace id"/"correlation"/"link every hop" — zero matches; a misremembering from an earlier turn). Left out of this plan entirely rather than built speculatively.

No rate-limiting/caching library (`slowapi`, `cachetools`, `redis`, etc.) is installed. No numeric rate-limit target exists in either spec.

---

## Design

### 1. Timeout — close the confirmed Section 9 gap

Add `model_settings=ModelSettings(timeout=LLM_CALL_TIMEOUT_SECONDS)` to all 5 `build_*_agent()` functions (coordinator + 4 sub-agents) — the exact same `ModelSettings` mechanism `groundedness.py` already uses for `temperature=0`, just a different field. `LLM_CALL_TIMEOUT_SECONDS = 10.0` defined once in `app/agents/retry.py` (already the "Section 9 resiliency" module, alongside `TRANSIENT_OPENAI_ERRORS`) and imported into each builder.

### 2. Cost/token logging — one hook point covers every LLM call for free

`call_with_retry` already wraps every single LLM call in the codebase (coordinator + all 4 sub-agents + the eval groundedness judge). Add an optional `label: str | None = None` parameter; after a successful call, if the result exposes `.usage` (`getattr(result, "usage", None)` — keeps `call_with_retry` generic, not hard-coupled to PydanticAI's return shape), log one line: `llm_usage label=%s requests=%s input_tokens=%s output_tokens=%s total_tokens=%s cost_usd=%s retries=%s latency_seconds=%.3f`. Each of the 6 call sites passes its own `label` (`"coordinator"`, `"review_summary_agent"`, etc.) — this directly closes Section 11's named "Token cost per turn: Tracked, no target yet" gap, and costs nothing extra since `call_with_retry` already has the result and `RetryStats` in hand.

### 3. Caching — API-layer only, exact-match, TTL-based

Placed in `app/api/`, not `app/agents/` — caching is a "serving repeated HTTP requests" concern (the CLI is a fresh process per invocation; an in-memory cache wouldn't persist between calls anyway), so `handle_query()`'s signature and every existing caller (CLI, tests) stay untouched. New `app/api/cache.py`: a small dict-based `TTLCache` (`get`/`set`, expiry timestamps, simple oldest-first eviction past a max size — no new dependency, matches this project's established preference for hand-rolling simple utility logic over pulling in a library for something this small, e.g. `sanitize.py`). The `/query` route checks the cache keyed by `sanitize_query(request.query)` (the same normalized text `handle_query()` itself sanitizes to internally) before calling `handle_query`, and stores the result after. Exact-string-match only, consistent with Appendix B's existing "no vector semantic caching — not triggered by any measured problem" stance; not a new decision, just applying the existing one.

### 4. Rate limiting — hand-rolled, per-IP, `/query` only

New `app/api/rate_limit.py`: a fixed-window counter keyed by `request.client.host`, `SMARTSHOP_RATE_LIMIT_PER_MINUTE` (default `20`, env-var-overridable, matching the `SMARTSHOP_*` convention) requests per rolling minute. Applied as a FastAPI `Depends` on `POST /query` only — `GET /health` stays unthrottled so monitoring/the UI's sidebar indicator is never blocked. Over the limit → `429` with the existing `AgentErrorEnvelope` shape (`code="rate_limited"`), reusing `AgentError`/`AgentErrorEnvelope` rather than inventing a new error shape. Hand-rolled rather than adding `slowapi`: the actual logic needed (single-process, in-memory, fixed window) is small enough that a library adds a dependency without meaningfully reducing code — noted as the honest trade-off (a multi-process/distributed deployment would need `slowapi`+Redis or similar; out of scope, no such deployment target exists).

### 5. Circuit breaker — re-evaluated, still not building it

Section 9 explicitly deferred this "to Phase 4, pre-launch hardening" — this is that phase. Re-checked the trigger condition Appendix B already uses for the same call elsewhere ("not justified at single-process, no-concurrent-load scale") — nothing about that has changed; there's still no multi-instance deployment or real concurrent load. Recorded as an explicit re-evaluated Appendix A row (still not applicable) rather than silently skipped or speculatively built.

---

## Files

```
app/agents/retry.py          # LLM_CALL_TIMEOUT_SECONDS constant; call_with_retry gains `label` + usage logging
app/agents/coordinator.py    # build_coordinator_agent: model_settings timeout; call_with_retry(..., label="coordinator")
app/agents/review_agent.py           # same 2 changes
app/agents/recommendation_agent.py   # same 2 changes
app/agents/comparison_agent.py       # same 2 changes
app/agents/policy_faq_agent.py       # same 2 changes
app/api/cache.py             # new: TTLCache
app/api/rate_limit.py        # new: fixed-window limiter, check_rate_limit() Depends
app/api/routes.py            # /query: cache check + Depends(check_rate_limit)
.env.example                 # SMARTSHOP_RATE_LIMIT_PER_MINUTE, SMARTSHOP_CACHE_TTL_SECONDS
tests/agents/test_retry.py   # extend: label/usage logging, graceful no-.usage handling
tests/api/test_cache.py      # new
tests/api/test_rate_limit.py # new
tests/api/test_query.py      # extend: a repeated query hits the cache (handle_query called once)
```
No new dependency, no new pytest marker.

---

## Verification

```bash
# Fast suite includes the new/extended tests, still no real API calls
.venv/bin/python -m pytest -q -m "not integration and not eval"

# Real manual smoke test
uvicorn app.api.main:app --reload &
curl -s -X POST localhost:8000/query -H 'Content-Type: application/json' -d '{"query": "What do people say about SP0001?"}'
# repeat the same query — should return instantly (cache hit), confirm via server logs (no second llm_usage line)
for i in $(seq 1 25); do curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/query -H 'Content-Type: application/json' -d '{"query": "hi"}'; done
# expect some 429s once the per-minute limit is exceeded
```
Check the server's stdout for `llm_usage label=coordinator ...` / `llm_usage label=review_summary_agent ...` lines confirming real token/cost figures are captured.

---

## After implementation — update in place (established convention)

- `smartshop-coordinator-agent-spec.md`: Section 9's timeout row → ✅ implemented; circuit-breaker row gets the re-evaluation note; Section 11's metrics table → token cost per turn ✅ tracked; Section 13's Phase 4 row → fully ✅; 5 new Appendix A rows (timeout, cost-logging hook point, caching placement/key, rate-limit approach, circuit-breaker re-evaluation).
- `.agents/memory-bank/testGenerationLog.md`: append a `v11` entry.
- `Reference/Learning/coordinator-agent/`: extend Section 5 (API Layer) with the new rate-limit/cache/timeout/usage-logging behavior; no new diagram needed (these are cross-cutting additions to the existing request flow, not a new hop).
- `git add`/commit/push everything in Files above except `app/agents/*.py` (stays local-only, matches existing exclusion) — `app/api/cache.py`, `app/api/rate_limit.py`, `app/api/routes.py`, `tests/api/*`, `.env.example` are outside the excluded directories and get tracked.

## Out of scope

Trace/correlation IDs — no requirement exists for this, not built speculatively. Distributed/multi-process rate limiting or caching (Redis, `slowapi`) — no deployment target requiring it exists. A numeric SLA/latency target for "Total turn duration" — still no production load target per spec Section 1. `X-Forwarded-For`-aware client IP resolution for rate limiting — no reverse-proxy deployment exists yet. Any change to `app/ui/` — this plan is backend-only; the UI already handles a `SmartshopAPIError` (including a future 429) with its existing friendly-error path, no UI code change needed.
