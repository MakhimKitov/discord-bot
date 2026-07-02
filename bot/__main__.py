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
    UtilityBot(config).run(config.token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
