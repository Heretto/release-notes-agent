"""Fragment normalization, chunking and topic assembly."""

import uuid
from types import SimpleNamespace

import pytest
from lxml import etree

from app.models.database import ChunkingStrategy
from app.services.llm_json import extract_json
from app.services.topic_assembler import (
    FragmentError, Layout, build_topic_xml, coerce_fragment, fragment_title, normalize_fragment,
    note_element, plan_topics, plain_text_fragment, template_errors, validate_fragment,
    validate_topic,
)


def _item(title, group=None, position=0, status="draft", components=(), dita=None):
    item_id = uuid.uuid4()
    fragment_id = f"rn-{str(item_id).split('-')[0]}"
    issues = [SimpleNamespace(components=list(components), issue_key="X-1")] if components else []
    return SimpleNamespace(
        id=item_id, fragment_id=fragment_id, title=title, summary=f"{title} summary", group_name=group,
        position=position, status=status, issues=issues, created_at=None,
        dita_content=dita or plain_text_fragment(fragment_id, title, f"{title} summary"),
    )


class TestNormalizeFragment:
    """A note stores its content. The element around it is assembly's decision."""

    def test_a_wrapping_div_is_unwrapped(self):
        out = normalize_fragment('<div><p><b>T</b></p><p>Body</p></div>', "rn-1", "T")
        assert not out.lstrip().startswith("<div")
        assert "outputclass" not in out and 'id="rn-1"' not in out
        assert "<p>Body</p>" in out

    def test_code_fences_and_declarations_are_stripped(self):
        raw = '```xml\n<?xml version="1.0"?>\n<div><p>Body</p></div>\n```'
        assert "<?xml" not in normalize_fragment(raw, "rn-1", "T")

    def test_section_is_unwrapped_and_its_title_becomes_a_lead(self):
        out = normalize_fragment("<section><title>Lead</title><p>Body</p></section>", "rn-1", "T")
        assert "<section" not in out and "<title>" not in out
        assert fragment_title(out) == "Lead"

    def test_sibling_elements_are_kept_side_by_side(self):
        out = normalize_fragment("<p>One</p><ul><li>Two</li></ul>", "rn-1", "T")
        assert "<div" not in out
        assert "<p>One</p>" in out and "<li>Two</li>" in out

    def test_loose_text_becomes_a_paragraph(self):
        # Bare text is not valid inside a <div> or an <li>, so it cannot be stored raw.
        assert normalize_fragment("Just a sentence.", "rn-1", "T") == "<p>Just a sentence.</p>"

    def test_malformed_xml_is_rejected(self):
        with pytest.raises(FragmentError):
            normalize_fragment("<div><p>unclosed</div>", "rn-1", "T")

    def test_empty_output_is_rejected(self):
        with pytest.raises(FragmentError):
            normalize_fragment("```\n```", "rn-1", "T")

    def test_the_wrappers_attributes_do_not_survive(self):
        out = normalize_fragment('<div class="x" id="other"><p>Body</p></div>', "rn-9", "T")
        assert ' class=' not in out and 'id="other"' not in out


class TestNoteElement:
    """The same stored content, placed in whichever element assembly asks for."""

    def test_the_wrapper_carries_the_identity(self):
        item = _item("A", None, 0, dita="<p>Body</p>")
        for tag in ("div", "li"):
            xml = etree.tostring(note_element(item, tag), encoding="unicode")
            assert xml.startswith(f"<{tag} ")
            assert f'id="{item.fragment_id}"' in xml
            # The workspace finds a note in rendered DITA by this pair; every mode keeps it.
            assert 'outputclass="release-note"' in xml
            assert "<p>Body</p>" in xml

    def test_unparseable_content_still_produces_an_element(self):
        item = _item("A", None, 0, dita="<p>broken")
        xml = etree.tostring(note_element(item, "li"), encoding="unicode")
        assert "A summary" in xml


class TestValidation:
    def test_valid_fragment_passes(self):
        assert validate_fragment('<p>ok <tt>x</tt></p><pre>y</pre><note type="tip"><p>n</p></note>') == []

    def test_invalid_element_is_reported_without_temp_paths(self):
        errors = validate_fragment('<p>ok</p><steps/>')
        assert errors and all(not e.startswith("/") for e in errors)
        assert any("steps" in e for e in errors)

    def test_coerce_raises_with_errors(self):
        with pytest.raises(FragmentError) as info:
            coerce_fragment("<p>ok</p><steps/>", "rn-1", "T")
        assert info.value.errors


class TestPlanning:
    def test_single_puts_everything_in_one_topic_with_group_sections(self):
        items = [_item("A", "Features", 0), _item("B", "Fixes", 1), _item("C", "Features", 2)]
        plans = plan_topics(items, ChunkingStrategy.SINGLE, "Release 1", "release-notes.xml")
        assert len(plans) == 1
        assert plans[0].filename == "release-notes.dita"
        assert [name for name, _ in plans[0].groups] == ["Features", "Fixes"]
        assert [i.title for i in plans[0].groups[0][1]] == ["A", "C"]

    def test_rejected_notes_are_left_out(self):
        items = [_item("A", "Features", 0), _item("B", "Features", 1, status="rejected")]
        plans = plan_topics(items, ChunkingStrategy.SINGLE, "R", "out")
        assert [i.title for i in plans[0].items] == ["A"]

    def test_by_group_makes_one_topic_per_group(self):
        items = [_item("A", "Features", 0), _item("B", "Fixes", 1), _item("C", None, 2)]
        plans = plan_topics(items, ChunkingStrategy.BY_GROUP, "R", "out")
        assert [p.title for p in plans] == ["R: Features", "R: Fixes", "R: Other changes"]
        assert plans[0].filename == "out-features.dita"

    def test_by_component_uses_the_first_component(self):
        items = [_item("A", "F", 0, components=["Web", "API"]), _item("B", "F", 1, components=["API"]), _item("C", "F", 2)]
        plans = plan_topics(items, ChunkingStrategy.BY_COMPONENT, "R", "out")
        assert [p.title for p in plans] == ["R: Web", "R: API", "R: Other changes"]


class TestTopicXml:
    def test_assembled_topic_validates_and_keeps_fragment_ids(self):
        items = [_item("A", "Features", 0), _item("B", "Fixes", 1)]
        plan = plan_topics(items, ChunkingStrategy.SINGLE, "Release 1", "notes")[0]
        xml = build_topic_xml(plan)
        assert validate_topic(xml) == []
        assert f'id="{items[0].fragment_id}"' in xml
        assert "<section" in xml and "Features" in xml

    def test_ungrouped_notes_go_straight_into_the_body(self):
        plan = plan_topics([_item("A", None, 0)], ChunkingStrategy.SINGLE, "R", "n")[0]
        xml = build_topic_xml(plan)
        assert "<section" not in xml and validate_topic(xml) == []

    def test_a_broken_fragment_falls_back_to_plain_text(self):
        item = _item("A", None, 0, dita="<p>broken")
        plan = plan_topics([item], ChunkingStrategy.SINGLE, "R", "n")[0]
        xml = build_topic_xml(plan)
        assert validate_topic(xml) == [] and "A summary" in xml


class TestExtractJson:
    def test_fenced(self):
        assert extract_json('Sure:\n```json\n{"a": 1}\n```') == {"a": 1}

    def test_embedded_object_with_strings_containing_braces(self):
        assert extract_json('Result: {"t": "a } b", "n": [1]} done') == {"t": "a } b", "n": [1]}

    def test_array(self):
        assert extract_json('[{"n": 1}]') == [{"n": 1}]

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            extract_json("nothing here")


class TestLayout:
    """Stage 2: the shape of a topic is the instruction set's choice."""

    def _plan(self):
        items = [_item("A", "New features", 0, dita="<p>One</p>"),
                 _item("B", "Fixes", 1, dita="<p>Two</p>")]
        return plan_topics(items, ChunkingStrategy.SINGLE, "R", "n")[0]

    def test_default_is_the_shape_this_app_always_produced(self):
        xml = build_topic_xml(self._plan())
        assert "<section" in xml and "<div" in xml and "<ul>" not in xml
        assert validate_topic(xml) == []

    def test_bold_heading_with_list_items(self):
        """The reported house style: a bold paragraph per group, its notes as one list."""
        layout = Layout(group_heading="paragraph", notes_wrapper="ul",
                        note_element="li", shortdesc="empty")
        xml = build_topic_xml(self._plan(), layout=layout)
        assert "<shortdesc/>" in xml
        assert "<section" not in xml
        assert "<b>New features</b>" in xml
        assert '<li id="rn-' in xml and 'outputclass="release-note"' in xml
        assert validate_topic(xml) == []

    def test_the_identity_survives_every_layout(self):
        """The workspace finds a note by id + outputclass; no layout may drop that pair."""
        for layout in (
            Layout(),
            Layout(group_heading="none", notes_wrapper="ol", note_element="li"),
            Layout(group_heading="paragraph"),
        ):
            xml = build_topic_xml(self._plan(), layout=layout)
            assert xml.count('outputclass="release-note"') == 2
            assert xml.count('id="rn-') >= 2

    def test_the_wrapper_decides_what_a_note_is(self):
        """A stored pair that disagrees still assembles to valid DITA.

        The schema refuses the mismatch on the way in, but a hand-edited row must not be
        able to put a <div> inside a <ul>.
        """
        xml = build_topic_xml(self._plan(), layout=Layout(notes_wrapper="ul", note_element="div"))
        assert "<div" not in xml and '<li id="rn-' in xml
        assert validate_topic(xml) == []

        xml = build_topic_xml(self._plan(), layout=Layout(notes_wrapper="none", note_element="li"))
        assert "<li" not in xml and '<div id="rn-' in xml
        assert validate_topic(xml) == []

    def test_shortdesc_text(self):
        layout = Layout(shortdesc="text", shortdesc_text="What changed this month.")
        assert "<shortdesc>What changed this month.</shortdesc>" in build_topic_xml(self._plan(), layout=layout)

    def test_unreadable_stored_layout_falls_back_to_the_default(self):
        class Set:
            layout = {"structured": "not a dict"}
        assert Layout.of(Set()) == Layout()
        assert Layout.of(None) == Layout()


class TestTemplateLayout:
    """Mode 2: the writer's own DITA, emitted as written."""

    TEMPLATE = (
        '<topic id="x"><title>{title}</title><shortdesc/><body>'
        '<p>Boilerplate with <ph conkeyref="vars/productName"/>.</p>'
        '<section outputclass="rn-group"><p><b>{group}</b></p>'
        '<ul outputclass="rn-notes"><li><p>sample</p></li></ul></section>'
        "</body></topic>"
    )

    def _plan(self):
        items = [_item("A", "New features", 0, dita="<p>One</p>"),
                 _item("B", "Fixes", 1, dita="<p>Two</p>")]
        return plan_topics(items, ChunkingStrategy.SINGLE, "Release 7", "n")[0]

    def test_a_good_template_has_no_errors(self):
        assert template_errors(self.TEMPLATE) == []

    @pytest.mark.parametrize("bad,expected", [
        ("<section><title>x</title></section>", "must be a <topic>"),
        ("<topic><title>t</title><body><p/></body></topic>", "where the notes go"),
        ("<topic><p>unclosed", "well-formed"),
        ('<topic><body><ul outputclass="rn-notes"/></body></topic>', "needs a <title>"),
    ])
    def test_unusable_templates_say_why(self, bad, expected):
        assert any(expected in e for e in template_errors(bad))

    def test_the_template_drives_the_output(self):
        xml = build_topic_xml(self._plan(), layout=Layout(mode="template", template=self.TEMPLATE))
        assert "{title}" not in xml and "Release 7" in xml
        assert 'conkeyref="vars/productName"' in xml          # author's content survives
        assert xml.count("<section") == 2                      # repeated per group
        assert "<b>New features</b>" in xml and "<b>Fixes</b>" in xml
        assert "sample" not in xml                             # the author's example is replaced
        assert xml.count('outputclass="release-note"') == 2
        assert "rn-group" not in xml and "rn-notes" not in xml  # markers do not ship

    def test_a_list_host_makes_notes_list_items(self):
        xml = build_topic_xml(self._plan(), layout=Layout(mode="template", template=self.TEMPLATE))
        assert '<li id="rn-' in xml

    def test_a_block_host_makes_notes_divs(self):
        template = self.TEMPLATE.replace('<ul outputclass="rn-notes"><li><p>sample</p></li></ul>',
                                         '<div outputclass="rn-notes"/>')
        xml = build_topic_xml(self._plan(), layout=Layout(mode="template", template=template))
        assert '<div id="rn-' in xml

    def test_agent_mode_without_a_settled_template_uses_the_options(self):
        """Before a release's first run there is no template; a topic is still produced."""
        layout = Layout(mode="agent", guidance="something", template="")
        xml = build_topic_xml(self._plan(), layout=layout)
        assert "<section" in xml and validate_topic(xml) == []
