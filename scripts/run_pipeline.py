import argparse
import os
from contextlib import contextmanager

from shared.cost_tracker import check_daily_budget
from shared.logging_config import setup_logging
from stage1_triage import run as run_stage1
from stage2_breakdown import run as run_stage2
from stage3_research import run as run_stage3


def acquire_lock(path: str) -> int:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    return os.open(path, flags, 0o644)


def release_lock(fd: int, path: str) -> None:
    try:
        os.close(fd)
    finally:
        if os.path.exists(path):
            os.unlink(path)


@contextmanager
def pipeline_lock(path: str):
    fd = acquire_lock(path)
    try:
        yield
    finally:
        release_lock(fd, path)


def run_cycle(stage_iterations: int = 1) -> dict:
    stage1 = run_stage1(max_iterations=stage_iterations)
    stage2 = run_stage2(max_iterations=stage_iterations)
    stage3 = run_stage3(max_iterations=stage_iterations)
    return {"stage1": stage1, "stage2": stage2, "stage3": stage3}


def main(lock_path: str, stage_iterations: int = 1) -> int:
    logger = setup_logging()

    try:
        with pipeline_lock(lock_path):
            within_budget, remaining = check_daily_budget()
            if not within_budget:
                logger.warning("Daily budget exceeded, skipping pipeline run (remaining=%0.2f)", remaining)
                return 0

            counts = run_cycle(stage_iterations=stage_iterations)
            logger.info(
                "Pipeline cycle complete: triage=%s breakdown=%s research=%s",
                counts["stage1"],
                counts["stage2"],
                counts["stage3"],
            )
            return 0
    except FileExistsError:
        logger.info("Pipeline already running (lock exists at %s). Exiting.", lock_path)
        return 0
    except Exception:
        logger.exception("Pipeline run failed")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run StupidClaw pipeline cycle.")
    parser.add_argument("--lock-path", default="/tmp/stupidclaw.lock", help="Lock file path.")
    parser.add_argument(
        "--stage-iterations",
        type=int,
        default=1,
        help="Maximum issues each stage should process per run.",
    )
    args = parser.parse_args()
    raise SystemExit(main(lock_path=args.lock_path, stage_iterations=args.stage_iterations))
