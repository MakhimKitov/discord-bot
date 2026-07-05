"""Voice foundation logic — pure functions, no Discord/network (#17, spec 0002 slice 1).

Covers query classification, playlist-URL rejection, and resolution's
rejection paths via an injected fake extractor (no real yt-dlp/network call).
The decorated command coroutines are integration surface, covered by the
platform's E2E tester per TESTING.md, not here.
"""

import asyncio
import time

import pytest
from bot.commands import music
from bot.commands.music import (
    ALREADY_PLAYING_MESSAGE,
    PLAYLIST_REJECTED_MESSAGE,
    ResolutionError,
    _after_playback,
    _idle_watch,
    classify_query,
    is_playlist_only_url,
    play,
    resolve_track,
    stop,
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


def test_idle_timeout_disconnect_is_not_self_cancelled():
    """Regression: _idle_watch's own on_timeout callback resolves to
    _disconnect, whose first line is _cancel_idle_watch(guild_id) — if that
    still finds *this same currently-running task* registered in
    _idle_tasks, it cancels itself. Self-cancellation while running sets
    _must_cancel, so the next await _disconnect hits (voice_client.disconnect())
    raises CancelledError mid-flight, skipping cleanup and the "disconnected"
    log line — the exact squatting failure mode the idle timeout exists to
    prevent. Exercises the real _schedule_idle_watch/_idle_watch/_disconnect/
    _cancel_idle_watch wiring (not a mock), with a fake voice client whose
    disconnect() awaits internally so a mid-flight cancellation would land
    squarely on it and be observable.
    """

    class FakeVoiceClient:
        def __init__(self):
            self._connected = True
            self.cleaned_up = False

        def is_connected(self):
            return self._connected

        def is_playing(self):
            return False

        async def disconnect(self, force=False):
            await asyncio.sleep(0)  # stands in for discord.py's internal await
            self._connected = False
            self.cleaned_up = True  # stands in for VoiceClient.cleanup()

    async def scenario():
        vc = FakeVoiceClient()
        guild_id = 55
        music._schedule_idle_watch(
            vc, guild_id, lambda: music._disconnect(vc, guild_id, "idle timeout"), timeout=0
        )
        task = music._idle_tasks[guild_id]
        await task
        return vc, task

    vc, task = asyncio.run(scenario())
    assert not task.cancelled()
    assert vc.cleaned_up is True
    assert not vc.is_connected()
    assert 55 not in music._idle_tasks


# _after_playback is the `after=` callback discord.py invokes unconditionally
# whenever voice_client.play() stops — a natural end, a manual /stop, or a
# mid-stream error alike (discord/player.py's AudioPlayer.run() `finally`
# block calls it every time). These regression-test the three cases it must
# tell apart, each via a monkeypatched _disconnect so no real voice client or
# event loop plumbing is needed.


@pytest.fixture(autouse=True)
def _clean_manual_stops():
    """_manual_stops is module-level state shared across guilds/tests."""
    music._manual_stops.clear()
    yield
    music._manual_stops.clear()


def test_after_playback_natural_end_disconnects_with_track_ended_reason(monkeypatch):
    calls = []

    async def fake_disconnect(voice_client, guild_id, reason):
        calls.append((guild_id, reason))

    monkeypatch.setattr(music, "_disconnect", fake_disconnect)

    async def scenario():
        loop = asyncio.get_running_loop()
        _after_playback(object(), 42, loop, None)
        await asyncio.sleep(0)  # let the scheduled coroutine run

    asyncio.run(scenario())
    assert calls == [(42, "track ended")]


def test_after_playback_error_disconnects_with_playback_error_reason(monkeypatch):
    calls = []

    async def fake_disconnect(voice_client, guild_id, reason):
        calls.append((guild_id, reason))

    monkeypatch.setattr(music, "_disconnect", fake_disconnect)

    async def scenario():
        loop = asyncio.get_running_loop()
        _after_playback(object(), 3, loop, RuntimeError("ffmpeg died"))
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert calls == [(3, "playback error")]


def test_after_playback_manual_stop_does_not_reschedule_a_disconnect(monkeypatch):
    """The exact bug the machine reviewer flagged: without the manual-stop
    guard, a /stop-triggered after-callback would log "track ended" and fire
    a second, redundant disconnect on top of the one /stop already did."""
    calls = []

    async def fake_disconnect(voice_client, guild_id, reason):
        calls.append((guild_id, reason))

    monkeypatch.setattr(music, "_disconnect", fake_disconnect)
    music._manual_stops.add(7)

    async def scenario():
        loop = asyncio.get_running_loop()
        _after_playback(object(), 7, loop, None)
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert calls == []
    assert 7 not in music._manual_stops  # consumed, not leaked


def test_after_playback_clears_manual_stop_flag_even_on_error(monkeypatch):
    """A stale /stop flag must not survive to mislabel the *next* track's
    natural end as a no-op skip."""
    calls = []

    async def fake_disconnect(voice_client, guild_id, reason):
        calls.append((guild_id, reason))

    monkeypatch.setattr(music, "_disconnect", fake_disconnect)
    music._manual_stops.add(9)

    async def scenario():
        loop = asyncio.get_running_loop()
        _after_playback(object(), 9, loop, RuntimeError("boom"))
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert calls == [(9, "playback error")]
    assert 9 not in music._manual_stops


# --- /play concurrency (TOCTOU) regression, and reply-format regressions ----
#
# play() is normally integration surface (see module docstring) left to the
# platform's E2E tester, but the race below is specifically about *await
# timing inside play() itself*, which no amount of pure-function testing can
# exercise — so this one test drives the real command coroutine end to end
# against a minimal fake Discord object graph, with resolve_track/
# build_audio_source stubbed out to control the timing precisely.


class _FakeVoiceClient:
    def __init__(self, channel):
        self.channel = channel
        self._playing = False
        self._connected = True

    def is_playing(self):
        return self._playing

    def is_connected(self):
        return self._connected

    def play(self, source, after=None):
        if self._playing:
            raise RuntimeError("Already playing audio.")
        self._playing = True

    def stop(self):
        self._playing = False

    async def disconnect(self, force=False):
        self._connected = False

    async def move_to(self, channel):
        self.channel = channel


class _FakeGuild:
    def __init__(self, guild_id):
        self.id = guild_id
        self.voice_client = None


class _FakeChannel:
    def __init__(self, channel_id, guild):
        self.id = channel_id
        self.guild = guild

    async def connect(self):
        vc = _FakeVoiceClient(self)
        self.guild.voice_client = vc
        return vc


class _FakeVoiceState:
    def __init__(self, channel):
        self.channel = channel


class _FakeMember:
    def __init__(self, channel):
        self.voice = _FakeVoiceState(channel)


class _FakeResponse:
    def __init__(self):
        self.messages = []

    async def defer(self):
        pass

    async def send_message(self, content, ephemeral=False):
        self.messages.append((content, ephemeral))


class _FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content, ephemeral=False):
        self.messages.append((content, ephemeral))


class _FakeInteraction:
    def __init__(self, guild, channel, loop):
        self.guild = guild
        self.guild_id = guild.id
        self.user = _FakeMember(channel)
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()
        self.client = type("C", (), {"loop": loop})()


def test_play_rejects_concurrent_call_during_resolve_join_window(monkeypatch):
    """The exact race the machine reviewer flagged: two /play calls both pass
    the is_playing() guard (nothing playing yet), then one is held up inside
    resolve_track's await. Without the _starting marker, the second call
    would also pass the guard, and whichever reaches voice_client.play()
    second would raise "Already playing audio." and tear down the other's
    just-started session. With the marker, the second call is rejected
    immediately instead of racing."""
    music._starting.clear()
    resolve_entered = asyncio.Event()
    release_resolve = asyncio.Event()

    def fake_resolve_track(query):
        # Runs on a worker thread via asyncio.to_thread; loop.call_soon_threadsafe
        # is the safe way to flip an asyncio.Event from off-loop code.
        loop.call_soon_threadsafe(resolve_entered.set)
        while not release_resolve.is_set():
            time.sleep(0.001)
        return music.ResolvedTrack(title="Track", stream_url="https://x/y", webpage_url="https://x/y")

    monkeypatch.setattr(music, "resolve_track", fake_resolve_track)
    monkeypatch.setattr(music, "build_audio_source", lambda url: object())

    async def scenario():
        guild = _FakeGuild(1)
        channel = _FakeChannel(10, guild)
        interaction1 = _FakeInteraction(guild, channel, loop)
        interaction2 = _FakeInteraction(guild, channel, loop)

        task1 = asyncio.ensure_future(play.callback(interaction1, "song a"))
        await asyncio.wait_for(resolve_entered.wait(), timeout=2)

        # interaction1 is now inside the resolve window, holding the
        # _starting marker for this guild — interaction2 must be rejected
        # immediately, without ever calling resolve_track/build_audio_source.
        await play.callback(interaction2, "song b")

        release_resolve.set()
        await asyncio.wait_for(task1, timeout=2)
        music._cancel_idle_watch(guild.id)  # the 300s idle-watch task would otherwise outlive the test
        return interaction1, interaction2, guild

    loop = asyncio.new_event_loop()
    try:
        interaction1, interaction2, guild = loop.run_until_complete(scenario())
    finally:
        loop.close()

    assert interaction2.response.messages == [(ALREADY_PLAYING_MESSAGE, True)]
    assert guild.voice_client.is_playing()
    assert any("Now playing" in content for content, _ in interaction1.followup.messages)
    assert music._starting == set()


def test_play_success_reply_matches_pinned_format(monkeypatch):
    """specs/bot/commands.md pins '▶️ Now playing **<title>**' — U+25B6 U+FE0F,
    the colored triangle emoji, not the bare U+25B6 text-presentation glyph.

    Drives the real play() coroutine end to end against the fake Discord
    object graph above (resolve_track/build_audio_source stubbed only to
    avoid real network/ffmpeg) and asserts on the actual message play()
    sent — unlike an earlier version of this test that built the expected
    string from the same \\N{...} escapes inline and compared it to itself,
    which would pass even if music.py's own reply diverged from the pinned
    format, since it never invoked play() at all.
    """
    monkeypatch.setattr(
        music,
        "resolve_track",
        lambda query: music.ResolvedTrack(
            title="Test Track", stream_url="https://x/y", webpage_url="https://x/y"
        ),
    )
    monkeypatch.setattr(music, "build_audio_source", lambda url: object())

    async def scenario():
        guild = _FakeGuild(101)
        channel = _FakeChannel(1010, guild)
        interaction = _FakeInteraction(guild, channel, loop)
        await play.callback(interaction, "some query")
        music._cancel_idle_watch(guild.id)  # the 300s idle-watch task would otherwise outlive the test
        return interaction

    loop = asyncio.new_event_loop()
    try:
        interaction = loop.run_until_complete(scenario())
    finally:
        loop.close()

    assert interaction.followup.messages == [("▶️ Now playing **Test Track**", False)]


def test_stop_success_reply_matches_pinned_format():
    """specs/bot/commands.md pins '⏹️ Stopped.' — U+23F9 U+FE0F. Drives the
    real stop() coroutine against an already-connected, already-playing fake
    voice client (see test_play_success_reply_matches_pinned_format's
    docstring for why this must invoke the real code, not re-derive the
    expected string)."""

    async def scenario():
        guild = _FakeGuild(102)
        channel = _FakeChannel(1020, guild)
        vc = _FakeVoiceClient(channel)
        vc._playing = True
        guild.voice_client = vc
        interaction = _FakeInteraction(guild, channel, loop)
        await stop.callback(interaction)
        return interaction

    loop = asyncio.new_event_loop()
    try:
        interaction = loop.run_until_complete(scenario())
    finally:
        loop.close()

    assert interaction.response.messages == [("⏹️ Stopped.", False)]
