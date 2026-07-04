"""Entrypoint: ``python -m bot``."""

from __future__ import annotations

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
    # of reaching stdout (issue #14).
    UtilityBot(config).run(config.token, root_logger=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
