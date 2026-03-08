# AGENT.md

This file defines how agents and engineers should work in this repository.

The project goal is not vague "AI research." The goal is to build a reproducible, auditable protein-design copilot with a narrow first scope and clean execution discipline.

## Core operating rules

- Ship the simplest correct solution.
- Prefer explicit code and data contracts over clever abstractions.
- Keep the first product slice narrow: binder design against protein targets.
- Do not bury system behavior inside giant prompts if the behavior should live in code, schemas, or config.
- Every meaningful decision must be inspectable after the fact.
- Provenance is mandatory. If a datum, score, or conclusion cannot be traced, treat it as defective.

## Scope discipline

- Optimize for one working vertical slice before expanding tool coverage.
- Do not introduce generalized protein-engineering workflows until the binder-design path is stable.
- Use stubs or mocks when scientific execution is not ready, but label them honestly.
- Do not claim scientific confidence from prompt-only outputs.

## Git rules

- Work on a branch. Do not commit directly to `main`.
- Keep branches focused on one logical change.
- Use branch names that describe intent plainly.
- Make small, reviewable commits.
- Commit messages must be imperative and specific.
- Do not mix refactors with behavior changes unless the refactor is required for the fix.
- Do not rewrite published history unless explicitly requested.
- Do not use destructive commands like `git reset --hard` or `git checkout --` unless explicitly approved.
- Check `git status` before and after making changes.
- Read the diff before committing.

## TDD and testing rules

- Default to test-driven development for logic-heavy code.
- Write or update tests for every non-trivial behavior change.
- Add regression tests for bugs before fixing them when practical.
- Start with narrow unit tests for schemas, routing, ranking, and policy decisions.
- Add integration tests for end-to-end flows once the interfaces are stable.
- If a change is hard to test, that is usually a design problem. Simplify the design.
- Do not mark work complete if behavior changed and no verification exists.

## Definition of done

Work is done only when all of the following are true:

- The code change is implemented.
- Tests relevant to the change exist and pass, or the missing coverage is called out explicitly.
- Linting and static checks relevant to the touched code have been run, or the gap is called out explicitly.
- The diff is understandable without hidden context.
- The change preserves or improves provenance and traceability.
- User-visible behavior, schema changes, and risks are documented in the final summary.

## PR hygiene

- Keep PRs narrow enough to review in one sitting.
- Do not open a PR that mixes roadmap churn, formatting noise, and real behavior changes.
- Include a clear statement of:
  - what changed
  - why it changed
  - how it was verified
  - known risks or follow-ups
- If a PR is large, split it.
- If a file is hard to review, simplify the file before adding more logic.
- Do not leave dead code, commented-out code, or placeholder branches without an explicit reason.

## Clean PR checklist

Before considering a PR ready:

- Rebase or merge as needed to remove obvious drift.
- Remove debug prints, temporary scripts, and unused imports.
- Remove unrelated file churn.
- Check naming. Ambiguous names are review debt.
- Check for duplicated logic that should be centralized.
- Check for silent fallbacks that hide failures.
- Check that new config, env vars, and external dependencies are documented.
- Check that generated files are either intentionally committed or ignored.

## Code review rules

Review code with a bias toward correctness, operational clarity, and future maintainability.

Always check:

- correctness of control flow
- schema and contract validity
- error handling and failure visibility
- provenance capture
- licensing and execution-mode correctness
- reproducibility
- test coverage
- security impact of tool execution
- performance impact where compute-heavy jobs are involved

Primary review questions:

- Can this fail silently?
- Can this produce an output that looks valid but is not traceable?
- Can this violate academic vs commercial-safe routing?
- Can this make the system harder to audit later?
- Does this put policy in prompts where it belongs in code or config?
- Is the abstraction justified by real reuse?

## Instructions for checking code

When asked to check code, default to a real review, not a superficial summary.

Review workflow:

1. Read the changed files and inspect the diff.
2. Identify behavior changes first, not style issues.
3. Look for regressions in:
   - schemas
   - tool routing
   - trace persistence
   - report generation
   - license handling
4. Check whether tests prove the intended behavior.
5. Check whether failure paths are explicit and observable.
6. Check whether the change increases prompt-coupled behavior that should be structural.
7. Summarize findings in severity order.

If no issues are found, say so explicitly and note residual risk or missing validation.

## Instructions for cleaning a PR

When asked to clean a PR:

1. Inspect the diff and separate signal from noise.
2. Remove dead code, debug artifacts, and unrelated edits.
3. Tighten naming and comments where they are vague.
4. Reduce file churn where possible.
5. Add or fix tests for the changed behavior.
6. Re-run relevant checks.
7. Produce a concise summary of what changed and what remains risky.

Do not "clean" a PR by hiding complexity without reducing it. Make the change easier to reason about.

## Prompting and agent behavior

- Ask users follow-up questions only when the answer materially changes the search space or execution mode.
- Prefer structured outputs over long free-form text.
- Persist machine-readable artifacts for campaign specs, traces, and candidate records.
- Never present hidden reasoning as scientific evidence.
- Tie rationale to scores, provenance, and explicit uncertainty.

## Security and tool execution

- Relaxed sandbox access does not remove the requirement for explicit tool invocation records.
- External commands, scripts, and APIs must be logged with version and timestamp when they affect outputs.
- Network-fetched data must record source and retrieval time.
- Do not silently fall back from one scientific tool to another without recording the routing decision.

## Research-specific rules

- Separate retrieval, planning, generation, evaluation, and reporting concerns.
- Use license-aware routing at all times.
- Default to conservative claims when tool outputs disagree.
- Cross-model disagreement is a signal, not an inconvenience to ignore.
- Prefer reproducible computational traces over polished but opaque narratives.

## File and repo conventions

- Keep specs, schemas, and contracts in versioned files.
- Keep artifacts and traces in predictable locations.
- Keep scripts small and single-purpose.
- Prefer JSON or YAML for machine-readable contracts.
- Prefer Markdown for human-facing specs and runbooks.

## Escalation rules

Stop and escalate when:

- the correct execution mode is unclear and it affects license compliance
- a schema change would break stored artifacts or adapters
- external tool behavior is ambiguous and results could be misleading
- scientific outputs appear inconsistent enough that ranking would be dishonest
- a requested shortcut would reduce auditability or reproducibility in a material way

## Default working style

- Be direct.
- Be conservative about scientific claims.
- Be explicit about assumptions.
- Prefer a small honest system over a broad fake one.
