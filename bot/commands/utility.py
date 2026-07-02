"""Utility slash commands: /ping, /roll, /choose.

Command logic lives in pure functions (parse_dice, roll_dice, pick) so it is
unit-testable without a Discord connection; the decorated coroutines are thin
interaction wrappers.
"""

from __future__ import annotations

import random

import discord
from discord import app_commands

MAX_COUNT = 100
MAX_SIDES = 1000


def parse_dice(spec: str) -> tuple[int, int]:
    """Parse ``NdM`` notation (``2d6``, ``d20``) into (count, sides)."""
    raw = spec.strip().lower()
    count_part, sep, sides_part = raw.partition("d")
    if not sep:
        raise ValueError(f"can't read {spec!r} — use NdM, like 2d6")
    try:
        count = int(count_part) if count_part else 1
        sides = int(sides_part)
    except ValueError:
        raise ValueError(f"can't read {spec!r} — use NdM, like 2d6") from None
    if not 1 <= count <= MAX_COUNT:
        raise ValueError(f"count must be 1–{MAX_COUNT}")
    if not 2 <= sides <= MAX_SIDES:
        raise ValueError(f"sides must be 2–{MAX_SIDES}")
    return count, sides


def roll_dice(count: int, sides: int, rng: random.Random | None = None) -> list[int]:
    rng = rng or random.Random()
    return [rng.randint(1, sides) for _ in range(count)]


def pick(options: str, rng: random.Random | None = None) -> str:
    """Pick one entry from a comma-separated list."""
    entries = [entry.strip() for entry in options.split(",") if entry.strip()]
    if not entries:
        raise ValueError("give me options, comma-separated: red, green, blue")
    rng = rng or random.Random()
    return rng.choice(entries)


def flip_coin(rng: random.Random | None = None) -> str:
    """Return ``'Heads'`` or ``'Tails'`` with equal probability."""
    rng = rng or random.Random()
    return rng.choice(("Heads", "Tails"))


@app_commands.command(description="Round-trip latency check.")
async def ping(interaction: discord.Interaction) -> None:
    latency_ms = round(interaction.client.latency * 1000)
    await interaction.response.send_message(f"Pong! `{latency_ms}ms`")


@app_commands.command(description="Roll dice in NdM notation (default 1d6).")
async def roll(interaction: discord.Interaction, dice: str = "1d6") -> None:
    try:
        count, sides = parse_dice(dice)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    rolls = roll_dice(count, sides)
    detail = " + ".join(str(r) for r in rolls)
    await interaction.response.send_message(f"🎲 {dice.strip()}: {detail} = **{sum(rolls)}**")


@app_commands.command(description="Pick one option from a comma-separated list.")
async def choose(interaction: discord.Interaction, options: str) -> None:
    try:
        choice = pick(options)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    await interaction.response.send_message(f"I choose **{choice}**")


@app_commands.command(description="Flip a coin — Heads or Tails.")
async def coinflip(interaction: discord.Interaction) -> None:
    result = flip_coin()
    await interaction.response.send_message(f"🪙 {result}!")


def register(tree: app_commands.CommandTree) -> None:
    tree.add_command(ping)
    tree.add_command(roll)
    tree.add_command(choose)
    tree.add_command(coinflip)
