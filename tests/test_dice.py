"""Dice logic — pure functions, no Discord."""

import random

import pytest
from bot.commands.utility import MAX_COUNT, MAX_SIDES, format_roll_reply, parse_dice, roll_dice


@pytest.mark.parametrize(
    "spec, expected",
    [
        ("2d6", (2, 6)),
        ("1d20", (1, 20)),
        (" 3D8 ", (3, 8)),
        ("2D6", (2, 6)),
        ("1d2", (1, 2)),
        (f"{MAX_COUNT}d{MAX_SIDES}", (MAX_COUNT, MAX_SIDES)),
    ],
)
def test_parse_accepts_valid_notation(spec, expected):
    assert parse_dice(spec) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "banana",
        "d",
        "2d",  # missing sides
        "d20",  # missing count — no positional default, unlike the option itself
        "-1d6",  # negative count
        "2d6+1",  # modifier, out of scope for v1
        "2x6",  # wrong separator
        "1.5d6",  # non-integer count
    ],
)
def test_parse_rejects_unreadable_specs_with_usage_message(bad):
    with pytest.raises(ValueError, match="NdM"):
        parse_dice(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "0d6",  # count below minimum
        f"{MAX_COUNT + 1}d6",  # count above maximum
        "1d1",  # sides below minimum
        f"1d{MAX_SIDES + 1}",  # sides above maximum
        "999d999999",  # both out of bounds
    ],
)
def test_parse_rejects_out_of_bounds_with_bounds_message(bad):
    with pytest.raises(ValueError, match=r"must be \d+–\d+"):
        parse_dice(bad)


def test_rolls_are_within_bounds_and_deterministic_with_seed():
    rolls = roll_dice(10, 6, random.Random(0))
    assert len(rolls) == 10
    assert all(1 <= r <= 6 for r in rolls)
    assert rolls == roll_dice(10, 6, random.Random(0))


def test_format_roll_reply_single_die_drops_sum():
    assert format_roll_reply(1, 6, [5]) == "🎲 1d6 → 5"


def test_format_roll_reply_multiple_dice_shows_total():
    assert format_roll_reply(2, 6, [4, 6]) == "🎲 2d6 → 4 + 6 = 10"


def test_worst_case_reply_length_is_well_under_discord_limit():
    # Worst case for FR-1's bounds: 20d1000, every die landing on the max side.
    worst = format_roll_reply(MAX_COUNT, MAX_SIDES, [MAX_SIDES] * MAX_COUNT)
    assert len(worst) == 157
    assert len(worst) < 2000
