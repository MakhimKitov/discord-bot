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

## Cleanup

Kill the bot process when done. Messages left in the test guild are fine — the guild
is disposable. Never delete the guild, its channels, or the application.
