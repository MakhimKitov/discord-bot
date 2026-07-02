"""Coinflip logic — pure function, no Discord."""

import random

from bot.commands.utility import flip_coin


def test_heads_reachable():
    results = {flip_coin(random.Random(seed)) for seed in range(100)}
    assert "Heads" in results


def test_tails_reachable():
    results = {flip_coin(random.Random(seed)) for seed in range(100)}
    assert "Tails" in results


def test_only_valid_outcomes():
    results = {flip_coin(random.Random(seed)) for seed in range(100)}
    assert results == {"Heads", "Tails"}


def test_deterministic_with_seed():
    assert flip_coin(random.Random(42)) == flip_coin(random.Random(42))
