"""Structured logging setup."""

from __future__ import annotations

import logging

import structlog


def configure_logging(level: str = "INFO", as_json: bool = True) -> None:
    processors: list[structlog.types.Processor] = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
    ]
    if as_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO), format="%(message)s"
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
