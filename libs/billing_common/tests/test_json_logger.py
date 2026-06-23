"""Testes unitários do build_logger (logging estruturado em JSON)."""

from __future__ import annotations

import json
import logging

from billing_common.logging.json_logger import build_logger


def test_build_logger_sets_level_and_name():
    logger = build_logger(name="test-logger-level", level=logging.WARNING)

    assert logger.name == "test-logger-level"
    assert logger.level == logging.WARNING


def test_build_logger_emits_single_json_line(capsys):
    logger = build_logger(name="test-logger-json")

    logger.info("hello world")

    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["message"] == "hello world"
    assert payload["severity"] == "INFO"
    assert payload["logger"] == "test-logger-json"
    assert "timestamp" in payload


def test_build_logger_includes_exception_when_logged_with_exc_info(capsys):
    logger = build_logger(name="test-logger-exception")

    try:
        raise ValueError("boom")
    except ValueError:
        logger.error("failed", exc_info=True)

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert "exception" in payload
    assert "ValueError: boom" in payload["exception"]


def test_build_logger_is_idempotent_and_does_not_duplicate_handlers():
    logger_first_call = build_logger(name="test-logger-idempotent")
    logger_second_call = build_logger(name="test-logger-idempotent")

    assert logger_first_call is logger_second_call
    assert len(logger_first_call.handlers) == 1


def test_build_logger_does_not_propagate_to_root():
    logger = build_logger(name="test-logger-no-propagate")

    assert logger.propagate is False
