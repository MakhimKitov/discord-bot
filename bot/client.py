"""The bot client: default intents (no message content), slash commands only."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from bot.commands import register_all
from bot.config import BotConfig

log = logging.getLogger(__name__)


class UtilityBot(discord.Client):
    def __init__(self, config: BotConfig) -> None:
        super().__init__(intents=discord.Intents.default())
        self.config = config
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        register_all(self.tree)
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("commands synced to guild %s", self.config.guild_id)
        else:
            await self.tree.sync()
            log.info("commands synced globally (may take up to an hour to appear)")

    async def on_ready(self) -> None:
        log.info("logged in as %s (id=%s)", self.user, self.user and self.user.id)
