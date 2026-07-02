"""Coinflip logic — pure function, no Discord."""

import random

from bot.commands.utility import flip_coin

# Seed 153 is known to produce the CLOWNED easter egg outcome.
_CLOWNED_SEED = 153


def test_heads_reachable():
    results = {flip_coin(random.Random(seed)) for seed in range(100)}
    assert "Heads" in results


def test_tails_reachable():
    results = {flip_coin(random.Random(seed)) for seed in range(100)}
    assert "Tails" in results


def test_clowned_reachable():
    assert flip_coin(random.Random(_CLOWNED_SEED)) == "CLOWNED"


def test_only_valid_outcomes():
    # Seeds 0-199 cover all three outcomes (seed 153 hits CLOWNED).
    results = {flip_coin(random.Random(seed)) for seed in range(200)}
    assert results == {"Heads", "Tails", "CLOWNED"}


def test_deterministic_with_seed():
    assert flip_coin(random.Random(42)) == flip_coin(random.Random(42))
