---
env: [DISCORD_TOKEN, GUILD_ID]
tools: []
---

# E2E testing contract

How this product is tested end-to-end. The audience is the platform's **tester agent**
(a fresh burst with no other context); the frontmatter above is parsed by the platform
to know what to inject. Unit tests are not your job — CI runs them; you judge the
*running bot*.

## The sandbox

`DISCORD_TOKEN` is a **dedicated test application's** bot token and `GUILD_ID` an
**empty guild that exists only for testing** — both disposable by construction.
Everything you do must stay inside that guild. There is no production to protect, but
treat the boundary as absolute anyway: never interact with any other guild.

## Boot

```
uv sync
DISCORD_TOKEN=… GUILD_ID=… uv run python -m bot
```

Online signal: the log line `commands synced to guild <id>` (guild sync is instant;
without `GUILD_ID` global sync can take up to an hour — always set it). Expect it
within ~60 s of start. A boot that exits or never syncs is a defect, not a setup
problem to route around — report it.

## How to drive it

A Discord rule shapes everything here: **a bot cannot invoke another bot's slash
commands**, and automating a human user account violates Discord ToS. So E2E for this
bot means three layers, in order of value:

1. **Registration** — with the bot online, list the guild's application commands via
   Discord REST (`GET /applications/{app_id}/guilds/{guild_id}/commands`, authorized
   with the bot token). Every command `specs/bot/commands.md` promises must be
   registered with the described signature; extras and gaps are defects.
2. **Handler invocation, in-process** — import the command callbacks from
   `bot/commands/` and invoke them against a stubbed `discord.Interaction`, asserting
   the exact reply text/format `specs/bot/commands.md` pins (including ephemeral flags on
   rejections). This is the interaction surface the pure-function unit tests do not
   cover.
3. **Liveness** — the bot process stays up across the above; a traceback in its log
   during any scenario is a defect even if the reply looked right.

## Scenarios

Invent them from `specs/bot/commands.md` — the living command reference, the contract
for the registered surface and reply formats — and the numbered specs it cites
(`specs/bot/NNNN-*.md`, the owner's decision log), weighted toward whatever the PR under test changed. Happy path plus the
rejection paths the PRD promises friendly messages for. Deterministic seams (injectable
`rng`) are for unit tests — at this layer, assert format and bounds, not exact random
outcomes.

## Pass / fail

- Boot failure, missing/mismatched command registration, reply-format deviation from
  the command reference, unfriendly rejection (raw traceback text reaching the user), or a crash in
  the bot's log → **defect**, with the scenario and reproduction steps.
- Cosmetic wording differences the command reference does not pin → not a defect; note them in the
  verdict prose if worth a human glance.

## Voice E2E recipe (`/play` + `/stop`, spec 0002 slice 1)

The sandbox has no ears — audible sound is out of scope. "E2E" here means the real
path minus the speaker: real gateway session, real voice-channel connect, real
yt-dlp resolution, a real ffmpeg child process, `voice_client.is_playing()` holding
for ~10 s, a clean `/stop` disconnect, and no traceback in the bot's log. The guild
needs at least one voice channel (operator guarantee) — create one if none exists.

Drive the real command callbacks directly (`play.callback` / `stop.callback`, the
coroutines the decorators wrap) against a small stub `discord.Interaction`, with the
bot's own running `discord.Client` supplying the real guild/channel/voice objects.
Run this as a second script *while the bot process from "Boot" above is running*,
logged in with the same token (Discord allows multiple gateway sessions per bot):

```python
# save as e2e_voice.py, then: DISCORD_TOKEN=… GUILD_ID=… uv run python e2e_voice.py
import asyncio, os
import discord
from bot.commands.music import play, stop

class StubResponse:
    async def defer(self): print("[stub] deferred")
    async def send_message(self, content, ephemeral=False):
        print(f"[stub] response.send_message(ephemeral={ephemeral}): {content}")

class StubFollowup:
    async def send(self, content, ephemeral=False):
        print(f"[stub] followup.send(ephemeral={ephemeral}): {content}")

class StubVoiceState:
    def __init__(self, channel): self.channel = channel

class StubMember:
    """A plain stand-in, not a real discord.Member — Member.voice is a
    read-only property with no setter, so it can't be poked directly."""
    def __init__(self, channel): self.voice = StubVoiceState(channel)

class StubInteraction:
    def __init__(self, client, guild, channel):
        self.client, self.guild, self.guild_id = client, guild, guild.id
        self.user = StubMember(channel)  # only .voice.channel is read by play()/stop()
        self.response, self.followup = StubResponse(), StubFollowup()

async def main():
    client = discord.Client(intents=discord.Intents.default())
    @client.event
    async def on_ready():
        guild = discord.utils.get(client.guilds, id=int(os.environ["GUILD_ID"]))
        channel = next(c for c in guild.voice_channels)  # or a specific channel id
        interaction = StubInteraction(client, guild, channel)

        await play.callback(interaction, query="ytsearch1:royalty free test tone")
        await asyncio.sleep(10)
        vc = guild.voice_client
        print("is_playing after ~10s:", vc.is_playing())  # expect True
        assert vc.is_playing()

        await stop.callback(interaction)
        await asyncio.sleep(1)
        print("voice_client after /stop:", guild.voice_client)  # expect None
        assert guild.voice_client is None or not guild.voice_client.is_connected()

        await client.close()
    await client.start(os.environ["DISCORD_TOKEN"])

asyncio.run(main())
```

Watch the bot process's own stdout while this runs — the lifecycle must be visible
there per spec 0002: `resolving query=...`, `joined channel=...`, `playback started
title=...`, `stopped by user` / `disconnected from guild=...`, and for the rejection
paths, one `... rejected: ...` line per rejection. A traceback anywhere in that log
during the run is a defect even if the script's own asserts passed.

Rejection scenarios to also exercise (each should reply ephemeral, no traceback):
not in a voice channel (build the interaction with `StubMember(channel=None)`),
already playing (call `/play` again while the first is still going), and a bad
query (e.g. a playlist URL, or a garbage URL that fails extraction).

## Cleanup

Kill the bot process when done. Messages left in the test guild are fine — the guild
is disposable. Never delete the guild, its channels, or the application.
