"""Voice foundation logic — pure functions, no Discord/network (#17, spec 0002 slice 1).

Covers query classification, playlist-URL rejection, and resolution's
rejection paths via an injected fake extractor (no real yt-dlp/network call).
The decorated command coroutines are integration surface, covered by the
platform's E2E tester per TESTING.md, not here.
"""

import asyncio

import pytest
from bot.commands.music import (
    PLAYLIST_REJECTED_MESSAGE,
    ResolutionError,
    _idle_watch,
    classify_query,
    is_playlist_only_url,
    resolve_track,
)


@pytest.mark.parametrize(
    "query, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "url"),
        ("http://youtu.be/dQw4w9WgXcQ", "url"),
        ("https://example.com/x", "url"),
        ("never gonna give you up", "search"),
        ("dQw4w9WgXcQ", "search"),
        ("www.youtube.com/watch?v=dQw4w9WgXcQ", "search"),  # no scheme -> not a URL
        ("", "search"),
    ],
)
def test_classify_query(query, expected):
    assert classify_query(query) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PLxyz",
        "https://youtube.com/playlist?list=PLxyz",
        "https://www.youtube.com/playlist?list=PLxyz&index=1",
    ],
)
def test_is_playlist_only_url_true_for_pure_playlist_links(url):
    assert is_playlist_only_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # plain video
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxyz",  # video within a playlist
        "https://youtu.be/dQw4w9WgXcQ",
        "not a url at all",
        "some playlist search text",
    ],
)
def test_is_playlist_only_url_false_otherwise(url):
    assert is_playlist_only_url(url) is False


def test_resolve_track_rejects_playlist_url_without_calling_extractor():
    calls = []

    def fake_extract(query):
        calls.append(query)
        return {"title": "should not be reached"}

    with pytest.raises(ResolutionError, match="playlist"):
        resolve_track("https://www.youtube.com/playlist?list=PLxyz", extract=fake_extract)
    assert calls == []


def test_resolve_track_returns_single_video_info():
    def fake_extract(query):
        return {
            "title": "Never Gonna Give You Up",
            "url": "https://cdn.example/stream.opus",
            "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }

    track = resolve_track("never gonna give you up", extract=fake_extract)
    assert track.title == "Never Gonna Give You Up"
    assert track.stream_url == "https://cdn.example/stream.opus"


def test_resolve_track_unwraps_search_result_entries():
    def fake_extract(query):
        return {
            "_type": "playlist",
            "entries": [
                {"title": "First result", "url": "https://cdn.example/first.opus"},
            ],
        }

    track = resolve_track("some search text", extract=fake_extract)
    assert track.title == "First result"


def test_resolve_track_raises_on_no_search_results():
    def fake_extract(query):
        return {"_type": "playlist", "entries": []}

    with pytest.raises(ResolutionError, match="no results"):
        resolve_track("obscure nonsense query", extract=fake_extract)


def test_resolve_track_raises_on_none_result():
    def fake_extract(query):
        return None

    with pytest.raises(ResolutionError, match="no results"):
        resolve_track("obscure nonsense query", extract=fake_extract)


def test_resolve_track_wraps_extractor_exception_without_traceback_leaking():
    def fake_extract(query):
        raise RuntimeError("Video unavailable: this content is age-restricted")

    with pytest.raises(ResolutionError, match="age-restricted"):
        resolve_track("https://www.youtube.com/watch?v=dead", extract=fake_extract)


def test_resolve_track_raises_when_no_stream_url_found():
    def fake_extract(query):
        return {"title": "No stream", "url": None}

    with pytest.raises(ResolutionError, match="playable audio stream"):
        resolve_track("some search text", extract=fake_extract)


def test_playlist_rejected_message_is_friendly_not_a_traceback():
    assert "Traceback" not in PLAYLIST_REJECTED_MESSAGE
    assert "playlist" in PLAYLIST_REJECTED_MESSAGE


def test_idle_watch_disconnects_when_still_idle_after_timeout():
    class FakeVoiceClient:
        def is_connected(self):
            return True

        def is_playing(self):
            return False

    fired = []

    async def on_timeout():
        fired.append(True)

    asyncio.run(_idle_watch(FakeVoiceClient(), guild_id=1, timeout=0, on_timeout=on_timeout))
    assert fired == [True]


def test_idle_watch_skips_disconnect_when_playing_resumed():
    class FakeVoiceClient:
        def is_connected(self):
            return True

        def is_playing(self):
            return True

    fired = []

    async def on_timeout():
        fired.append(True)

    asyncio.run(_idle_watch(FakeVoiceClient(), guild_id=1, timeout=0, on_timeout=on_timeout))
    assert fired == []
