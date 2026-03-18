import logging
import sys


def setup_logging() -> logging.Logger:
    """Configure and return the root pipeline logger.
    Call this once in run_pipeline.py's main(), not at module scope."""
    logger = logging.getLogger("stupidclaw")

    if logger.handlers:
        # Already configured (e.g., called twice) — don't double-add handlers
        return logger

    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
