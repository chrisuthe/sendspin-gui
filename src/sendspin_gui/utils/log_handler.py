"""Custom logging handler for forwarding logs to the GUI."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class GUILogHandler(logging.Handler):
    """Logging handler that forwards log records to a GUI callback.

    This handler is thread-safe and can be used from async contexts.
    The callback should handle thread marshalling to the GUI thread.
    """

    # Map Python logging levels to GUI event log levels
    LEVEL_MAP = {
        logging.DEBUG: "debug",
        logging.INFO: "info",
        logging.WARNING: "warning",
        logging.ERROR: "error",
        logging.CRITICAL: "error",
    }

    def __init__(self, callback: Callable[[str, str], None]) -> None:
        """Initialize the handler.

        Args:
            callback: Function to call with (message, level) for each log record.
                     The callback will be called from the logging thread, so it
                     should handle thread marshalling if needed.
        """
        super().__init__()
        self._callback = callback
        self.setFormatter(
            logging.Formatter("%(name)s: %(message)s")
        )

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record by calling the callback.

        Args:
            record: The log record to emit.
        """
        try:
            msg = self.format(record)
            level = self.LEVEL_MAP.get(record.levelno, "info")
            self._callback(msg, level)
        except Exception:
            # Don't raise exceptions from logging - it can cause infinite loops
            self.handleError(record)
