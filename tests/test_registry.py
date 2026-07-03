"""The command registry wires every command into the tree (offline — no gateway)."""

import discord
from bot.commands import register_all
from discord import app_commands


def test_all_commands_registered():
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)
    register_all(tree)
    assert {command.name for command in tree.get_commands()} == {
        "ping",
        "roll",
        "choose",
        "coinflip",
        "casino",
    }
