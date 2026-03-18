# ROADMAP

## Objective

Move StupidClaw from a strong functional MVP to a production-ready, observable, and safely repeatable automation system.

## Priority 1: Reliability and Idempotency

### 1. Mutation idempotency pass
- Ensure every state transition and comment write can run safely more than once.
- Add precondition checks before updates (expected current state/labels/markers).
- Prevent duplicate subtask creation in Stage 2 when rerun.
- Prevent duplicate rollup summaries in Stage 3.

Success criteria:
- Re-running the same pipeline cycle produces no duplicate side effects.
- Integration tests explicitly cover rerun behavior.

### 2. Retry and failure handling policy
- Add bounded retries with backoff for transient Linear/Anthropic errors.
- Distinguish transient vs terminal errors in stage logic.
- Standardize failure results and error markers for post-mortem clarity.

Success criteria:
- Transient failures recover automatically without manual intervention.
- Fatal failures surface clear diagnostics and do not corrupt workflow state.

## Priority 2: Observability and Operations

### 3. Structured run telemetry
- Emit per-stage timing, processed counts, and outcome buckets.
- Add run-level IDs and issue-level correlation IDs in logs.
- Record lock contention, budget skips, and exception categories.

Success criteria:
- One run log can explain exactly what changed and why.
- Operators can quickly answer “what happened in the last hour/day.”

### 4. Lightweight run reporting
- Add optional summary comment or status artifact per completed pipeline cycle.
- Include: stage counts, skipped reasons, blocked/scope-change counts.

Success criteria:
- Team can see execution health without opening raw logs.

## Priority 3: Delivery Guardrails

### 5. CI pipeline
- Add GitHub Actions workflow for lint + tests (`pytest -q`).
- Fail PRs on test regressions.
- Optionally add coverage reporting threshold.

Success criteria:
- `master` remains deployable.
- Every change is validated before merge.

### 6. Release and environment discipline
- Add environment matrix docs (dev/staging/prod expectations).
- Add release checklist (tests, smoke run, tag, deploy, post-deploy verify).
- Add rollback procedure.

Success criteria:
- Deploys are repeatable and reversible with documented steps.

## Priority 4: Product Behavior Improvements

### 7. Smarter blocked-loop handling
- Add blocked staleness escalation behavior.
- Improve human-reply extraction with better filtering and edge-case handling.
- Add explicit “re-entry reason” comments when returning `Blocked -> Backlog`.

Success criteria:
- Blocked issues do not stall silently.
- Re-entry behavior is auditable in comments.

### 8. Budget-awareness refinements
- Add per-stage budget spend estimates before expensive calls.
- Add optional hard stop for per-parent budget cap.
- Add budget trend reporting to logs.

Success criteria:
- Cost control becomes proactive, not only reactive.

## Suggested Execution Order

1. Idempotency + retries
2. Telemetry + run reporting
3. CI and release guardrails
4. Blocked-loop and budget refinements

## Notes

- Keep all new behavior covered by mock integration tests first.
- Prefer additive, small PRs by workstream to reduce risk.
