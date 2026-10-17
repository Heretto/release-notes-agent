"""The instruction set's guidance must reach the agent that writes the words.

It used to go only to the organize stage, which decides group names and order, so a person
who wrote their house style in that box saw no change in the notes — the reported bug.
"""

import pytest

from app.services import pipeline_prompts as prompts

GUIDANCE = 'Each <li> must start with "Added." and each note must start with "We".'


def test_guidance_is_in_the_writer_instructions() -> None:
    assert GUIDANCE in prompts.write_instructions("Heretto CCMS", GUIDANCE)


def test_guidance_survives_the_dita_retry() -> None:
    """A retry that drops the style fixes the markup and loses the wording."""
    assert GUIDANCE in prompts.rewrite_instructions("Heretto CCMS", ["bad element"], GUIDANCE)


@pytest.mark.parametrize("empty", [None, "", "   ", "\n"])
def test_no_guidance_adds_nothing(empty) -> None:
    assert prompts.house_style(empty) == ""
    assert "House style" not in prompts.write_instructions("Heretto CCMS", empty)


def test_writer_is_told_to_ignore_topic_level_rules() -> None:
    """Guidance usually describes the whole topic. Asked to produce that, the writer emits
    a fragment that fails DTD validation and the note falls back to its plain summary."""
    block = prompts.house_style(GUIDANCE)
    assert "<shortdesc>" in block and "assembled into topics" in block


def test_fragment_format_still_follows_the_guidance() -> None:
    """Ordering matters: the format rules are last, so they win on any conflict."""
    instructions = prompts.write_instructions("Heretto CCMS", GUIDANCE)
    assert instructions.index(GUIDANCE) < instructions.index("## Output format")
