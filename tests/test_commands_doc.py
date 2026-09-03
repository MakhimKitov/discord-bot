"""specs/bot/commands.md is 'state, not log' — it must list every registered command.

Regression test for issue #23: /coinflip was live and registered but had no
entry in the command reference doc. This guards against the same drift for
any future command.
"""

import re
from pathlib import Path

import discord
from discord import app_commands

from bot.commands import register_all

COMMANDS_MD = Path(__file__).parent.parent / "specs" / "bot" / "commands.md"


def _documented_command_names() -> set[str]:
    text = COMMANDS_MD.read_text()
    # Section headers look like "## `/ping`" or "## `/roll [dice]`" or
    # "## `/choose <options>`" — pull the bare command name out of each.
    return set(re.findall(r"^## `/(\w+)", text, flags=re.MULTILINE))


def _registered_command_names() -> set[str]:
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)
    register_all(tree)
    return {command.name for command in tree.get_commands()}


def test_every_registered_command_is_documented():
    missing = _registered_command_names() - _documented_command_names()
    assert not missing, f"registered but undocumented in {COMMANDS_MD}: {missing}"


def test_every_documented_command_is_registered():
    stale = _documented_command_names() - _registered_command_names()
    assert not stale, f"documented in {COMMANDS_MD} but not registered: {stale}"
