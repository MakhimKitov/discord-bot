"""Fun commands with an external dependency: ``/lol`` (issue #21).

Meme selection is pure and unit-testable via an injected async ``fetch_json``
callable — mirrors ``bot.commands.music.resolve_track``'s injected ``extract``:
``parse_memes``/``pick_safe_meme`` need no network access to test, and
``fetch_meme`` itself is exercised with a fake ``fetch_json`` standing in for
the real HTTP call. The decorated command coroutine is a thin interaction
wrapper that defers, awaits the network call, and posts the result (or a
friendly ephemeral error).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Awaitable, Callable

import aiohttp
import discord
from discord import app_commands

log = logging.getLogger(__name__)

MEME_API_URL = "https://meme-api.com/gimme"
# Fetch a batch in one request rather than re-rolling with repeat calls to the
# source — keeps the external-service posture to "one request per invocation"
# (per issue #21) even though some of the batch may get filtered out below as
# NSFW/spoiler.
MEME_BATCH_SIZE = 10
FETCH_TIMEOUT_SECONDS = 5

NO_MEME_MESSAGE = "couldn't grab a meme right now — try again in a bit."


class MemeFetchError(Exception):
    """The meme source is unreachable, errored, or yielded nothing safe to post.

    Message is user-facing only via NO_MEME_MESSAGE (the command never shows
    this exception's text) — raised for every expected failure mode.
    """


@dataclass(slots=True)
class MemeItem:
    url: str
    title: str
    nsfw: bool
    spoiler: bool


def parse_memes(payload: dict) -> list[MemeItem]:
    """Extract MemeItems from a meme-api.com response.

    Handles both the batch shape (``{"memes": [...]}``, from
    ``/gimme/{count}``) and the single-item shape (bare ``/gimme``) the same
    API returns. Entries missing a usable ``url`` are dropped rather than
    raising.
    """
    raw_items = payload.get("memes") if "memes" in payload else [payload]
    items = []
    for raw in raw_items or []:
        url = raw.get("url")
        if not url:
            continue
        items.append(
            MemeItem(
                url=url,
                title=raw.get("title") or "",
                nsfw=bool(raw.get("nsfw")),
                spoiler=bool(raw.get("spoiler")),
            )
        )
    return items


def pick_safe_meme(items: list[MemeItem], rng: random.Random | None = None) -> MemeItem | None:
    """Filter out anything flagged nsfw/spoiler and randomly pick one of what's
    left — FR-4's re-roll, implemented as "never consider it" rather than a
    second network round-trip. None if every candidate was filtered out (or
    there were none to begin with)."""
    safe = [item for item in items if not item.nsfw and not item.spoiler]
    if not safe:
        return None
    rng = rng or random.Random()
    return rng.choice(safe)


async def _default_fetch_json(url: str) -> dict:
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json(content_type=None)


async def fetch_meme(
    *,
    fetch_json: Callable[[str], Awaitable[dict]] = _default_fetch_json,
    rng: random.Random | None = None,
) -> MemeItem:
    """Fetch a batch of memes and return one safe-for-work pick.

    Raises MemeFetchError — never lets an aiohttp/timeout/malformed-payload
    exception's traceback reach the caller — for every expected failure:
    unreachable source, non-2xx status, timeout, malformed payload, or a
    batch that turns out to be entirely NSFW/spoiler.
    """
    try:
        payload = await fetch_json(f"{MEME_API_URL}/{MEME_BATCH_SIZE}")
        items = parse_memes(payload)
    except MemeFetchError:
        raise
    except Exception as exc:  # aiohttp errors, asyncio.TimeoutError, bad JSON/shape
        raise MemeFetchError(f"couldn't fetch a meme: {exc}") from exc

    picked = pick_safe_meme(items, rng=rng)
    if picked is None:
        raise MemeFetchError("no safe-for-work meme found in the batch")
    return picked


@app_commands.command(description="Post a random funny image.")
async def lol(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    try:
        meme = await fetch_meme()
    except MemeFetchError as exc:
        log.info("lol failed: %s", exc)
        await interaction.followup.send(NO_MEME_MESSAGE, ephemeral=True)
        return
    embed = discord.Embed(title=meme.title or None)
    embed.set_image(url=meme.url)
    log.info("lol posted meme title=%r", meme.title)
    await interaction.followup.send(embed=embed)


def register(tree: app_commands.CommandTree) -> None:
    tree.add_command(lol)
