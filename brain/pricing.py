"""Per-model $/token pricing for cost visibility. Anthropic-published rates
as of 2026-07 (introductory Sonnet 5 pricing through 2026-08-31 is used
here since that's what the company is actually billed) — update PRICING
when pricing changes or the configured model changes."""

from __future__ import annotations

from brain.models import LLMUsageRecord

# $ per million tokens. cache_write approximates the 5-minute-TTL premium
# (1.25x input); cache_read is the standard 0.1x input discount.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.20},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
}

# An unrecognized model (renamed, or a future upgrade not yet added above)
# still needs an estimate rather than a crash — Sonnet-tier rates are the
# reasonable middle ground.
_FALLBACK = PRICING["claude-sonnet-5"]


def cost_for_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    """Dollar cost of one LLM call from its reported token usage."""
    rates = PRICING.get(model, _FALLBACK)
    return (
        input_tokens * rates["input"]
        + output_tokens * rates["output"]
        + cache_creation_input_tokens * rates["cache_write"]
        + cache_read_input_tokens * rates["cache_read"]
    ) / 1_000_000


def summarize_usage(records: list[LLMUsageRecord]) -> dict:
    """Total cost/tokens plus a per-command breakdown, sorted priciest
    first — the shape both the dashboard cost card and `brain status` want."""
    total_cost = 0.0
    total_tokens = 0
    by_command: dict[str, dict] = {}

    for r in records:
        cost = cost_for_usage(
            r.model, r.input_tokens, r.output_tokens,
            r.cache_creation_input_tokens, r.cache_read_input_tokens,
        )
        tokens = r.input_tokens + r.output_tokens
        total_cost += cost
        total_tokens += tokens
        entry = by_command.setdefault(r.command, {"command": r.command, "calls": 0, "cost": 0.0, "tokens": 0})
        entry["calls"] += 1
        entry["cost"] += cost
        entry["tokens"] += tokens

    return {
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "calls": len(records),
        "by_command": sorted(by_command.values(), key=lambda e: -e["cost"]),
    }
