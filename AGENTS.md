# Project Rules & Conventions

This file enforces Vibe Engineering rules and workspace conventions for all agents operating in this workspace.

## 1. Spec-Driven BDD Checkpoints
* Before generating or modifying any code for features, you MUST formulate a technical BDD specification in `specs/` (narrative + Gherkin scenarios). 
* Do not write or execute code changes until the user has approved the specification or implementation plan.

## 2. Context Budgeting & Hygiene
* Do not print verbose loops, large logs, or heavy outputs to the standard stdout or chat interface.
* Always pipe noisy outputs to a log file and present only a concise summary in the chat.

## 3. Vibe Diff Checkpoints
* Before executing any long-running or resource-intensive tasks, present a concise "Vibe Diff" checkpoint summarizing the exact parameters and target files.

## 4. Durable Memory Primitives
* Every major run, evaluation, or architectural decision MUST be recorded in a durable log under `.agents/memory-bank/` (e.g., `projectDocs.md` or `activeContext.md`). 

## 5. Environment & Path Safety
* **Environment**: Always use the local project environment tools and test runners (e.g., local virtualenv, local node_modules). Do not use system-level commands blindly.
* **Path Resolution**: Never hardcode base paths. Always import paths from a configuration module and resolve them dynamically. Use `os.path.join` or equivalent path libraries for cross-platform compatibility.

## 6. Document Code Logic
* Any code added or modified MUST contain thorough inline comments, method-level docstrings, and file-level docstrings explaining the technical logic, inputs, outputs, and design trade-offs.

## 7. Reuse Before Reinventing
* Before writing new logic — a script, a process, a doc-generation pattern, a spec structure — check `skills/` (project) and the user's global skills for one that already covers it (e.g. `test-suite-generator`, `knowledge-artifact-doc`, the `SpecToolBox` templates) and use or extend it instead of hand-rolling an equivalent from scratch.
* If no skill covers a task that's likely to recur, consider creating one (see `skills/knowledge-artifact-doc/SKILL.md` for the expected format) rather than leaving the pattern undocumented in a one-off response.

## 8. Knowledge Artifact per Implemented Requirement
* After implementing a new requirement or feature (not just planning it), produce or update — in place, never as a new numbered/dated file — a knowledge artifact via the `knowledge-artifact-doc` skill: a markdown reference doc plus a companion Mermaid sequence-diagram HTML artifact, filed under `Reference/Learning/<topic>/`.
* Use judgment on granularity: a one-line bugfix doesn't need a new artifact; a new agent, module, or pipeline phase does.

## 9. Verify Against Reality, Not Assumption
* Before coding against a library — especially a fast-moving one like `pydantic-ai` — confirm its actual installed API surface via introspection (`inspect.signature`, a small throwaway script) rather than relying on possibly-stale prior knowledge of its API.
* Before declaring a feature complete, run at least one real end-to-end execution (a real CLI invocation, a real rendered diagram, a real DB run) — not just passing mocked/unit tests. Mocked tests catch contract bugs; only a real run catches a design/behavior bug in how those contracts are used together.

## 10. One Living Document Per Domain, Tracked With a Decision Log
* A spec, implementation plan, or learning doc for a given domain is one file, updated in place as it progresses — a Roadmap/status table inside it tracks phase, not the filename or a `-v2`/`-phase2`/dated copy.
* Every spec carries a Decision Log (option considered, selected option, reason, date). Mark a resolved decision with strikethrough plus its resolution rather than deleting the row — the record of what was considered and why is the point.
* New domains get their own numbered folder under `specs/` (`specs/1_data-pipeline/`, `specs/2_coordinator-agent/`, ...) — the number reflects build order, not creation date.

## 11. Fix Every Cross-Reference When Renaming or Moving a File
* Grep the whole repo for the old path/filename and update every reference in the same change. A moved file with dangling links elsewhere is a regression, not a detail to leave for later.

## 12. Match Existing Code Idioms
* When adding a new module, reuse this codebase's established pattern for the same concern (retry-with-backoff via `tenacity`, structured error envelopes, `_Fake*`/`monkeypatch` test mocking style) rather than introducing a second convention for something already solved elsewhere in the repo.
