"""Utility slash commands: /ping, /roll, /choose, /coinflip, /casino.

Command logic lives in pure functions (parse_dice, roll_dice, pick, flip_coin,
spin_reels) so it is unit-testable without a Discord connection; the decorated
coroutines are thin interaction wrappers.
"""

from __future__ import annotations

import random
from collections import Counter

import discord
from discord import app_commands

MAX_COUNT = 100
MAX_SIDES = 1000

CASINO_SYMBOLS = ("🍒", "🍋", "🔔", "⭐", "💎")


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
    """Return ``'Heads'`` or ``'Tails'`` (~49.5 % each) or ``'CLOWNED'`` (~1 % easter egg)."""
    rng = rng or random.Random()
    return rng.choices(("Heads", "Tails", "CLOWNED"), weights=(99, 99, 2))[0]


def spin_reels(rng: random.Random | None = None) -> tuple[str, str, str]:
    """Draw three reel symbols, independently and uniformly, from CASINO_SYMBOLS."""
    rng = rng or random.Random()
    return (
        rng.choice(CASINO_SYMBOLS),
        rng.choice(CASINO_SYMBOLS),
        rng.choice(CASINO_SYMBOLS),
    )


def casino_outcome(reels: tuple[str, str, str]) -> str:
    """Classify a spin as ``'jackpot'`` (3 of a kind), ``'small win'`` (2 of a
    kind), or ``'bust'`` (all different)."""
    counts = Counter(reels)
    top = counts.most_common(1)[0][1]
    if top == 3:
        return "jackpot"
    if top == 2:
        return "small win"
    return "bust"


_CASINO_OUTCOME_TEXT = {
    "jackpot": "JACKPOT! 🎉",
    "small win": "small win!",
    "bust": "bust.",
}


def format_casino_reply(reels: tuple[str, str, str]) -> str:
    """Render the three reels plus the outcome tier's distinct response text."""
    outcome = casino_outcome(reels)
    reel_display = f"{reels[0]} | {reels[1]} | {reels[2]}"
    return f"🎰 {reel_display} — {_CASINO_OUTCOME_TEXT[outcome]}"


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
    if result == "CLOWNED":
        await interaction.response.send_message("🤡 YOU WERE CLOWNED")
    else:
        await interaction.response.send_message(f"🪙 {result}!")


@app_commands.command(description="Spin the one-armed bandit — three reels, one outcome.")
async def casino(interaction: discord.Interaction) -> None:
    reels = spin_reels()
    await interaction.response.send_message(format_casino_reply(reels))


def register(tree: app_commands.CommandTree) -> None:
    tree.add_command(ping)
    tree.add_command(roll)
    tree.add_command(choose)
    tree.add_command(coinflip)
    tree.add_command(casino)
