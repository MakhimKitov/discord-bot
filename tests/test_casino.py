"""Casino (one-armed bandit) logic — pure functions, no Discord."""

import random
from collections import Counter

from bot.commands.utility import (
    CASINO_SYMBOLS,
    CASINO_WEIGHTS,
    casino_outcome,
    format_casino_reply,
    spin_reels,
)

# Known seeds covering all three outcome tiers (weighted draws — see #5).
_SMALL_WIN_SEED = 0  # ('🔔', '🔔', '🍒')
_BUST_SEED = 2  # ('💎', '⭐', '🍒')
_JACKPOT_SEED = 4  # ('🍒', '🍒', '🍒')


def test_weights_are_strictly_descending():
    """FR-1: common symbols must be strictly more likely than rarer ones."""
    assert len(CASINO_WEIGHTS) == len(CASINO_SYMBOLS)
    assert all(a > b for a, b in zip(CASINO_WEIGHTS, CASINO_WEIGHTS[1:]))


def test_common_symbol_drawn_strictly_more_than_rare_symbol():
    """FR-1: over many spins, the most common symbol beats the rarest one."""
    most_common_symbol = CASINO_SYMBOLS[0]
    rarest_symbol = CASINO_SYMBOLS[-1]
    counts = Counter()
    for seed in range(2000):
        counts.update(spin_reels(random.Random(seed)))
    assert counts[most_common_symbol] > counts[rarest_symbol]


def test_every_symbol_reachable_on_every_reel():
    reach = [set(), set(), set()]
    for seed in range(300):
        reels = spin_reels(random.Random(seed))
        for i, symbol in enumerate(reels):
            reach[i].add(symbol)
    assert all(reel_symbols == set(CASINO_SYMBOLS) for reel_symbols in reach)


def test_only_known_symbols_appear():
    for seed in range(300):
        reels = spin_reels(random.Random(seed))
        assert set(reels) <= set(CASINO_SYMBOLS)


def test_spin_returns_three_reels():
    reels = spin_reels(random.Random(0))
    assert len(reels) == 3


def test_deterministic_with_seed():
    assert spin_reels(random.Random(42)) == spin_reels(random.Random(42))


def test_jackpot_on_three_of_a_kind():
    reels = spin_reels(random.Random(_JACKPOT_SEED))
    assert len(set(reels)) == 1
    assert casino_outcome(reels) == "jackpot"


def test_small_win_on_exactly_two_of_a_kind():
    reels = spin_reels(random.Random(_SMALL_WIN_SEED))
    assert len(set(reels)) == 2
    assert casino_outcome(reels) == "small win"


def test_bust_on_all_different():
    reels = spin_reels(random.Random(_BUST_SEED))
    assert len(set(reels)) == 3
    assert casino_outcome(reels) == "bust"


def test_all_three_tiers_reachable():
    outcomes = {casino_outcome(spin_reels(random.Random(seed))) for seed in range(500)}
    assert outcomes == {"jackpot", "small win", "bust"}


def test_reply_shows_all_three_reels_and_jackpot_tier():
    reels = spin_reels(random.Random(_JACKPOT_SEED))
    reply = format_casino_reply(reels)
    for symbol in reels:
        assert symbol in reply
    assert "JACKPOT" in reply


def test_reply_shows_all_three_reels_and_small_win_tier():
    reels = spin_reels(random.Random(_SMALL_WIN_SEED))
    reply = format_casino_reply(reels)
    for symbol in reels:
        assert symbol in reply
    assert "small win" in reply


def test_reply_shows_all_three_reels_and_bust_tier():
    reels = spin_reels(random.Random(_BUST_SEED))
    reply = format_casino_reply(reels)
    for symbol in reels:
        assert symbol in reply
    assert "bust" in reply


def test_outcome_tiers_have_visibly_distinct_text():
    jackpot_reply = format_casino_reply(spin_reels(random.Random(_JACKPOT_SEED)))
    small_win_reply = format_casino_reply(spin_reels(random.Random(_SMALL_WIN_SEED)))
    bust_reply = format_casino_reply(spin_reels(random.Random(_BUST_SEED)))
    tier_texts = {
        jackpot_reply.rsplit("—", 1)[1],
        small_win_reply.rsplit("—", 1)[1],
        bust_reply.rsplit("—", 1)[1],
    }
    assert len(tier_texts) == 3
