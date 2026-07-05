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
        "rps",
        "play",
        "stop",
    }


def test_rps_move_parameter_offers_exactly_three_choices():
    """FR-1: the 'move' parameter is a fixed three-choice picker, no free text."""
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)
    register_all(tree)
    move_param = next(p for p in tree.get_command("rps").parameters if p.name == "move")
    assert move_param.required
    assert {choice.value for choice in move_param.choices} == {"rock", "paper", "scissors"}
