"""Token usage and estimated cost reporting (Day 4).

Pulls ``input_tokens`` / ``output_tokens`` off a finished Anthropic ``Message``
(the final message from :meth:`Claude.chat_stream` carries cumulative usage for
the whole streamed reply) and turns them into a one-line ``$`` estimate.
"""

# Price per million tokens: (input, output) in USD, keyed by model-id substring.
# Rough published Anthropic prices; check anthropic.com/pricing for the latest.
PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-opus": (15.0, 75.0),
    "claude-3-haiku": (0.25, 1.25),
}

# Fallback for models we don't recognize: sonnet-class pricing.
DEFAULT_PRICING: tuple[float, float] = (3.0, 15.0)


def pricing_for(model: str) -> tuple[float, float]:
    """Return (input, output) price per million tokens for ``model``."""
    model = (model or "").lower()
    for key, prices in PRICING_PER_MILLION.items():
        if key in model:
            return prices
    return DEFAULT_PRICING


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimated USD cost of one turn from its token counts."""
    price_in, price_out = pricing_for(model)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def usage_of(message) -> tuple[int, int]:
    """Safely pull (input_tokens, output_tokens) off a finished message.

    Returns ``(0, 0)`` when the message carries no usage info (e.g. test
    doubles), so callers can simply skip the usage line in that case.
    """
    usage = getattr(message, "usage", None)
    if usage is None:
        return (0, 0)
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )


def format_turn_usage(
    input_tokens: int,
    output_tokens: int,
    cost: float,
    session_cost: float,
) -> str:
    """One-line usage summary shown after each model turn."""
    return (
        f"📊 {input_tokens:,} in · {output_tokens:,} out · "
        f"~${cost:.4f} (session ~${session_cost:.4f})"
    )
