"""Command registry: every command module registers itself here.

Adding a command group = new module with a ``register(tree)`` + one line below.
"""

from __future__ import annotations

from discord import app_commands

from bot.commands import fun, music, utility


def register_all(tree: app_commands.CommandTree) -> None:
    utility.register(tree)
    music.register(tree)
    fun.register(tree)
