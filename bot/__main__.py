"""Entrypoint: ``python -m bot``."""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from bot.client import UtilityBot
from bot.config import ConfigError, load_config


def main() -> int:
    load_dotenv()
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    # discord.Client.run() defaults to root_logger=False, which only attaches a
    # handler to the "discord" logger namespace. bot/client.py logs on "bot.client"
    # (via logging.getLogger(__name__)); without root_logger=True those records
    # propagate to the unconfigured root logger and are silently dropped instead
    # of reaching stdout (issue #14). root_logger=True alone still isn't enough:
    # discord.py's default handler is a bare logging.StreamHandler(), which binds
    # to sys.stderr — but the PRD (specs/bot/0001-prd.md) requires logging to
    # stdout for the platform's monitor, so the handler must be explicit.
    UtilityBot(config).run(
        config.token,
        root_logger=True,
        log_handler=logging.StreamHandler(sys.stdout),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
