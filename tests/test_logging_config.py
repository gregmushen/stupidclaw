import logging
from shared.logging_config import setup_logging


class TestSetupLogging:
    def test_returns_logger_instance(self):
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "stupidclaw"

    def test_no_duplicate_handlers_on_second_call(self):
        logger1 = setup_logging()
        handler_count = len(logger1.handlers)
        logger2 = setup_logging()
        assert len(logger2.handlers) == handler_count
        assert logger1 is logger2
