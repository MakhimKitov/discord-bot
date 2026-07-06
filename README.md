# discord-bot

A simple utility Discord bot — the **product** in an experiment in autonomous software
maintenance: an AI developer maintains this repo through GitHub issues and PRs, gated by
human review. The operating contract for anyone (or anything) working here is
[`CLAUDE.md`](CLAUDE.md); roles and review flow are in [`AGENTS.md`](AGENTS.md).

## Commands

| Command | What it does |
|---|---|
| `/ping` | Round-trip latency check |
| `/roll [dice]` | Roll dice in `NdM` notation (default `1d6`) |
| `/choose <options>` | Pick one from a comma-separated list |
| `/play <query>` | Play a YouTube video's audio (URL or search) in your voice channel |
| `/stop` | Stop playback and leave the voice channel |
| `/lol` | Post a random funny image (meme) |

The PRD lives in [`specs/bot/0001-prd.md`](specs/bot/0001-prd.md).

## Run

```bash
uv sync
cp .env.example .env    # add DISCORD_TOKEN (and optionally GUILD_ID for instant sync)
uv run python -m bot
```

The bot uses slash commands only, with default gateway intents (no message content).
Invite it with the `bot` + `applications.commands` scopes.

## Test

```bash
uv run pytest           # pure-logic tests, no network
```
