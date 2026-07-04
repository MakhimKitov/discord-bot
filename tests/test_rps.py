"""Rock-paper-scissors logic — pure functions, no Discord."""

import random
from collections import Counter

import pytest
from bot.commands.utility import (
    RPS_EMOJI,
    RPS_MOVES,
    bot_move,
    format_rps_reply,
    rps_outcome,
)

# Seeded draws (module's existing pattern, see test_casino.py / test_choose.py).
_ROCK_SEED = 1
_PAPER_SEED = 0
_SCISSORS_SEED = 5


def test_bot_move_is_deterministic_with_seed():
    assert bot_move(random.Random(_ROCK_SEED)) == "rock"
    assert bot_move(random.Random(_PAPER_SEED)) == "paper"
    assert bot_move(random.Random(_SCISSORS_SEED)) == "scissors"


def test_bot_move_only_draws_known_moves():
    for seed in range(300):
        assert bot_move(random.Random(seed)) in RPS_MOVES


def test_bot_move_distribution_is_roughly_uniform():
    # FR-2: over many seeded draws, each move lands close to a third.
    counts = Counter(bot_move(random.Random(seed)) for seed in range(3000))
    for move in RPS_MOVES:
        assert 0.28 < counts[move] / 3000 < 0.38


# -- outcome matrix (FR-3) ---------------------------------------------------


@pytest.mark.parametrize(
    "player,bot,expected",
    [
        ("rock", "scissors", "win"),
        ("scissors", "paper", "win"),
        ("paper", "rock", "win"),
        ("rock", "paper", "loss"),
        ("paper", "scissors", "loss"),
        ("scissors", "rock", "loss"),
        ("rock", "rock", "tie"),
        ("paper", "paper", "tie"),
        ("scissors", "scissors", "tie"),
    ],
)
def test_outcome_matrix(player, bot, expected):
    assert rps_outcome(player, bot) == expected


# -- reply format (FR-4) -----------------------------------------------------


def test_reply_format_win():
    assert format_rps_reply("rock", "scissors") == "🪨 vs ✂️ — you win!"


def test_reply_format_loss():
    assert format_rps_reply("rock", "paper") == "🪨 vs 📄 — you lose!"


def test_reply_format_tie():
    assert format_rps_reply("rock", "rock") == "🪨 vs 🪨 — tie!"


def test_emoji_map_covers_every_move():
    assert set(RPS_EMOJI) == set(RPS_MOVES)


# -- unknown move rejection (FR-5) -------------------------------------------


def test_unknown_player_move_rejects_with_friendly_message():
    with pytest.raises(ValueError, match="rock, paper, scissors"):
        rps_outcome("lizard", "rock")


def test_unknown_bot_move_rejects_with_friendly_message():
    with pytest.raises(ValueError, match="rock, paper, scissors"):
        rps_outcome("rock", "spock")


def test_unknown_move_in_reply_formatting_raises_not_tracebacks_elsewhere():
    # format_rps_reply delegates validation to rps_outcome — no KeyError from
    # the emoji lookup on a bad move.
    with pytest.raises(ValueError, match="rock, paper, scissors"):
        format_rps_reply("lizard", "rock")
