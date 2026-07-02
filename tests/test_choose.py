"""Choose logic — pure functions, no Discord."""

import random

import pytest
from bot.commands.utility import pick


def test_picks_one_of_the_options():
    assert pick("red, green, blue", random.Random(0)) in {"red", "green", "blue"}


def test_whitespace_and_empty_entries_are_ignored():
    assert pick(" solo , ,, ", random.Random(0)) == "solo"


@pytest.mark.parametrize("bad", ["", "  ", ",,,"])
def test_no_options_raises(bad):
    with pytest.raises(ValueError, match="comma-separated"):
        pick(bad)
