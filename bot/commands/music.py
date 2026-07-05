"""Voice foundation: ``/play <query>`` and ``/stop`` (spec 0002, slice 1).

Resolution/classification logic is pure and unit-testable without a Discord
connection or network access (``classify_query``, ``is_playlist_only_url``,
``resolve_track`` with an injected extractor). The decorated coroutines are
thin interaction wrappers that own the voice-client lifecycle: join, play,
track-end/idle disconnect.

No queue here (slice 2) — a guild with something already playing rejects a
second ``/play`` instead of enqueuing.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import stat
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal
from urllib.parse import parse_qs, urlparse

import discord
from discord import app_commands
from static_ffmpeg import run as static_ffmpeg_run
from yt_dlp import YoutubeDL

log = logging.getLogger(__name__)

# Idle-connected disconnect: a guard against squatting in a channel if playback
# never actually starts (e.g. the audio source stalls before is_playing() ever
# reports it left the "idle" state) or is otherwise interrupted before the
# after-callback fires. The common path — a track that ends normally — is
# already disconnected immediately by _after_playback, well under this.
IDLE_TIMEOUT_SECONDS = 300

NOT_IN_VOICE_MESSAGE = "join a voice channel first — I play into whichever one you're in."
ALREADY_PLAYING_MESSAGE = "something's already playing here — `/stop` it first (queueing isn't supported yet)."
NOTHING_PLAYING_MESSAGE = "nothing's playing right now."
JOIN_FAILED_MESSAGE = "couldn't join your voice channel — try again in a moment."
PLAYLIST_REJECTED_MESSAGE = (
    "that's a playlist link — I only play a single video. Paste a video URL instead."
)

_YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "default_search": "ytsearch1",
    "quiet": True,
    "no_warnings": True,
    "logtostderr": False,
}

# yt-dlp streams need ffmpeg to reconnect through transient network hiccups
# without dying silently mid-track.
_FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"


class ResolutionError(Exception):
    """A query could not be resolved to a single playable video.

    Message is user-facing and friendly — raised only for expected failure
    modes (dead URL, no search results, geo/age block, playlist link).
    """


@dataclass(slots=True)
class ResolvedTrack:
    title: str
    stream_url: str
    webpage_url: str


def classify_query(query: str) -> Literal["url", "search"]:
    """A query is a URL if it parses with an http(s) scheme and a host;
    anything else (including bare domains with no scheme) is a search term
    handed to yt-dlp's default-search."""
    parsed = urlparse(query.strip())
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return "url"
    return "search"


def is_playlist_only_url(query: str) -> bool:
    """True for a URL that names a playlist with no specific video — e.g.
    ``.../playlist?list=...`` — which slice 1 must reject rather than fan out.

    A watch URL that merely carries a playlist *context* alongside a video id
    (``.../watch?v=X&list=Y``) is NOT playlist-only: yt-dlp's ``noplaylist``
    option resolves that to the single video ``X``, per spec 0002.
    """
    if classify_query(query) != "url":
        return False
    parsed = urlparse(query.strip())
    if parsed.path.rstrip("/") == "/playlist":
        return True
    params = parse_qs(parsed.query)
    return "list" in params and "v" not in params


def _default_extract(query: str) -> dict | None:
    with YoutubeDL(_YDL_OPTS) as ydl:
        return ydl.extract_info(query, download=False)


def resolve_track(
    query: str,
    *,
    extract: Callable[[str], dict | None] = _default_extract,
) -> ResolvedTrack:
    """Resolve a URL or search query to a single playable track.

    Raises ResolutionError with a friendly message for every expected
    failure: playlist links, dead URLs, no search results, extraction
    failures (geo/age-blocked, etc.) — never lets a yt-dlp exception's
    traceback reach the caller.
    """
    if is_playlist_only_url(query):
        raise ResolutionError(PLAYLIST_REJECTED_MESSAGE)

    try:
        info = extract(query)
    except Exception as exc:  # yt-dlp raises its own DownloadError subclasses
        raise ResolutionError(
            f"couldn't play that — {exc}" if str(exc) else "couldn't play that — extraction failed"
        ) from exc

    if info is None:
        raise ResolutionError("no results found")

    if info.get("_type") == "playlist" or "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise ResolutionError("no results found")
        info = entries[0]

    stream_url = info.get("url")
    if not stream_url:
        raise ResolutionError("couldn't find a playable audio stream for that")

    title = info.get("title") or "Unknown title"
    webpage_url = info.get("webpage_url") or query
    return ResolvedTrack(title=title, stream_url=stream_url, webpage_url=webpage_url)


_ffmpeg_executable_cache: str | None = None


def _ensure_executable(path: str) -> None:
    """Belt-and-braces on top of static-ffmpeg's own permission fix: on at
    least one overlay filesystem observed in development, the exec bit it
    sets on the freshly-extracted binary didn't persist, and the subsequent
    subprocess spawn raised a bare PermissionError. Best-effort — if chmod
    itself isn't permitted here, leave it to the subprocess call to surface
    the real problem."""
    try:
        if not os.access(path, os.X_OK):
            mode = os.stat(path).st_mode
            os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _ffmpeg_executable() -> str:
    """Path to a working ffmpeg binary, fetched on first use and cached.

    static-ffmpeg carries the binary as a Python dependency (downloading a
    platform build on first run, then reusing it) so `uv sync` alone is
    enough — no system ffmpeg/libopus package required (spec 0002
    constraints). ffmpeg does the Opus encoding, so libopus itself is never
    loaded by this process.
    """
    global _ffmpeg_executable_cache
    if _ffmpeg_executable_cache is None:
        ffmpeg_exe, _ffprobe_exe = static_ffmpeg_run.get_or_fetch_platform_executables_else_raise()
        _ensure_executable(ffmpeg_exe)
        _ffmpeg_executable_cache = ffmpeg_exe
    return _ffmpeg_executable_cache


def build_audio_source(stream_url: str) -> discord.FFmpegOpusAudio:
    return discord.FFmpegOpusAudio(
        stream_url,
        executable=_ffmpeg_executable(),
        before_options=_FFMPEG_BEFORE_OPTIONS,
    )


# Per-guild idle-disconnect watchdog tasks, keyed by guild id.
_idle_tasks: dict[int, asyncio.Task] = {}


def _cancel_idle_watch(guild_id: int) -> None:
    task = _idle_tasks.pop(guild_id, None)
    if task and not task.done():
        task.cancel()


async def _idle_watch(
    voice_client: discord.VoiceClient,
    guild_id: int,
    timeout: float,
    on_timeout: Callable[[], Awaitable[None]],
) -> None:
    await asyncio.sleep(timeout)
    if voice_client.is_connected() and not voice_client.is_playing():
        log.info("idle timeout (%ss) in guild=%s, disconnecting", timeout, guild_id)
        await on_timeout()


def _schedule_idle_watch(
    voice_client: discord.VoiceClient,
    guild_id: int,
    on_timeout: Callable[[], Awaitable[None]],
    timeout: float = IDLE_TIMEOUT_SECONDS,
) -> None:
    _cancel_idle_watch(guild_id)
    _idle_tasks[guild_id] = asyncio.ensure_future(
        _idle_watch(voice_client, guild_id, timeout, on_timeout)
    )


async def _disconnect(voice_client: discord.VoiceClient, guild_id: int, reason: str) -> None:
    _cancel_idle_watch(guild_id)
    if not voice_client.is_connected():
        return
    await voice_client.disconnect()
    log.info("disconnected from guild=%s (%s)", guild_id, reason)


# Guild ids for which /play has passed the "already playing" guard and is
# resolving/joining/building the audio source but hasn't reached
# voice_client.play() yet. Without this, the guard's is_playing() read is a
# point-in-time check with two awaits (resolve_track's network call,
# build_audio_source spawning ffmpeg) between it and voice_client.play() —
# a second concurrent /play can read the same not-yet-playing state and race
# past the guard too. Whichever call reaches voice_client.play() second then
# raises "Already playing audio.", which the generic except around that call
# catches and tears down the *shared* guild voice_client — killing whichever
# request actually started, for an unrelated user. /play adds its guild id
# here immediately after the guard (no await in between, so no other task
# can interleave) and removes it in a finally covering the rest of the
# command, closing the window.
_starting: set[int] = set()

# Guild ids for which /stop just called voice_client.stop() itself. discord.py's
# AudioPlayer invokes the `after=` callback unconditionally in its run loop's
# `finally` block — on a natural end, a mid-stream error, AND a manual .stop() —
# so without this, a user-initiated /stop (or a playback error) would be
# misreported by _after_playback as "track ended" and would fire a second,
# redundant disconnect. /stop adds the guild id right before calling .stop();
# _after_playback consumes (pops) it to tell the three cases apart.
_manual_stops: set[int] = set()


def _after_playback(
    voice_client: discord.VoiceClient,
    guild_id: int,
    loop: asyncio.AbstractEventLoop,
    error: Exception | None,
) -> None:
    """The ``after=`` callback for ``voice_client.play()``.

    A standalone function (not a closure) so the three cases it must tell
    apart — natural end, user-initiated /stop, mid-stream error — are
    unit-testable without a real Discord connection. discord.py calls this
    unconditionally from the audio player thread whenever playback stops for
    *any* reason, so treating every call as "track ended" (as an earlier
    version of this file did) misreports a /stop or an error in the logs and
    fires a redundant disconnect.
    """
    manual_stop = guild_id in _manual_stops
    _manual_stops.discard(guild_id)
    if error:
        log.warning("playback error in guild=%s: %s", guild_id, error)
        reason = "playback error"
    elif manual_stop:
        # /stop already logged "stopped by user" and disconnected
        # synchronously — this is that same stop's after-callback firing,
        # not a natural end. Nothing left to do.
        return
    else:
        log.info("track ended in guild=%s", guild_id)
        reason = "track ended"
    asyncio.run_coroutine_threadsafe(_disconnect(voice_client, guild_id, reason), loop)


@app_commands.command(
    name="play", description="Play a YouTube video's audio in your voice channel (URL or search)."
)
async def play(interaction: discord.Interaction, query: str) -> None:
    guild = interaction.guild
    member = interaction.user
    voice_state = getattr(member, "voice", None)
    channel = voice_state.channel if voice_state else None
    if guild is None or channel is None:
        log.info("play rejected: user=%s not in a voice channel", member)
        await interaction.response.send_message(NOT_IN_VOICE_MESSAGE, ephemeral=True)
        return

    voice_client = guild.voice_client
    if (voice_client is not None and voice_client.is_playing()) or guild.id in _starting:
        log.info("play rejected: already playing in guild=%s", guild.id)
        await interaction.response.send_message(ALREADY_PLAYING_MESSAGE, ephemeral=True)
        return

    # No await between the guard above and this line — marking the guild
    # "starting" is atomic with the check from any other task's point of view.
    _starting.add(guild.id)
    try:
        await interaction.response.defer()
        log.info("resolving query=%r for guild=%s", query, guild.id)
        try:
            track = await asyncio.to_thread(resolve_track, query)
        except ResolutionError as exc:
            log.info("resolution rejected query=%r: %s", query, exc)
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            if voice_client is None or not voice_client.is_connected():
                voice_client = await channel.connect()
            elif voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
        except (discord.ClientException, asyncio.TimeoutError) as exc:
            log.warning("join failed for guild=%s channel=%s: %s", guild.id, channel, exc)
            await interaction.followup.send(JOIN_FAILED_MESSAGE, ephemeral=True)
            return
        log.info("joined channel=%s guild=%s", channel, guild.id)

        after_callback = functools.partial(
            _after_playback, voice_client, guild.id, interaction.client.loop
        )
        try:
            source = await asyncio.to_thread(build_audio_source, track.stream_url)
            voice_client.play(source, after=after_callback)
        except Exception as exc:
            log.warning("playback failed to start in guild=%s: %s", guild.id, exc)
            await _disconnect(voice_client, guild.id, "playback failed to start")
            await interaction.followup.send(
                "couldn't start playback for that — try again.", ephemeral=True
            )
            return

        log.info("playback started title=%r guild=%s", track.title, guild.id)
        _schedule_idle_watch(
            voice_client, guild.id, lambda: _disconnect(voice_client, guild.id, "idle timeout")
        )
        await interaction.followup.send(
            f"\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16} Now playing **{track.title}**"
        )
    finally:
        _starting.discard(guild.id)


@app_commands.command(name="stop", description="Stop playback and leave the voice channel.")
async def stop(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    voice_client = guild.voice_client if guild else None
    if voice_client is None or not voice_client.is_connected():
        log.info("stop rejected: nothing playing in guild=%s", guild.id if guild else None)
        await interaction.response.send_message(NOTHING_PLAYING_MESSAGE, ephemeral=True)
        return

    _manual_stops.add(guild.id)
    voice_client.stop()
    await _disconnect(voice_client, guild.id, "stopped by user")
    await interaction.response.send_message(
        "\N{BLACK SQUARE FOR STOP}\N{VARIATION SELECTOR-16} Stopped."
    )


def register(tree: app_commands.CommandTree) -> None:
    tree.add_command(play)
    tree.add_command(stop)
