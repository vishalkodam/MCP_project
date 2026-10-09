"""Tests for per-turn token usage + estimated cost reporting (Day 4)."""

from types import SimpleNamespace

from core import usage
from core.chat import Chat
from tests.test_streaming import (
    FakeMcpClient,
    final_message,
    make_claude,
    text_block,
    tool_use_block,
)


def message_with_usage(blocks, input_tokens, output_tokens, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=list(blocks),
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_pricing_lookup_known_model():
    assert usage.pricing_for("claude-sonnet-4-20250514") == (3.0, 15.0)
    assert usage.pricing_for("claude-3-haiku-20240307") == (0.25, 1.25)


def test_pricing_lookup_unknown_model_falls_back():
    assert usage.pricing_for("claude-mystery-99") == usage.DEFAULT_PRICING
    assert usage.pricing_for("") == usage.DEFAULT_PRICING


def test_estimate_cost_math():
    # 1M input + 2M output tokens at (3, 15)/M = 3 + 30 = $33
    assert usage.estimate_cost("claude-sonnet-4", 1_000_000, 2_000_000) == 33.0


def test_usage_of_missing_usage_returns_zeros():
    msg = final_message([text_block("hi")])  # no .usage attribute
    assert usage.usage_of(msg) == (0, 0)


def test_usage_of_reads_token_counts():
    msg = message_with_usage([text_block("hi")], 1204, 386)
    assert usage.usage_of(msg) == (1204, 386)


def test_format_turn_usage_contains_numbers():
    line = usage.format_turn_usage(1204, 386, 0.0094, 0.0211)
    assert "1,204" in line
    assert "386" in line
    assert "$0.0094" in line
    assert "$0.0211" in line


async def test_run_prints_usage_and_tracks_session_total(capsys):
    turn1 = message_with_usage(
        [text_block("Reading."), tool_use_block()], 1000, 200, stop_reason="tool_use"
    )
    turn2 = message_with_usage([text_block("Done.")], 1500, 100)
    service = make_claude(
        [
            (["Reading."], turn1),
            (["Done."], turn2),
        ],
        model="claude-sonnet-4-20250514",
    )
    chat = Chat(claude_service=service, clients={"documents": FakeMcpClient()})
    await chat.run("read hello.md")

    out = capsys.readouterr().out
    assert "1,000 in · 200 out" in out
    assert "1,500 in · 100 out" in out
    # session totals accumulated across both turns: 2500 in / 300 out
    assert chat.session_input_tokens == 2500
    assert chat.session_output_tokens == 300
    expected = usage.estimate_cost("claude-sonnet-4-20250514", 2500, 300)
    assert f"(session ~${expected:.4f})" in out


async def test_run_without_usage_still_works(capsys):
    # Old-style doubles carry no usage info; run should not crash or print stats.
    service = make_claude([(["hi"], final_message([text_block("hi")]))])
    chat = Chat(claude_service=service, clients={})
    assert await chat.run("hello") == "hi"
    assert "📊" not in capsys.readouterr().out
    assert chat.session_input_tokens == 0
