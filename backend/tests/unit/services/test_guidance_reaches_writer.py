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
    assert "Output guidance" not in prompts.write_instructions("Heretto CCMS", empty)


def test_writer_is_told_to_ignore_topic_level_rules() -> None:
    """Guidance usually describes the whole topic. Asked to produce that, the writer emits
    a fragment that fails DTD validation and the note falls back to its plain summary."""
    block = prompts.house_style(GUIDANCE)
    assert "<shortdesc>" in block and "assembled into topics" in block


def test_fragment_format_still_follows_the_guidance() -> None:
    """Ordering matters: the format rules are last, so they win on any conflict."""
    instructions = prompts.write_instructions("Heretto CCMS", GUIDANCE)
    assert instructions.index(GUIDANCE) < instructions.index("## Output format")


def test_house_style_does_not_ask_for_a_wrapper() -> None:
    """The format rules forbid a wrapping <div>; the house style once asked for one, so a
    writer with guidance was given two contradictory instructions."""
    block = prompts.house_style(GUIDANCE)
    assert "Return one <div>" not in block
    assert "no wrapper" in block


@pytest.mark.parametrize("element", ["<codeph>", "<codeblock>", "<uicontrol>", "<filepath>"])
def test_technical_content_elements_are_offered(element) -> None:
    """These validate against the technicalContent shells (hop-core v0.1.16+). The prompt
    banned them while the base DTD rejected them, and the ban outlived the reason."""
    allowed, forbidden = prompts.FRAGMENT_FORMAT.split("Do NOT use", 1)
    assert element in allowed
    assert element not in forbidden


def test_the_writer_can_link_each_issue() -> None:
    """Guidance can ask for an internal link to each Jira issue; without the issue's URL the
    writer can only guess the Jira site, so the links were missing or wrong."""
    from types import SimpleNamespace

    issue = SimpleNamespace(
        issue_key="EZD-1", url="https://example.atlassian.net/browse/EZD-1", issue_type="Bug",
        status="Done", priority=None, summary="s", description=None, labels=[], components=[],
        fix_versions=[], comments=[],
    )
    assert prompts.issue_record(issue)["url"] == "https://example.atlassian.net/browse/EZD-1"
    assert '"url"' in prompts.FRAGMENT_FORMAT


# ── One output guidance, read by every stage that shapes the output ────────────────────

def test_organize_follows_the_output_guidance() -> None:
    """Grouping by product is in the output guidance; organize used to read another box
    and fell back to grouping by kind of change."""
    instructions = prompts.organize_instructions(GUIDANCE, [])
    assert GUIDANCE in instructions
    assert "kind of change" not in instructions          # the default is for no guidance only
    assert "kind of change" in prompts.organize_instructions(None, [])


def test_organize_can_put_versions_in_group_names() -> None:
    """A heading like "Heretto Portal v6 26.10.22" needs the version from Jira."""
    from types import SimpleNamespace

    issue = SimpleNamespace(issue_key="P-1", issue_type="Bug", components=["Portal"],
                            fix_versions=["Portal v6 26.10.22"])
    item = SimpleNamespace(title="t", summary="s", group_name="Fix", issues=[issue])
    import json
    record = json.loads(prompts.organize_input([item]))[0]
    assert record["fix_versions"] == ["Portal v6 26.10.22"]
    assert "fix_versions" in prompts.organize_instructions(GUIDANCE, [])


def test_the_template_agent_takes_only_the_structure() -> None:
    """It now receives the whole output description, note wording included."""
    instructions = prompts.topic_structure_instructions(GUIDANCE)
    assert GUIDANCE in instructions and "Take from it only the structure" in instructions


def test_layout_guidance_is_what_the_stages_read() -> None:
    from types import SimpleNamespace
    from app.services.topic_assembler import Layout

    stored = SimpleNamespace(layout={"mode": "structured", "guidance": GUIDANCE})
    assert Layout.of(stored).guidance == GUIDANCE
