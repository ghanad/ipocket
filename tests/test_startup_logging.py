from __future__ import annotations

import logging

from app.startup import configure_logging


def test_configure_logging_defaults_to_info(monkeypatch) -> None:
    monkeypatch.delenv("IPOCKET_LOG_LEVEL", raising=False)

    configure_logging()

    assert logging.getLogger().getEffectiveLevel() == logging.INFO


def test_configure_logging_respects_env(monkeypatch) -> None:
    monkeypatch.setenv("IPOCKET_LOG_LEVEL", "DEBUG")

    configure_logging()

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
