"""
filename: logging.py
description: Structured logger via structlog. Returns per-module bound loggers.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import logging
import sys

import structlog


def _configure() -> None:
    # Route logs to stderr so script stdout (e.g. run_pipeline.py JSON) stays parseable.
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


_configure()


def get_logger(name: str):
    return structlog.get_logger(name)
