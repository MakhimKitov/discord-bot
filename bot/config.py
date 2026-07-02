"""Configuration from environment only (PRD: no config files, no secrets in-repo)."""

from __future__ import annotations

import os
from dataclasses import dataclass

DISCORD_TOKEN = "DISCORD_TOKEN"
GUILD_ID = "GUILD_ID"


class ConfigError(ValueError):
    """The environment does not provide a runnable configuration."""


@dataclass(slots=True)
class BotConfig:
    token: str
    guild_id: int | None = None


def load_config(environ: dict[str, str] | None = None) -> BotConfig:
    env = dict(os.environ) if environ is None else environ
    token = env.get(DISCORD_TOKEN, "").strip()
    if not token:
        raise ConfigError(f"{DISCORD_TOKEN} is required (see .env.example)")
    guild_id: int | None = None
    raw_guild = env.get(GUILD_ID, "").strip()
    if raw_guild:
        try:
            guild_id = int(raw_guild)
        except ValueError as exc:
            raise ConfigError(f"{GUILD_ID} must be an integer, got {raw_guild!r}") from exc
    return BotConfig(token=token, guild_id=guild_id)
