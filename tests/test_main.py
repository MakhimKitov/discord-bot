"""Entrypoint wiring: the bot's own INFO logs must reach stdout (issue #14).

Two independent defects had to be fixed, and both are covered here:

1. Visibility — discord.Client.run() defaults to root_logger=False, which only
   configures the "discord" logger namespace. bot/client.py logs on
   "bot.client" (a different namespace) via ``logging.getLogger(__name__)``;
   those records propagate to the root logger, which discord.py leaves
   unconfigured unless root_logger=True is passed. Without it, "commands
   synced to guild %s" and "logged in as %s" never print anywhere.
2. Destination — even with root_logger=True, discord.py's default handler is
   a bare ``logging.StreamHandler()``, which binds to sys.stderr. The PRD
   (specs/bot/0001-prd.md) requires "logging to stdout", so an explicit
   ``logging.StreamHandler(sys.stdout)`` must be passed as log_handler.
"""

from __future__ import annotations

import logging
import sys

import discord

from bot import __main__ as entrypoint
from bot.client import UtilityBot


def test_run_is_called_with_root_logger_true_and_a_stdout_handler(monkeypatch):
    """Covers both halves of the PRD's 'logging to stdout' requirement:
    root_logger=True (visibility — issue #14) and an explicit stdout-bound
    log_handler (destination — without it, discord.py's default handler is a
    bare logging.StreamHandler() bound to sys.stderr, not sys.stdout).
    """
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.delenv("GUILD_ID", raising=False)
    monkeypatch.setattr(entrypoint, "load_dotenv", lambda: None)

    captured = {}

    def fake_run(self, token, **kwargs):
        captured["token"] = token
        captured["kwargs"] = kwargs

    monkeypatch.setattr(UtilityBot, "run", fake_run)

    assert entrypoint.main() == 0
    assert captured["token"] == "test-token"
    assert captured["kwargs"].get("root_logger") is True
    handler = captured["kwargs"].get("log_handler")
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout


def test_default_root_logger_drops_bot_client_info():
    """Baseline: reproduces the defect in isolation. "bot.client" has no level
    of its own, so it inherits the root logger's effective level. An
    unconfigured root logger defaults to WARNING, so log.info() calls on
    "bot.client" are filtered before any handler ever sees them — this is
    exactly why the sync/on_ready lines never reached stdout.
    """
    root = logging.getLogger()
    bot_logger = logging.getLogger("bot.client")
    original_root_level = root.level
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    root.addHandler(handler)
    try:
        root.setLevel(logging.WARNING)
        bot_logger.info("commands synced to guild %s", 123)
        assert records == []
    finally:
        root.removeHandler(handler)
        root.setLevel(original_root_level)


def test_root_logger_true_lets_bot_client_info_through():
    """The visibility half of the fix: discord.utils.setup_logging(root=True) —
    what run(root_logger=True) triggers — raises the root logger's level to
    INFO, so "bot.client" (which still sets no level of its own) now has an
    effective level of INFO and its records reach a handler on the root
    logger. This intentionally uses a plain logging.Handler, not a stream
    handler: it isolates the visibility mechanism from the destination
    (stdout vs stderr), which test_stdout_handler_reaches_sys_stdout covers
    separately.
    """
    root = logging.getLogger()
    bot_logger = logging.getLogger("bot.client")
    original_root_level = root.level
    original_handlers = list(root.handlers)
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    try:
        discord.utils.setup_logging(root=True, handler=handler)
        bot_logger.info("commands synced to guild %s", 123)
        assert len(records) == 1
        assert records[0].getMessage() == "commands synced to guild 123"
    finally:
        root.setLevel(original_root_level)
        root.handlers[:] = original_handlers


def test_stdout_handler_reaches_sys_stdout(capsys):
    """The destination half of the fix: a bare logging.StreamHandler() (what
    discord.py's setup_logging uses when no log_handler is passed) binds to
    sys.stderr, not sys.stdout. The PRD (specs/bot/0001-prd.md) requires
    'logging to stdout', so bot/__main__.py must pass an explicit
    logging.StreamHandler(sys.stdout). This confirms that handler actually
    writes to the stdout stream pytest captures, not stderr.
    """
    root = logging.getLogger()
    bot_logger = logging.getLogger("bot.client")
    original_root_level = root.level
    original_handlers = list(root.handlers)
    try:
        discord.utils.setup_logging(root=True, handler=logging.StreamHandler(sys.stdout))
        bot_logger.info("commands synced to guild %s", 123)
        captured = capsys.readouterr()
        assert "commands synced to guild 123" in captured.out
        assert "commands synced to guild 123" not in captured.err
    finally:
        root.setLevel(original_root_level)
        root.handlers[:] = original_handlers
