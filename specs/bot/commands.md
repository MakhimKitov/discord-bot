# Command reference

The bot's current command surface: what is registered and how each command replies.

**This file is state, not log.** It must always match the running bot, and the
developer updates it as part of every change that touches the surface (operating
contract rule 7). The *decisions* behind each entry — rationale, bounds discussions,
rejected alternatives — live in the numbered specs (`specs/bot/NNNN-*.md`, the owner's
append-only decision log) and the issues cited per entry; this file records only what
is, never why.

The platform's tester judges the running bot against this reference: a registered
command missing here, an entry with no registered command, or a reply deviating from
a pinned format is a defect. Formats marked *(not pinned)* leave exact wording free —
deviations there are cosmetic, not defects.

## `/ping`

No parameters. Replies with the gateway latency in milliseconds *(exact format not
pinned)*. — 0001

## `/roll [dice]`

`dice` is optional plain-`NdM` notation; the `1d6` default applies only when the
option is omitted entirely. Parsing is strict: both counts must be present as digits
(`d20` is rejected, not read as `1d20`). Bounds: **1–20 dice**, **2–1000 sides**.
Reply: `🎲 2d6 → 4 + 6 = 10`; a single die drops the sum (`🎲 1d6 → 5`). Invalid
input rejects with a short friendly message. Modifiers (`2d6+3`), multiple dice
groups, and advantage/disadvantage are out of scope. — 0001, #7

## `/choose <options>`

`options` is a required comma-separated list. An option may carry a trailing `:N`
integer weight (`pizza:3, sushi` picks pizza 3× as often); unweighted options default
to weight 1, and weighted/unweighted mix freely. Recognition rule: split each option
on its *last* colon — if the trimmed remainder is pure digits it is a weight
(`pizza: 3` included), otherwise the colon is literal text (`red:ish`, `pizza:2.5`,
`ratio 3:x`). Weights must be **1–100**; an out-of-range weight or one attached to
empty option text (`:3`) rejects the whole command with an ephemeral message naming
the valid form and bounds. Reply: `I choose **pizza**` — the weight suffix never
leaks. — 0001, #9

## `/rps <move>`

`move` is required, exactly three Discord-UI choices (rock / paper / scissors — no
free text). The bot's counter-move is drawn uniformly from the same three; standard
rules, judged from the player's perspective. Reply is the player's move first with
the fixed emoji map (🪨 📄 ✂️): `🪨 vs ✂️ — you win!` / `🪨 vs 📄 — you lose!` /
`🪨 vs 🪨 — tie!`. A move outside the three (unreachable via the UI, reachable by
direct handler invocation) rejects with a friendly ephemeral message naming the valid
moves. No scores, series, or variants. — 0001, #11

## `/casino`

No parameters. Spins three reels drawn independently from the fixed symbol set
`🍒 🍋 🔔 ⭐ 💎` using the `CASINO_WEIGHTS` table (strictly descending from `🍒` to
`💎` — common symbols dominate, a `💎` jackpot is genuinely rare). Replies with the
reels plus exactly one outcome tier: **jackpot** (three of a kind), **small win**
(exactly two of a kind), or **bust** (all different) *(exact wording not pinned)*.
No bets, currency, balances, or per-user state. — 0001, #3, #5

## `/play <query>`

`query` is a YouTube URL or free-text search (first result). Joins the invoker's
current voice channel and plays the single resolved video's audio; a pure playlist
URL (`.../playlist?list=...`, no video id) is rejected rather than fanned out — a
watch URL that also carries a `list=` param plays just that video, ignoring the
list. Reply names the resolved title: `▶️ Now playing **<title>**`. Friendly
ephemeral rejections, never tracebacks: invoker not in a voice channel, something
already playing in the guild (no queue in slice 1 — `/play` rejects instead of
enqueuing), or resolution/extraction failure (dead URL, no search results,
geo/age-blocked, playlist link). Disconnects automatically when the track ends, or
after **300 s (5 min)** connected with nothing playing — the bot never squats in a
channel. — 0002, #17

## `/stop`

No parameters. Stops playback and disconnects from the voice channel. Reply:
`⏹️ Stopped.`. Ephemeral rejection (`nothing's playing right now.`) when the bot
isn't connected/playing in the guild. — 0002, #17
