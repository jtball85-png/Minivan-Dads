"""Free-text-everywhere interaction primitive.

Product rule (progress summary §5): at every decision point, listed options
are accelerators only. Typing anything else is a discussion message to the
brain, which replies in place — then the CEO is prompted again. Voice v1 is
OS dictation into the same input; nothing to build here for that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Exchange:
    speaker: str  # "CEO" | "brain"
    text: str


def render_exchanges(exchanges: list[Exchange], indent: str = "") -> str:
    return "\n".join(f"{indent}{e.speaker}: {e.text}" for e in exchanges)


def prompt_with_freetext(
    prompt: str,
    options: dict[str, str],
    discuss: Callable[[str, list[Exchange]], str],
    transcript: list[Exchange] | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> str:
    """Prompt until the CEO picks an option; free text becomes discussion.

    `options` maps short keys to canonical values, e.g. {"a": "approve"}.
    Input matching an option key or full value (case-insensitive) returns the
    canonical value. Empty input re-prompts with a hint. Anything else is sent
    to `discuss(ceo_text, history)`; both sides are appended to `transcript`
    (caller-owned — pass the same list to keep history across items) and the
    reply is printed before re-prompting.
    """
    if transcript is None:
        transcript = []

    values = {v.lower(): v for v in options.values()}

    while True:
        raw = input_fn(prompt).strip()
        lowered = raw.lower()

        if not lowered:
            print_fn("(pick an option, or type a question/comment for the brain)")
            continue
        if lowered in options:
            return options[lowered]
        if lowered in values:
            return values[lowered]

        transcript.append(Exchange("CEO", raw))
        reply = discuss(raw, transcript)
        transcript.append(Exchange("brain", reply))
        print_fn(f"\nbrain> {reply}\n")
