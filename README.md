# StupidClaw

Automated Linear workflow agent for the `STU` team.  
The pipeline runs in three stages:

1. `Stage 1: Triage` (`Backlog -> Triaged|Blocked`)
2. `Stage 2: Breakdown` (`Triaged -> Planning Complete` + ordered subtasks)
3. `Stage 3: Research` (agent subtasks + sibling advancement + parent rollup)

The entrypoint is [`scripts/run_pipeline.py`](scripts/run_pipeline.py), designed for cron/Docker execution with lock protection and daily budget gating.

## What This Repo Contains

- Stage scripts:
  - [`scripts/stage1_triage.py`](scripts/stage1_triage.py)
  - [`scripts/stage2_breakdown.py`](scripts/stage2_breakdown.py)
  - [`scripts/stage3_research.py`](scripts/stage3_research.py)
- Pipeline runner:
  - [`scripts/run_pipeline.py`](scripts/run_pipeline.py)
- Shared clients/utilities:
  - [`scripts/shared/`](scripts/shared)
- Prompts:
  - [`prompts/triage.md`](prompts/triage.md)
  - [`prompts/breakdown.md`](prompts/breakdown.md)
  - [`prompts/research.md`](prompts/research.md)
- Test suite:
  - [`tests/`](tests)
- Container runtime:
  - [`Dockerfile`](Dockerfile), [`docker-compose.yml`](docker-compose.yml), [`crontab`](crontab), [`entrypoint.sh`](entrypoint.sh)

## Architecture

### Stage 1: Triage

- Pulls issues in `STATE_BACKLOG`.
- Calls Claude with prompt + structured issue context.
- Parses strict JSON (`task_type`, `complexity`, `priority`, `blocked`, etc).
- Writes marker comments:
  - `<!-- triage-result -->` on success
  - `<!-- blocked -->` when blocked
- Applies state transitions:
  - Not blocked -> `STATE_TRIAGED`
  - Blocked -> `STATE_BLOCKED` + clarification label
- Supports blocked re-entry:
  - If a human replies after a blocked marker, issue is moved `Blocked -> Backlog` for re-triage.

### Stage 2: Breakdown

- Pulls issues in `STATE_TRIAGED`.
- Calls Claude to return ordered `tasks[]` with `agent|human` type.
- Creates child issues with `sortOrder`.
- State assignment for children:
  - First `agent-task` child -> `STATE_IN_PROGRESS`
  - Remaining children -> `STATE_TODO`
- Moves parent to `STATE_PLANNING_COMPLETE`.
- Writes `<!-- breakdown-result -->` marker comment.

### Stage 3: Research

- Pulls `agent-task` issues in `STATE_IN_PROGRESS`.
- Enforces predecessor gate using `sortOrder`.
- Calls Claude and parses `completed|blocked|needs_human|scope_change`.
- On completion:
  - Marks current child `STATE_DONE`
  - Writes `<!-- research-result -->`
  - Advances next eligible `agent-task` sibling to `STATE_IN_PROGRESS`
  - If all children are terminal, rolls up parent to `Done` or `Blocked` and writes `<!-- summary -->`
- On blocked/needs_human/scope_change:
  - Marks child `STATE_BLOCKED`
  - Applies relevant labels (`clarification`, `scope-change`)
  - Writes marker comment.

### Pipeline Runtime

[`scripts/run_pipeline.py`](scripts/run_pipeline.py):

- Acquires lock using an exclusive lockfile.
- Skips safely if lock already exists.
- Checks daily budget before any stage work.
- Runs Stage 1 -> Stage 2 -> Stage 3 in order.
- Logs stage counts and exits `0` on no-op/skip, `1` on hard failure.

## Prerequisites

- Python `>=3.11`
- Linear workspace/team setup for `STU`
- Anthropic API key
- Docker (optional, for containerized runtime)

## Quick Start (Local)

### 1) Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2) Configure environment

```bash
cp .env.example .env
```

Fill required keys in `.env`:
- `LINEAR_API_KEY`
- `ANTHROPIC_API_KEY`
- all `STATE_*`
- all `LABEL_*`

### 3) Generate STU IDs (optional helper)

```bash
LINEAR_API_KEY="your_key" python scripts/setup_workspace.py
```

Copy output values into `.env`.

### 4) Run one pipeline cycle

```bash
python scripts/run_pipeline.py
```

Useful flags:

```bash
python scripts/run_pipeline.py --lock-path /tmp/stupidclaw.lock --stage-iterations 1
```

## Running Individual Stages

```bash
python scripts/stage1_triage.py
python scripts/stage2_breakdown.py
python scripts/stage3_research.py
```

## Docker / Cron Runtime

Build and run:

```bash
docker compose up --build
```

Manual smoke run:

```bash
docker compose run --rm stupidclaw python scripts/run_pipeline.py
```

Cron schedule is defined in [`crontab`](crontab) (`*/5 * * * *`).

## Testing

Run all tests:

```bash
pytest -q
```

Run verbose suite:

```bash
pytest tests/ -v
```

Current suite size in this repo: `81` tests.

### Test strategy highlights

- Unit tests for parsers/builders and utility modules.
- Mocked Linear GraphQL layer via [`tests/mock_linear.py`](tests/mock_linear.py).
- Integration tests for full pipeline lifecycle and blocked re-entry.
- No live network calls in tests.

## Environment Variables

See [`.env.example`](.env.example) for full list.

Core categories:
- API: `LINEAR_API_KEY`, `ANTHROPIC_API_KEY`
- Workflow states: `STATE_*`
- Labels: `LABEL_*`
- Budgeting: `DAILY_BUDGET_CAP`, `PER_TASK_TOKEN_CAP`, `COST_TRACKER_PATH`
- Runtime: `LOCKFILE_PATH`, `STALE_BLOCKED_HOURS`, `CLAUDE_MODEL`

## Marker Comments

Used to make stage output idempotent and queryable in Linear comments:

- `<!-- triage-result -->`
- `<!-- breakdown-result -->`
- `<!-- research-result -->`
- `<!-- blocked -->`
- `<!-- summary -->`

## Operational Notes

- Lock behavior is intentionally fail-safe: second runner exits cleanly.
- Budget gating happens before stage work each cycle.
- Stage 3 progression is strictly ordered by child `sortOrder`.
- Parent rollup occurs only when all children are terminal.

## Troubleshooting

- Missing env var:
  - Error from `shared.config._env(...)` indicates a required key is not set.
- Stage not picking up issues:
  - Verify state IDs/label IDs in `.env` match `STU` workflow.
- Docker compose warning about `version` key:
  - Harmless with modern Compose; can remove `version` field if desired.
- Blocked issue not re-triaging:
  - Ensure there is a non-agent human reply comment posted after `<!-- blocked -->`.

## Development Workflow

1. Make code changes.
2. Run `pytest -q`.
3. Run local pipeline smoke (`python scripts/run_pipeline.py`) or Docker smoke.
4. Update Linear statuses only after passing verification.

