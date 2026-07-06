"""``/lol`` meme picker — pure logic (no network) plus a stubbed-interaction
drive of the real command coroutine, per tests/test_music.py's pattern
(FakeResponse/FakeFollowup standing in for discord.Interaction)."""

from __future__ import annotations

import asyncio
import random

import pytest
from bot.commands import fun
from bot.commands.fun import (
    MemeFetchError,
    MemeItem,
    NO_MEME_MESSAGE,
    fetch_meme,
    lol,
    parse_memes,
    pick_safe_meme,
)


# --- parse_memes: payload shapes -------------------------------------------


def test_parse_memes_handles_batch_shape():
    payload = {
        "count": 2,
        "memes": [
            {"url": "https://i.redd.it/a.png", "title": "A", "nsfw": False, "spoiler": False},
            {"url": "https://i.redd.it/b.png", "title": "B", "nsfw": True, "spoiler": False},
        ],
    }
    items = parse_memes(payload)
    assert items == [
        MemeItem(url="https://i.redd.it/a.png", title="A", nsfw=False, spoiler=False),
        MemeItem(url="https://i.redd.it/b.png", title="B", nsfw=True, spoiler=False),
    ]


def test_parse_memes_handles_single_item_shape():
    payload = {"url": "https://i.redd.it/c.png", "title": "C", "nsfw": False, "spoiler": False}
    assert parse_memes(payload) == [
        MemeItem(url="https://i.redd.it/c.png", title="C", nsfw=False, spoiler=False)
    ]


def test_parse_memes_drops_entries_without_a_url():
    payload = {"memes": [{"title": "no url", "nsfw": False, "spoiler": False}]}
    assert parse_memes(payload) == []


def test_parse_memes_empty_batch():
    assert parse_memes({"count": 0, "memes": []}) == []


# --- pick_safe_meme: FR-4 (nsfw/spoiler filtering) --------------------------


def test_pick_safe_meme_excludes_nsfw_and_spoiler():
    items = [
        MemeItem(url="https://x/1", title="nsfw", nsfw=True, spoiler=False),
        MemeItem(url="https://x/2", title="spoiler", nsfw=False, spoiler=True),
        MemeItem(url="https://x/3", title="safe", nsfw=False, spoiler=False),
    ]
    for seed in range(20):
        picked = pick_safe_meme(items, rng=random.Random(seed))
        assert picked.title == "safe"


def test_pick_safe_meme_returns_none_when_everything_is_unsafe():
    items = [
        MemeItem(url="https://x/1", title="nsfw", nsfw=True, spoiler=False),
        MemeItem(url="https://x/2", title="spoiler", nsfw=False, spoiler=True),
    ]
    assert pick_safe_meme(items, rng=random.Random(0)) is None


def test_pick_safe_meme_returns_none_for_empty_input():
    assert pick_safe_meme([], rng=random.Random(0)) is None


# --- pick_safe_meme: FR-3 (randomness across repeated picks) ---------------


def test_pick_safe_meme_yields_different_picks_across_seeds():
    items = [
        MemeItem(url=f"https://x/{i}", title=str(i), nsfw=False, spoiler=False) for i in range(5)
    ]
    picks = {pick_safe_meme(items, rng=random.Random(seed)).url for seed in range(30)}
    assert len(picks) > 1


# --- fetch_meme: success, FR-4 exclusion end to end, and FR-5 failure modes -


def test_fetch_meme_returns_a_safe_pick():
    async def fake_fetch_json(url):
        return {
            "memes": [
                {"url": "https://x/safe", "title": "ok", "nsfw": False, "spoiler": False},
            ]
        }

    meme = asyncio.run(fetch_meme(fetch_json=fake_fetch_json, rng=random.Random(0)))
    assert meme.url == "https://x/safe"


def test_fetch_meme_excludes_nsfw_and_spoiler_from_the_batch():
    async def fake_fetch_json(url):
        return {
            "memes": [
                {"url": "https://x/nsfw", "title": "bad1", "nsfw": True, "spoiler": False},
                {"url": "https://x/spoiler", "title": "bad2", "nsfw": False, "spoiler": True},
                {"url": "https://x/safe", "title": "ok", "nsfw": False, "spoiler": False},
            ]
        }

    for seed in range(20):
        meme = asyncio.run(fetch_meme(fetch_json=fake_fetch_json, rng=random.Random(seed)))
        assert meme.url == "https://x/safe"


def test_fetch_meme_raises_when_batch_is_entirely_unsafe():
    async def fake_fetch_json(url):
        return {"memes": [{"url": "https://x/nsfw", "title": "bad", "nsfw": True, "spoiler": False}]}

    with pytest.raises(MemeFetchError):
        asyncio.run(fetch_meme(fetch_json=fake_fetch_json))


def test_fetch_meme_raises_when_batch_is_empty():
    async def fake_fetch_json(url):
        return {"memes": []}

    with pytest.raises(MemeFetchError):
        asyncio.run(fetch_meme(fetch_json=fake_fetch_json))


def test_fetch_meme_wraps_source_exception_without_leaking_traceback():
    async def fake_fetch_json(url):
        raise TimeoutError("took too long")

    with pytest.raises(MemeFetchError) as exc_info:
        asyncio.run(fetch_meme(fetch_json=fake_fetch_json))
    assert "Traceback" not in str(exc_info.value)


def test_fetch_meme_raises_on_malformed_payload():
    async def fake_fetch_json(url):
        return "not a dict"

    with pytest.raises(MemeFetchError):
        asyncio.run(fetch_meme(fetch_json=fake_fetch_json))


# --- /lol command: interaction-stub drive, per tests/test_music.py ---------


class _FakeResponse:
    def __init__(self):
        self.deferred = False

    async def defer(self):
        self.deferred = True


class _FakeFollowup:
    def __init__(self):
        self.messages = []  # list of dicts: {"content":..., "embed":..., "ephemeral":...}

    async def send(self, content=None, *, embed=None, ephemeral=False):
        self.messages.append({"content": content, "embed": embed, "ephemeral": ephemeral})


class _FakeInteraction:
    def __init__(self):
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()


def test_lol_posts_public_reply_carrying_the_fetched_image(monkeypatch):
    """FR-2: the reply carries the fetched image, as a public (non-ephemeral) send."""

    async def fake_fetch_meme():
        return MemeItem(url="https://i.redd.it/xyz.png", title="Funny", nsfw=False, spoiler=False)

    monkeypatch.setattr(fun, "fetch_meme", fake_fetch_meme)

    interaction = _FakeInteraction()
    asyncio.run(lol.callback(interaction))

    assert interaction.response.deferred
    assert len(interaction.followup.messages) == 1
    sent = interaction.followup.messages[0]
    assert sent["ephemeral"] is False
    assert sent["embed"].image.url == "https://i.redd.it/xyz.png"


def test_lol_replies_ephemeral_friendly_error_on_fetch_failure(monkeypatch):
    """FR-5: source error -> ephemeral friendly error, no exception raised."""

    async def fake_fetch_meme():
        raise MemeFetchError("boom")

    monkeypatch.setattr(fun, "fetch_meme", fake_fetch_meme)

    interaction = _FakeInteraction()
    asyncio.run(lol.callback(interaction))  # must not raise

    assert interaction.response.deferred
    assert interaction.followup.messages == [
        {"content": NO_MEME_MESSAGE, "embed": None, "ephemeral": True}
    ]


def test_lol_replies_ephemeral_friendly_error_when_source_yields_nothing_usable(monkeypatch):
    """FR-5: empty result (everything filtered out) -> same friendly ephemeral path."""

    async def fake_fetch_meme():
        raise MemeFetchError("no safe-for-work meme found in the batch")

    monkeypatch.setattr(fun, "fetch_meme", fake_fetch_meme)

    interaction = _FakeInteraction()
    asyncio.run(lol.callback(interaction))

    assert interaction.followup.messages == [
        {"content": NO_MEME_MESSAGE, "embed": None, "ephemeral": True}
    ]
