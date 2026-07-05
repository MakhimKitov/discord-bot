# 0002 — Play music from YouTube (owner, 2026-07-05)

The capability-test task planned since 0001 ("Backlog"): voice-channel audio via
`discord.py` + `yt-dlp` + FFmpeg. This spec authorizes it in **two slices, one issue
each** — an issue references its slice; work outside the referenced slice is out of
scope for that PR.

## Slice 1 — voice foundation

Two commands:

- **`/play <query>`** — `query` is a YouTube URL **or** free-text search (first
  result). The bot joins the invoker's current voice channel and plays the single
  resolved video's audio. The reply names the resolved title, so the user can tell a
  bad search pick immediately. Friendly ephemeral rejections, never tracebacks, for:
  invoker not in a voice channel · something already playing · extraction/resolution
  failure (dead URL, no results, geo/age-blocked).
- **`/stop`** — stops playback and disconnects from the voice channel. Rejects
  politely when nothing is playing.

Lifecycle: when a track ends, or after being idle-connected for a few minutes with
nothing playing, the bot disconnects on its own — it never squats in a channel.
Exact reply wording and the idle timeout value are the developer's to pin in
`commands.md`.

## Slice 2 — queue (sketch; own issue, not authorized by a slice-1 issue)

`/play` while playing enqueues instead of rejecting; `/skip`, `/queue`, and
`/nowplaying` manage it. Details go in this spec's revision or a follow-up numbered
spec when slice 2 is filed.

## Constraints (both slices)

- **`uv sync` alone must yield a fully functional bot.** No system packages or
  libraries may be assumed — no apt, no brew, no preinstalled ffmpeg/libopus. If a
  binary is needed, carry it as a Python dependency. (A known-viable route, not a
  mandate: a static-ffmpeg wheel + `discord.py`'s `FFmpegOpusAudio`, which lets
  ffmpeg do the Opus encoding so libopus is never loaded.)
- YouTube only; **single videos only — a playlist URL must not fan out** (play the
  single video a watch-URL points at, reject pure playlist URLs politely).
- No new required configuration: `DISCORD_TOKEN` / `GUILD_ID` stay the whole env
  surface (0001 NFR).
- Logging to stdout (0001 NFR) — and the playback lifecycle must be visible there:
  resolve, join, play start/end, disconnect, and every rejection, with enough detail
  that a monitor could spot extraction breakage from logs alone.
- Slash commands only; no message-content intent (0001 holds).
- yt-dlp use is for this personal experiment's test guild — not a public
  redistribution service.

## Testability (part of the deliverable, not an afterthought)

The sandbox has no ears — audible sound is out of scope. E2E for voice means the
real path minus the speaker: real gateway session, real voice-channel connect, real
yt-dlp resolution, real ffmpeg child process, `voice_client.is_playing()` holding
for ~10 seconds, a clean `/stop` disconnect, and no traceback in the log.

- The slice-1 PR **must update `TESTING.md`** with a working recipe for the above —
  the tester burst reads the contract from the PR's own head, so the feature ships
  with the instructions for testing it. The recipe must let the tester drive the
  real command callbacks (a stubbed interaction whose `user.voice.channel` is a real
  channel object from the running client is acceptable).
- The sandbox guild provides at least one voice channel (operator guarantee); the
  tester may create one if none exists.

## Out of scope (both slices)

Pause/resume, volume, seek, loop/repeat, non-YouTube sources, playlists as queues,
DJ/permission roles, per-guild settings, and any persistence — a restart may forget
everything. Multi-guild playback isolation only needs to be *correct*, not tuned:
the bot lives in one guild today.
