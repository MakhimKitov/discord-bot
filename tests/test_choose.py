"""Choose logic — pure functions, no Discord."""

import random

import pytest
from bot.commands.utility import parse_weighted_option, pick


def test_picks_one_of_the_options():
    assert pick("red, green, blue", random.Random(0)) in {"red", "green", "blue"}


def test_whitespace_and_empty_entries_are_ignored():
    assert pick(" solo , ,, ", random.Random(0)) == "solo"


@pytest.mark.parametrize("bad", ["", "  ", ",,,"])
def test_no_options_raises(bad):
    with pytest.raises(ValueError, match="comma-separated"):
        pick(bad)


# -- weighted options (#9) --------------------------------------------------


def test_weighted_pick_seeded_exact_result():
    # FR-1/FR-6: a fixed seed against a weighted+unweighted mix picks
    # deterministically, matching the module's existing seeded-rng pattern.
    assert pick("a:3, b", random.Random(42)) == "a"


def test_weighted_pick_distribution_favors_higher_weight():
    # FR-1: over many seeded draws, a:3 vs b (weight 1) lands near the 3:1
    # (75%) ratio implied by the weights, within loose statistical bounds.
    rng = random.Random(7)
    counts = {"a": 0, "b": 0}
    draws = 2000
    for _ in range(draws):
        counts[pick("a:3, b", rng)] += 1
    assert 0.65 < counts["a"] / draws < 0.85


def test_mixed_weighted_and_unweighted_options_parse_and_draw():
    # FR-2: weighted and unweighted options mix freely in one invocation.
    rng = random.Random(3)
    for _ in range(50):
        assert pick("pizza:5, sushi, tacos:2", rng) in {"pizza", "sushi", "tacos"}


@pytest.mark.parametrize("bad", ["x:0", "x:101", ":3"])
def test_out_of_range_or_empty_weight_rejects_with_bounds_message(bad):
    # FR-3: pure-digit weights outside 1-100, or attached to empty option
    # text, reject the whole command naming the valid form and bounds.
    with pytest.raises(ValueError, match=r"option:N.*1–100|1–100.*option:N"):
        pick(bad)


@pytest.mark.parametrize("literal", ["red:ish", "pizza:2.5", "ratio 3:x"])
def test_non_digit_colon_suffix_is_literal_option_text(literal):
    # FR-4: a colon suffix that isn't pure digits stays literal text —
    # the colon is not weight syntax.
    assert parse_weighted_option(literal) == (literal, 1)
    assert pick(literal, random.Random(0)) == literal


def test_weighted_pick_returns_option_without_weight_suffix():
    # FR-5: the chosen option never leaks its :N weight suffix.
    assert pick("pizza:3", random.Random(0)) == "pizza"


@pytest.mark.parametrize("non_ascii_digit", ["pizza:²", "pizza:３"])
def test_non_ascii_digit_suffix_is_literal_not_a_weight(non_ascii_digit):
    # FR-4 edge case: str.isdigit() is True for non-ASCII digits (superscript
    # "²", full-width "３") that int() can't parse. These must be
    # treated as literal text, not crash past the friendly bounds message.
    assert parse_weighted_option(non_ascii_digit) == (non_ascii_digit, 1)
