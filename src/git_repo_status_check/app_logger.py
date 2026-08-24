"""Centralized logger — single on/off + level toggle for all diagnostics.

Feature code calls ``AppLogger``, never ``logging.getLogger`` or ``print`` directly.
This is for diagnostics only; user-facing report text is printed by ``reporter``.
"""

from __future__ import annotations

import logging

_LOGGER_NAME = "git_repo_status_check"


class AppLogger:
    """Thin wrapper over stdlib ``logging`` with one configuration point."""

    _logger: logging.Logger | None = None

    @classmethod
    def configure(cls, *, debug: bool = False) -> None:
        """Configure the single underlying logger. Call once at startup."""
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(logging.DEBUG if debug else logging.WARNING)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            logger.addHandler(handler)
        cls._logger = logger

    @classmethod
    def _get(cls) -> logging.Logger:
        if cls._logger is None:
            cls.configure()
        assert cls._logger is not None
        return cls._logger

    @classmethod
    def debug(cls, message: str) -> None:
        cls._get().debug(message)

    @classmethod
    def info(cls, message: str) -> None:
        cls._get().info(message)

    @classmethod
    def warning(cls, message: str) -> None:
        cls._get().warning(message)

    @classmethod
    def error(cls, message: str) -> None:
        cls._get().error(message)
