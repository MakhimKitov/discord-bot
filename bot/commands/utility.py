"""Utility slash commands: /ping, /roll, /choose, /coinflip, /casino.

Command logic lives in pure functions (parse_dice, roll_dice, parse_weighted_option,
pick, flip_coin, spin_reels) so it is unit-testable without a Discord connection; the
decorated coroutines are thin interaction wrappers.
"""

from __future__ import annotations

import random
import re
from collections import Counter

import discord
from discord import app_commands

MAX_COUNT = 20
MAX_SIDES = 1000
MIN_WEIGHT = 1
MAX_WEIGHT = 100

_DICE_RE = re.compile(r"(\d+)d(\d+)", re.IGNORECASE)

CASINO_SYMBOLS = ("🍒", "🍋", "🔔", "⭐", "💎")
# Fixed draw weights, strictly descending from most to least common — 🍒 is the
# workhorse symbol, 💎 is the rare jackpot symbol. Values are the dev's choice
# per #5; only the strictly-descending ordering is load-bearing.
CASINO_WEIGHTS = (50, 25, 13, 7, 5)


def parse_dice(spec: str) -> tuple[int, int]:
    """Parse strict ``NdM`` notation (e.g. ``2d6``) into (count, sides).

    Both ``N`` and ``M`` must be present as digit runs — there's no positional
    default for an omitted count (``d20`` is rejected, not read as ``1d20``);
    the ``/roll`` command's own default (``1d6``) only applies when the whole
    option is omitted. ``d`` is case-insensitive and surrounding whitespace is
    tolerated.
    """
    raw = spec.strip()
    match = _DICE_RE.fullmatch(raw)
    if not match:
        raise ValueError(
            f"can't read {spec!r} — use NdM, like 2d6 "
            f"(1–{MAX_COUNT} dice, 2–{MAX_SIDES} sides)"
        )
    count, sides = int(match.group(1)), int(match.group(2))
    if not 1 <= count <= MAX_COUNT:
        raise ValueError(f"count must be 1–{MAX_COUNT} (got {count}) — example: 2d6")
    if not 2 <= sides <= MAX_SIDES:
        raise ValueError(f"sides must be 2–{MAX_SIDES} (got {sides}) — example: 2d6")
    return count, sides


def roll_dice(count: int, sides: int, rng: random.Random | None = None) -> list[int]:
    rng = rng or random.Random()
    return [rng.randint(1, sides) for _ in range(count)]


def format_roll_reply(count: int, sides: int, rolls: list[int]) -> str:
    """Render the individual rolls and, for more than one die, the total —
    ``🎲 2d6 → 4 + 6 = 10`` or, for a single die, ``🎲 1d6 → 5``."""
    detail = " + ".join(str(r) for r in rolls)
    if len(rolls) == 1:
        return f"🎲 {count}d{sides} → {detail}"
    return f"🎲 {count}d{sides} → {detail} = {sum(rolls)}"


def parse_weighted_option(entry: str) -> tuple[str, int]:
    """Split one ``/choose`` option on its *last* colon to find an optional
    trailing integer weight.

    If everything after the last colon is pure digits (whitespace-tolerant),
    it's a weight and must resolve to ``MIN_WEIGHT``–``MAX_WEIGHT`` with
    non-empty option text on the left; otherwise the colon is just literal
    text (``red:ish``, ``pizza:2.5``) and the option defaults to weight 1.
    """
    text, sep, suffix = entry.rpartition(":")
    stripped_suffix = suffix.strip()
    if sep and stripped_suffix.isascii() and stripped_suffix.isdigit():
        option, weight = text.strip(), int(stripped_suffix)
        if not option:
            raise ValueError(
                f"a weight needs option text — use option:N, like pizza:3 "
                f"(N is {MIN_WEIGHT}–{MAX_WEIGHT})"
            )
        if not MIN_WEIGHT <= weight <= MAX_WEIGHT:
            raise ValueError(
                f"weight must be {MIN_WEIGHT}–{MAX_WEIGHT} (got {weight}) — "
                f"use option:N, like pizza:3"
            )
        return option, weight
    return entry, 1


def pick(options: str, rng: random.Random | None = None) -> str:
    """Pick one entry from a comma-separated list, honoring an optional
    trailing ``:N`` weight per option (default weight 1 when omitted)."""
    entries = [entry.strip() for entry in options.split(",") if entry.strip()]
    if not entries:
        raise ValueError("give me options, comma-separated: red, green, blue")
    parsed = [parse_weighted_option(entry) for entry in entries]
    rng = rng or random.Random()
    return rng.choices(
        [option for option, _ in parsed],
        weights=[weight for _, weight in parsed],
    )[0]


def flip_coin(rng: random.Random | None = None) -> str:
    """Return ``'Heads'`` or ``'Tails'`` (~49.5 % each) or ``'CLOWNED'`` (~1 % easter egg)."""
    rng = rng or random.Random()
    return rng.choices(("Heads", "Tails", "CLOWNED"), weights=(99, 99, 2))[0]


def spin_reels(rng: random.Random | None = None) -> tuple[str, str, str]:
    """Draw three reel symbols, independently, weighted by CASINO_WEIGHTS —
    common symbols (🍒) dominate, rare ones (💎) show up seldom."""
    rng = rng or random.Random()
    symbol1, symbol2, symbol3 = rng.choices(CASINO_SYMBOLS, weights=CASINO_WEIGHTS, k=3)
    return (symbol1, symbol2, symbol3)


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
    await interaction.response.send_message(format_roll_reply(count, sides, rolls))


@app_commands.command(
    description="Pick one option from a comma-separated list; add :N to weight one."
)
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
