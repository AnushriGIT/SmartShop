# Conversational Coordinator Agent Specification Template

## Overview
This template provides a reusable, full-maturity specification framework for a coordinator/orchestrator agent that routes conversational queries to specialized sub-agents. Use it for any project where a single entry-point agent must classify intent, dispatch to domain agents, and return a synthesized response.

**Write every section at full target maturity, even for an early-stage project.** Don't fork this into a per-phase or per-week file — fill in Section 13 (Roadmap) to say what's built now vs. later, and update the rest of the document *in place* as the project matures. A spec that accumulates `-v2`/`-phase2` copies is harder to trust than one authoritative document with an honest status column (this mirrors how `specs/1_data-pipeline/smartshop-implementation-guide.md` was updated in place as its own phases shipped, rather than split into new files).

### Required workflow
1. Fill in every `{{PLACEHOLDER}}` and `[bracket]` field before treating this as approved.
2. Resolve every row in Appendix A (Decision Log) — a spec with open decisions isn't ready to build from.
3. Get sign-off against Section 14 (Acceptance Criteria) *before* implementation starts — this is the approval gate, distinct from Section 15's post-build verification checklist.
4. As work progresses, update Section 13's status column in place. Do not create a new file per phase/week.

### Naming example
Template → `specs/{{project}}-coordinator-agent-spec.md`

---

## Table of Contents
1. Meta and Scope
2. Architecture Pattern Selection
3. Sub-Agent Registry & Tool Contract
4. Routing & Intent Classification
5. State Management & Memory Hierarchy
6. Schema Typing & Validation
7. Dependency Injection & Resource Lifecycle
8. Cognitive Features (Tier 2)
9. Resiliency & Graceful Degradation
10. Data Governance & Security
11. Telemetry, Tracing & Operational SLA
12. Required Test Suite & Evaluation
13. Roadmap / Phase Mapping
14. Acceptance Criteria (pre-build gate)
15. Production Verification Checklist (post-build gate)
16. Appendix A: Decision Log
17. Appendix B: Out-of-Scope / Non-Goals

---

## 1. Meta and Scope

| Field | Value |
| :--- | :--- |
| Document Version | `{{MAJOR.MINOR.PATCH}}` |
| System ID / Code Name | `{{e.g. ORCH-COORD-PROD}}` |
| Lead System Architect | `{{Name / Title}}` |
| Runtime Target | `{{e.g. Python 3.11+, PydanticAI}}` |
| Deployment Topology | `{{e.g. local dev, ECS Fargate, Cloud Run}}` |
| LLM Provider(s) + Model(s) | `{{e.g. OpenAI gpt-4o-mini, fallback: none yet}}` |

### Required discovery before implementation
- What domains/sub-agents exist at launch, and which are planned but not yet built?
- What is the expected query volume (QPS) and acceptable end-to-end latency?
- Does an evaluation dataset already exist, or does one need to be authored (see Section 12)?
- Is this agent reachable only in-process/CLI today, or does it sit behind an API (FastAPI, etc.)? If the API doesn't exist yet, say so explicitly rather than assuming it.

---

## 2. Architecture Pattern Selection

Select and justify one operational pattern:

| Pattern | Characteristics | Best for |
| :--- | :--- | :--- |
| **A. Pure Semantic Router** | Single-turn intent classification, zero local computation, direct handoff to a leaf agent | High-throughput, stateless Q&A |
| **B. Supervisor / Orchestrator (Hierarchical)** | Dispatches to multiple worker agents, evaluates outputs, synthesizes final response | Composite requests spanning >1 domain |
| **C. ReAct / Dynamic Planner Loop** | Chain-of-thought + scratchpad to plan step-by-step tool use | Open-ended diagnostic/multi-step paths |

**Selected pattern**: `{{A / B / C}}`
**Justification**: `{{why this pattern fits the product requirement, not just architectural preference}}`

---

## 3. Sub-Agent Registry & Tool Contract

Every sub-agent the coordinator can dispatch to must be declared here **before** Section 4's routing logic can be implemented — this is what the coordinator classifies against.

| Sub-agent | Trigger intents / example queries | Input schema | Output schema | Data/tools it owns |
| :--- | :--- | :--- | :--- | :--- |
| `{{sub_agent_name}}` | `{{e.g. "summarize reviews for X"}}` | `{{PydanticModel}}` | `{{PydanticModel}}` | `{{e.g. reviews.csv}}` |

**Tool-calling convention**: `{{e.g. PydanticAI @agent.tool, function name = sub-agent name, docstring = routing description}}`

---

## 4. Routing & Intent Classification

**Probabilistic/semantic routing only** — reject hardcoded string/keyword matching. Routing must use LLM function-calling, structured-output classification, or vector similarity against the Sub-Agent Registry (Section 3).

**Confidence source**: `{{how is C computed? e.g. a `confidence: float` field the coordinator's structured output is required to populate; or cosine similarity to an intent-bank embedding; or logprob of the selected tool call}}` — this must be answered concretely; "the LLM decides" is not an implementation.

| Confidence range (`C`) | Route action | Default threshold |
| :--- | :--- | :--- |
| `C ≥ τ_exec` | Direct sub-agent dispatch | `{{0.75}}` |
| `τ_clarify ≤ C < τ_exec` | Clarification / disambiguation turn | `{{0.50}}` – `{{0.75}}` |
| `C < τ_clarify` | Global fallback / human escalation | `< {{0.50}}` |

Log every routing decision (chosen sub-agent, `C`, and the action taken) — this is the input to Section 12's routing-accuracy evaluation.

---

## 5. State Management & Memory Hierarchy

- **Session identity**: `{{how is a session keyed? e.g. session_id per conversation, tied to a customer_id if authenticated}}`
- **Context decoupling**: short-term session state (ephemeral tool scratchpads) must stay isolated from long-term memory (customer profile, order history).
- **Token sliding window**: `{{FIFO eviction / summarization buffer — specify the strategy and the trigger (e.g. token count > N)}}`

---

## 6. Schema Typing & Validation

- Incoming requests and outgoing responses (including every sub-agent's I/O from Section 3) must validate against strict schemas (Pydantic v2 or equivalent).
- On a schema/contract violation, return an explicit JSON error envelope — never an unhandled 500/stack trace.

**Error envelope shape**: `{{e.g. {"error": {"code": str, "message": str, "sub_agent": str | None}}}}`

---

## 7. Dependency Injection & Resource Lifecycle

Long-lived resources — DB pools, HTTP clients, LLM client instances — must be instantiated once at startup and injected into route/agent calls, never re-instantiated per request.

**Singleton resources for this project**: `{{list them, e.g. asyncpg pool, OpenAI client}}`

---

## 8. Cognitive Features (Tier 2 — build when the product requirement justifies it, not by default)

| Feature | What it does | Trigger to build it |
| :--- | :--- | :--- |
| Scatter-Gather / Fan-Out | Decompose a multi-intent query, dispatch to N sub-agents via `asyncio.gather`, synthesize one response | A real query in the eval set (Section 12) needs >1 sub-agent to answer |
| Vector Semantic Cache | Skip LLM generation for near-duplicate queries via embedding-distance cache | Measured LLM cost/latency becomes a problem |
| Human-in-the-Loop (HITL) Intercept | Escalate to a human queue on low confidence or negative sentiment | Product requires a human fallback path |
| Streaming (SSE/WebSocket) | Progressive token streaming with status markers | A UI consumes this agent directly (needs an API layer first — see Section 1) |

---

## 9. Resiliency & Graceful Degradation

```
Coordinator Request ──► [Circuit Breaker: CLOSED] ──► Sub-Agent Execution
                              │
                              ├─► (Failures > {{N}} in {{window}})
                              ▼
                      [Circuit Breaker: OPEN]
                              │
                              └──► Graceful Fallback (cached/static content)
```

| Control | Default | Notes |
| :--- | :--- | :--- |
| Sub-agent timeout | `{{4.0s}}` | Terminate unresponsive calls, trigger the fallback path |
| Retry backoff | Exponential + jitter | Only for retriable errors (e.g. `429`) — never for data/validation errors |
| Circuit breaker trip | `{{>15% failure rate}}` over `{{1 min}}` | Routes to a static fallback without exhausting backend threads |

---

## 10. Data Governance & Security

- **Input sanitization**: strip/neutralize prompt-injection delimiter attacks before queries reach the coordinator prompt.
- **PII redaction**: scrub credit-card numbers, emails, phone numbers before routing to sub-agents (or before logging).
- **Credential handling**: secrets come from `{{env vars for local dev / a secrets manager for prod}}` — never hardcoded, never logged.

---

## 11. Telemetry, Tracing & Operational SLA

| Metric | Collection mechanism | Target SLA |
| :--- | :--- | :--- |
| Time to First Token (TTFT) | `{{tracing tool}}` | `{{< 800ms}}` |
| Total turn duration (p95) | `{{APM tool}}` | `{{< 2.5s}}` |
| Routing accuracy | Offline eval set (Section 12) | `{{> 96%}}` |
| Token cost per turn | `{{billing metric source}}` | Tracked per session |

A trace ID must link every hop across coordinator → sub-agent calls.

---

## 12. Required Test Suite & Evaluation

- **Routing-accuracy eval set**: a fixed list of `(query, expected_sub_agent)` pairs, run offline against the live classifier — this is what Section 11's "Routing accuracy" SLA measures against.
- **Golden Q&A regression set**: known-good `(query, expected_response_shape)` pairs per sub-agent, to catch prompt/model-swap regressions.
- **Mocking policy**: `{{how are LLM calls mocked in unit tests? e.g. a fixed-response fake model for schema/routing tests, real-model calls only in the eval set}}`
- **Contract tests**: every sub-agent's declared input/output schema (Section 3) is exercised with at least one valid and one invalid payload.
- Durable test-generation log: append results to `{{path, e.g. .agents/memory-bank/testGenerationLog.md}}`, following this project's existing convention.

---

## 13. Roadmap / Phase Mapping

Map this document's sections to when each is actually being built — update the **Status** column in place as work progresses. This is the mechanism for tracking "what's real today," not a separate per-phase spec file.

Use sequential phase numbers (`Phase 1`, `Phase 2`, ...) rather than calendar time (sprints/weeks/dates) — a phase name should describe a capability milestone that holds up regardless of how the project's schedule shifts.

| Section(s) | Capability | Target phase | Status |
| :--- | :--- | :--- | :--- |
| Section 3, Section 4, Section 6 | Coordinator routes to 1 sub-agent, strict schemas | `{{e.g. Phase 1}}` | ⏳ Planned |
| Section 3 (additional rows) | More sub-agents registered | `{{e.g. Phase 2}}` | ⏳ Planned |
| Section 12 | Evaluation harness | `{{e.g. Phase 3}}` | ⏳ Planned |
| Section 1 (API layer), Section 8 (streaming) | FastAPI integration | `{{e.g. Phase 3}}` | ⏳ Planned |
| Section 9, Section 10, Section 11 | Resiliency, security, telemetry | `{{e.g. Phase 4 / post-launch}}` | ⏳ Planned |

---

## 14. Acceptance Criteria (pre-build gate)

- [ ] Section 1 discovery questions answered (domains, QPS/latency target, eval dataset status, API-layer status).
- [ ] Section 2 pattern selected with a justification tied to the actual product requirement.
- [ ] Section 3 registry lists every sub-agent in scope for the *current* roadmap milestone (Section 13), each with input/output schemas.
- [ ] Section 4 confidence source is concretely specified, not left as "the LLM decides."
- [ ] Section 5 session-identity contract is defined.
- [ ] Section 12 mocking policy and at least a draft eval set exist before agent code is written.
- [ ] Appendix A (Decision Log) has no open rows.
- [ ] Appendix B (Out-of-Scope) is filled in — not left empty.

---

## 15. Production Verification Checklist (post-build gate)

- [ ] Substring/keyword matching eliminated in favor of semantic intent classification.
- [ ] Strict schemas enforced on every cross-agent boundary (Section 6).
- [ ] Long-lived resources injected as singletons, not re-instantiated per call (Section 7).
- [ ] Context-window eviction/sliding buffer configured (Section 5).
- [ ] Circuit breaker and timeout policies defined for each downstream dependency (Section 9).
- [ ] PII redaction and prompt-injection filters active (Section 10).
- [ ] Distributed tracing (trace ID) linked across all agent hops (Section 11).
- [ ] Routing-accuracy eval set passes at the Section 11 target (Section 12).

---

## Appendix A: Decision Log

| Decision | Options considered | Selected option | Reason | Date |
| :--- | :--- | :--- | :--- | :--- |
| `{{DECISION}}` | `{{OPTIONS}}` | `{{SELECTED}}` | `{{RATIONALE}}` | `{{DATE}}` |

## Appendix B: Out-of-Scope / Non-Goals

List what this coordinator agent explicitly does **not** do at the current roadmap milestone (Section 13), so scope creep has an obvious reference point.

- `{{e.g. "Multi-language support — deferred, no requirement yet"}}`

---

**Version**: 1.0
**Last Updated**: `{{Date}}`
**Template Author**: `{{Name}}`
