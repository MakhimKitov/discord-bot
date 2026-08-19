"""``/uptime`` — process lifetime, formatted (issue #24).

format_uptime/format_uptime_reply are pure functions (FR-4), the wrapper reads
a monotonic clock via interaction.client (FR-3), and the start marker itself
is captured once at client construction, not on_ready (FR-2).
"""

from __future__ import annotations

import asyncio

import pytest
from bot.client import UtilityBot
from bot.commands import utility
from bot.commands.utility import format_uptime, format_uptime_reply, uptime
from bot.config import BotConfig

# -- format_uptime / format_uptime_reply: FR-4 table -------------------------


@pytest.mark.parametrize(
    "elapsed_seconds, expected_duration",
    [
        (0, "0s"),
        (41, "41s"),
        (59.9, "59s"),  # truncated, never rounded up
        (60, "1m"),
        (7 * 60 + 12, "7m 12s"),
        (60 * 60 + 5, "1h 5s"),  # the zero-valued minute is dropped, not just the trailing zero
        (60 * 60 + 5 * 60 + 30, "1h 5m"),
        (23 * 60 * 60 + 59 * 60, "23h 59m"),
        (24 * 60 * 60, "1d"),
        (3 * 86400 + 4 * 3600 + 12 * 60, "3d 4h"),
    ],
)
def test_format_uptime_table(elapsed_seconds, expected_duration):
    assert format_uptime(elapsed_seconds) == expected_duration
    assert format_uptime_reply(elapsed_seconds) == f"⏱️ Up **{expected_duration}**"


# -- /uptime wrapper: FR-3 (reads a monotonic source, driven directly) ------


class _FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content):
        self.messages.append(content)


class _FakeClient:
    def __init__(self, started_monotonic):
        self.started_monotonic = started_monotonic


class _FakeInteraction:
    def __init__(self, started_monotonic):
        self.client = _FakeClient(started_monotonic)
        self.response = _FakeResponse()


def test_uptime_wrapper_reads_monotonic_clock_via_client(monkeypatch):
    monkeypatch.setattr(utility.time, "monotonic", lambda: 1_000.0)
    interaction = _FakeInteraction(started_monotonic=1_000.0 - 7205)  # 2h 0m 5s ago

    asyncio.run(uptime.callback(interaction))

    assert interaction.response.messages == ["⏱️ Up **2h 5s**"]


def test_uptime_wrapper_is_unaffected_by_the_wall_clock(monkeypatch):
    """FR-3: only the monotonic source drives the reply — no dependence on
    wall-clock time (e.g. time.time()) that an NTP step could move."""
    monkeypatch.setattr(utility.time, "monotonic", lambda: 500.0)
    interaction = _FakeInteraction(started_monotonic=500.0 - 41)

    asyncio.run(uptime.callback(interaction))

    assert interaction.response.messages == ["⏱️ Up **41s**"]


# -- start marker: FR-2 (captured once at construction, survives on_ready) --


def test_start_marker_captured_once_and_survives_repeated_on_ready(monkeypatch):
    import bot.client as client_module

    # Patch monotonic only around construction — asyncio's own event loop
    # relies on time.monotonic() internally (it's the same stdlib module
    # object), so the patch must not still be in effect once on_ready runs.
    with monkeypatch.context() as m:
        m.setattr(client_module.time, "monotonic", lambda: 100.0)
        bot = UtilityBot(BotConfig(token="test-token"))

    assert bot.started_monotonic == 100.0

    # on_ready fires again after a gateway resume — it must not touch the
    # marker captured at construction.
    asyncio.run(bot.on_ready())
    asyncio.run(bot.on_ready())

    assert bot.started_monotonic == 100.0
