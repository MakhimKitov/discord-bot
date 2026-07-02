"""Dice logic — pure functions, no Discord."""

import random

import pytest
from bot.commands.utility import MAX_COUNT, MAX_SIDES, parse_dice, roll_dice


def test_parse_standard_notation():
    assert parse_dice("2d6") == (2, 6)
    assert parse_dice("1d20") == (1, 20)
    assert parse_dice(" 3D8 ") == (3, 8)


def test_count_defaults_to_one():
    assert parse_dice("d20") == (1, 20)


@pytest.mark.parametrize("bad", ["", "banana", "d", "2d", "2x6", "1.5d6"])
def test_unreadable_specs_raise(bad):
    with pytest.raises(ValueError, match="NdM"):
        parse_dice(bad)


@pytest.mark.parametrize("bad", ["0d6", f"{MAX_COUNT + 1}d6", "1d1", f"1d{MAX_SIDES + 1}"])
def test_out_of_range_raises(bad):
    with pytest.raises(ValueError):
        parse_dice(bad)


def test_rolls_are_within_bounds_and_deterministic_with_seed():
    rolls = roll_dice(10, 6, random.Random(0))
    assert len(rolls) == 10
    assert all(1 <= r <= 6 for r in rolls)
    assert rolls == roll_dice(10, 6, random.Random(0))
