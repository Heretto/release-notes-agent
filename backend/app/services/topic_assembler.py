"""Turning release note items into DITA topics.

Every note stores **content**, not a wrapper: the children that go inside whatever element
assembly decides to put them in. The wrapper is assembly's business, so a note can be a
``<div>`` in one instruction set and an ``<li>`` inside a shared ``<ul>`` in another without
the stored note changing. Whatever the element, assembly stamps it with the note's
``fragment_id`` and ``outputclass="release-note"`` — that pair is what lets the workspace map
rendered DITA back to the note it came from, and nothing downstream should assume more. Notes can
be grouped under ``<section>`` headings, split across topics, and re-split later without the
writer agent rewriting anything. This module owns that fragment shape (normalizing what a
model returns into it, validating it against the DITA 1.3 DTD), the chunking strategies that
decide which notes share a topic, and the topic XML itself.
"""

from __future__ import annotations

import copy
import re
import dataclasses
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from lxml import etree

from hop_core.dita import DitaRenderer, DitaValidator, DitaParseError

from app.models.database import ChunkingStrategy, ItemStatus, ReleaseNoteItem

_FENCE = re.compile(r"```(?:xml|dita)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_XML_DECL = re.compile(r"<\?xml[^>]*\?>")
_DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>", re.IGNORECASE)
_SLUG = re.compile(r"[^a-z0-9]+")

# Elements that cannot live inside a <div>; a model occasionally reaches for them anyway.
_UNWRAP_TAGS = {"section", "body", "topic", "conbody", "refbody", "concept", "reference"}

DOCTYPE = '<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">'


class FragmentError(ValueError):
    """A release note fragment is not well-formed or not valid DITA."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or [message]


def slugify(text: str, fallback: str = "release-notes") -> str:
    slug = _SLUG.sub("-", (text or "").lower()).strip("-")
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"rn-{slug}"
    return slug[:120]


def _parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, remove_blank_text=False)


def _strip_wrappers(text: str) -> str:
    fenced = _FENCE.search(text or "")
    if fenced:
        text = fenced.group(1)
    text = _XML_DECL.sub("", text)
    text = _DOCTYPE.sub("", text)
    return text.strip()


def normalize_fragment(raw: str, fragment_id: str, title: str) -> str:
    """Coerce a model's output into a note's **content** — body-level elements, no wrapper.

    Accepts a bare ``<div>``, several sibling elements, or a fragment wrapped in a
    ``<section>``/``<topic>``; rejects anything that is not well-formed XML. A wrapping
    ``<div>`` is unwrapped rather than kept: which element holds this content is decided
    when the topic is assembled, so storing one here would fix it for every mode.

    `fragment_id` is still taken so callers do not have to change and so the signature says
    which note this is; it is no longer written into the content.
    """
    text = _strip_wrappers(raw)
    if not text:
        raise FragmentError("The writer returned no content")

    try:
        root = etree.fromstring(f"<wrapper>{text}</wrapper>", _parser())
    except etree.XMLSyntaxError as exc:
        raise FragmentError(f"Not well-formed XML: {exc}") from exc

    # Unwrap containers a <div> cannot hold, keeping their children.
    changed = True
    while changed:
        changed = False
        for el in list(root.iter()):
            if el is root or not isinstance(el.tag, str):
                continue
            if el.tag in _UNWRAP_TAGS:
                parent = el.getparent()
                index = parent.index(el)
                children = list(el)
                # <title> of an unwrapped section becomes a bold lead paragraph.
                for child in children:
                    if child.tag == "title":
                        lead = etree.Element("p")
                        bold = etree.SubElement(lead, "b")
                        bold.text = "".join(child.itertext()).strip()
                        child.getparent().replace(child, lead)
                for offset, child in enumerate(list(el)):
                    parent.insert(index + offset, child)
                parent.remove(el)
                changed = True
                break

    children = [c for c in root if isinstance(c.tag, str)]
    if len(children) == 1 and children[0].tag == "div" and not (root.text or "").strip():
        div = children[0]
    else:
        div = etree.Element("div")
        if (root.text or "").strip():
            para = etree.SubElement(div, "p")
            para.text = root.text.strip()
        for child in children:
            div.append(child)
        # Loose text after an element (tails) stays attached to the element; fine for XML.

    # A nested <div> is legal DITA but makes the fragment hard to edit; flatten one level.
    for nested in list(div.findall("div")):
        index = div.index(nested)
        for offset, child in enumerate(list(nested)):
            div.insert(index + offset, child)
        div.remove(nested)

    # <title> is not allowed in a div; the fragment carries its title as a bold lead.
    for title_el in list(div.iter("title")):
        lead = etree.Element("p")
        bold = etree.SubElement(lead, "b")
        bold.text = "".join(title_el.itertext()).strip()
        title_el.getparent().replace(title_el, lead)

    if not len(div) and not (div.text or "").strip():
        raise FragmentError("The fragment has no content")

    # Serialize the children, not the holder. Loose text directly inside the holder would
    # not be valid in a <div> or an <li> either, so it is wrapped first.
    if (div.text or "").strip():
        lead = etree.Element("p")
        lead.text = div.text.strip()
        div.text = None
        div.insert(0, lead)

    return "\n".join(
        etree.tostring(child, encoding="unicode", pretty_print=True).strip()
        for child in div
        if isinstance(child.tag, str)
    ).strip()


def plain_text_fragment(fragment_id: str, title: str, summary: str) -> str:
    """The fallback when a model cannot produce valid DITA: the plain summary, escaped.

    Content only, like everything else stored on a note. `fragment_id` is unused and kept
    so the many call sites do not all have to change at once.
    """
    body = escape((summary or "").strip() or title)
    return f"<p><b>{escape(title)}</b></p>\n<p>{body}</p>"


def fragment_title(fragment: str) -> Optional[str]:
    """The bold lead of a note's content, if it has one.

    Wrapped before parsing because a note is content now, not one element.
    """
    try:
        div = etree.fromstring(f"<div>{fragment}</div>", _parser())
    except etree.XMLSyntaxError:
        return None
    first = next((c for c in div if isinstance(c.tag, str)), None)
    if first is not None and first.tag == "p" and len(first) and first[0].tag == "b":
        return "".join(first[0].itertext()).strip() or None
    return None


#: What a note's content is wrapped in while it is validated. Assembly can place the same
#: content in a different element (stage 2 makes that configurable); <div> is the most
#: permissive body-level holder, so content that validates here validates anywhere it is
#: later put.
VALIDATION_WRAPPER = "div"


def _wrap_for_validation(fragment: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n'
        f'<topic id="validation"><title>Validation</title><body>'
        f'<{VALIDATION_WRAPPER}>{fragment}</{VALIDATION_WRAPPER}>'
        f'</body></topic>'
    )


_TEMP_PATH = re.compile(r"^.*?\.xml:(\d+): ")


def clean_errors(errors: Optional[Iterable[str]]) -> List[str]:
    """xmllint prefixes every error with a temp file path; keep only the line number."""
    cleaned = []
    for error in errors or []:
        text = _TEMP_PATH.sub(r"line \1: ", str(error)).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned or ["Invalid DITA"]


def validate_fragment(fragment: str, validator: Optional[DitaValidator] = None) -> List[str]:
    """DTD-validate a fragment inside a minimal topic. Returns the error list (empty = valid)."""
    validator = validator or DitaValidator()
    valid, errors = validator.validate_with_dtd(_wrap_for_validation(fragment))
    if valid:
        return []
    return clean_errors(errors)


def coerce_fragment(raw: str, fragment_id: str, title: str, validator: Optional[DitaValidator] = None) -> str:
    """normalize + validate in one step; raises FragmentError with the DTD errors."""
    fragment = normalize_fragment(raw, fragment_id, title)
    errors = validate_fragment(fragment, validator)
    if errors:
        raise FragmentError("The fragment is not valid DITA", errors)
    return fragment


# ── Chunking ─────────────────────────────────────────────────────────────────────────

@dataclass
class TopicPlan:
    slug: str
    title: str
    filename: str
    items: List[ReleaseNoteItem] = field(default_factory=list)
    # Group name → items, in order. Empty-string key means "ungrouped".
    groups: List[Tuple[str, List[ReleaseNoteItem]]] = field(default_factory=list)


def included_items(items: Iterable[ReleaseNoteItem]) -> List[ReleaseNoteItem]:
    """Notes that go into the output: everything not rejected, in position order."""
    return sorted(
        (i for i in items if i.status != ItemStatus.REJECTED),
        key=lambda i: (i.position, i.created_at or 0),
    )


def _group_in_order(items: Sequence[ReleaseNoteItem]) -> List[Tuple[str, List[ReleaseNoteItem]]]:
    groups: Dict[str, List[ReleaseNoteItem]] = {}
    order: List[str] = []
    for item in items:
        name = (item.group_name or "").strip()
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(item)
    return [(name, groups[name]) for name in order]


def _base_filename(output_filename: Optional[str], fallback: str) -> str:
    name = (output_filename or fallback or "release-notes").strip()
    name = name.rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return re.sub(r"[^\w.\-]", "-", name).strip("-.") or "release-notes"


def plan_topics(
    items: Iterable[ReleaseNoteItem],
    strategy: str,
    release_title: str,
    output_filename: Optional[str],
) -> List[TopicPlan]:
    """Decide which notes share a topic.

    ``single``: one topic. ``by_group``: one per organization group, in group order.
    ``by_component``: one per Jira component (a note with several components lands in the
    first; notes with none go to a final "Other changes" topic).
    """
    notes = included_items(items)
    base = _base_filename(output_filename, release_title)
    base_slug = slugify(base)

    if strategy == ChunkingStrategy.BY_GROUP:
        plans = []
        for name, group_items in _group_in_order(notes):
            label = name or "Other changes"
            plans.append(TopicPlan(
                slug=f"{base_slug}-{slugify(label)}",
                title=f"{release_title}: {label}",
                filename=f"{base}-{slugify(label)}.dita",
                items=list(group_items),
                groups=[("", list(group_items))],
            ))
        return plans

    if strategy == ChunkingStrategy.BY_COMPONENT:
        by_component: Dict[str, List[ReleaseNoteItem]] = {}
        order: List[str] = []
        for item in notes:
            components: List[str] = []
            for issue in item.issues:
                for component in (issue.components or []):
                    if component and component not in components:
                        components.append(component)
            key = components[0] if components else ""
            if key not in by_component:
                by_component[key] = []
                order.append(key)
            by_component[key].append(item)
        order = [k for k in order if k] + ([""] if "" in by_component else [])
        plans = []
        for key in order:
            label = key or "Other changes"
            plans.append(TopicPlan(
                slug=f"{base_slug}-{slugify(label)}",
                title=f"{release_title}: {label}",
                filename=f"{base}-{slugify(label)}.dita",
                items=list(by_component[key]),
                groups=_group_in_order(by_component[key]),
            ))
        return plans

    return [TopicPlan(
        slug=base_slug,
        title=release_title,
        filename=f"{base}.dita",
        items=notes,
        groups=_group_in_order(notes),
    )]


# ── Topic XML ────────────────────────────────────────────────────────────────────────

def note_element(item: ReleaseNoteItem, tag: str = "div") -> etree._Element:
    """A note's stored content inside `tag`, identified so the workspace can find it again.

    The id and `outputclass="release-note"` go on whatever element holds the content. The
    workspace maps rendered DITA back to a note through exactly that pair, so every mode
    must keep stamping it — see build_topic_xml and the preview in workspace.component.ts.
    """
    content = item.dita_content or plain_text_fragment(item.fragment_id, item.title, item.summary)
    try:
        el = etree.fromstring(f"<{tag}>{content}</{tag}>", _parser())
    except etree.XMLSyntaxError:
        fallback = plain_text_fragment(item.fragment_id, item.title, item.summary)
        el = etree.fromstring(f"<{tag}>{fallback}</{tag}>", _parser())
    el.set("id", item.fragment_id)
    el.set("outputclass", "release-note")
    return el


@dataclass(frozen=True)
class Layout:
    """The resolved layout. See schemas.TopicLayout for what each field means."""

    mode: str = "structured"
    template: str = ""
    guidance: str = ""
    group_heading: str = "section"
    notes_wrapper: str = "none"
    note_element: str = "div"
    shortdesc: str = "omit"
    shortdesc_text: str = ""

    @classmethod
    def of(cls, instruction_set) -> "Layout":
        """The layout an instruction set asks for, falling back to today's shape.

        Anything unreadable gives the default rather than raising: a release that cannot be
        assembled is worse than one assembled the old way, and the editor validates on save.
        """
        stored = getattr(instruction_set, "layout", None) or {}
        if not isinstance(stored, dict):
            return cls()
        options = stored.get("structured") or {}
        if not isinstance(options, dict):
            options = {}
        template = (stored.get("template") or {}) if isinstance(stored.get("template"), dict) else {}
        agent = (stored.get("agent") or {}) if isinstance(stored.get("agent"), dict) else {}
        mode = stored.get("mode") if stored.get("mode") in ("structured", "template", "agent") else "structured"

        fields = {f.name for f in dataclasses.fields(cls)} - {"mode", "template", "guidance"}
        resolved = cls(
            mode=mode,
            template=str(template.get("dita") or ""),
            guidance=str(agent.get("guidance") or ""),
            **{k: v for k, v in options.items() if k in fields and isinstance(v, str)},
        )
        # A template mode with no template cannot build anything; the schema refuses to
        # store that, but a hand-edited row should degrade rather than fail every run.
        if resolved.mode == "template" and not resolved.template.strip():
            return dataclasses.replace(resolved, mode="structured")
        return resolved


def _add_shortdesc(topic: etree._Element, layout: Layout, shortdesc: Optional[str]) -> None:
    """A caller-supplied shortdesc wins; otherwise the layout decides."""
    if shortdesc:
        etree.SubElement(topic, "shortdesc").text = shortdesc
    elif layout.shortdesc == "empty":
        etree.SubElement(topic, "shortdesc")
    elif layout.shortdesc == "text" and layout.shortdesc_text.strip():
        etree.SubElement(topic, "shortdesc").text = layout.shortdesc_text.strip()


def _group_container(body: etree._Element, slug: str, index: int, name: str, layout: Layout):
    """Where a group's notes go, and the heading that introduces them.

    Returns the element the notes are appended to. With a section heading the notes live
    inside the section; with a paragraph or no heading they sit directly in the body —
    which is what lets a <ul> follow a <p><b>Group</b></p> as a sibling, the shape a
    section cannot produce.
    """
    if layout.group_heading == "section":
        section = etree.SubElement(body, "section", id=f"{slug}-g{index}")
        etree.SubElement(section, "title").text = name or "Other changes"
        host = section
    else:
        if layout.group_heading == "paragraph":
            para = etree.SubElement(body, "p")
            etree.SubElement(para, "b").text = name or "Other changes"
        host = body

    if layout.notes_wrapper in ("ul", "ol"):
        return etree.SubElement(host, layout.notes_wrapper)
    return host


def build_topic_xml(
    plan: TopicPlan,
    shortdesc: Optional[str] = None,
    layout: Optional[Layout] = None,
) -> str:
    """A complete, DTD-valid DITA topic for one plan, laid out as the layout asks."""
    layout = layout or Layout()
    # The agent mode resolves to a template before it gets here — assemble_job_topics
    # passes the one the run settled on. Without it (a release assembled before its first
    # run) the structured options apply, which is the sane shape rather than no topic.
    if layout.mode in ("template", "agent") and layout.template.strip():
        return build_topic_from_template(plan, layout.template)
    topic = etree.Element("topic", id=plan.slug)
    title = etree.SubElement(topic, "title")
    title.text = plan.title
    _add_shortdesc(topic, layout, shortdesc)
    body = etree.SubElement(topic, "body")

    has_groups = any(name for name, _ in plan.groups)
    if not plan.items:
        para = etree.SubElement(body, "p")
        para.text = "No release notes."
    elif has_groups:
        for index, (name, group_items) in enumerate(plan.groups, start=1):
            host = _group_container(body, plan.slug, index, name, layout)
            for item in group_items:
                host.append(note_element(item, layout.note_element))
    else:
        # No groups: the wrapper still applies, so <li> notes remain inside a list.
        host = body
        if layout.notes_wrapper in ("ul", "ol"):
            host = etree.SubElement(body, layout.notes_wrapper)
        for _, group_items in plan.groups:
            for item in group_items:
                host.append(note_element(item, layout.note_element))

    xml = etree.tostring(topic, encoding="unicode", pretty_print=True)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n{xml}'



# ── Template layout ──────────────────────────────────────────────────────────────────

#: The element repeated once per group, and the element its notes are placed in. Markers
#: rather than a bespoke syntax so the template stays a real DITA topic — it can be opened
#: in an editor, validated, and carry whatever else a house template carries.
GROUP_MARKER = "rn-group"
NOTES_MARKER = "rn-notes"

#: A <ul>/<ol> host means the notes are list items; anything else holds blocks.
_LIST_HOSTS = {"ul", "ol", "sl"}


def _marked(root: etree._Element, marker: str) -> Optional[etree._Element]:
    for el in root.iter():
        if isinstance(el.tag, str) and marker in (el.get("outputclass") or "").split():
            return el
    return None


def _strip_marker(el: etree._Element, marker: str) -> None:
    """Take the marker out of the output; keep any other classes the author set."""
    classes = [c for c in (el.get("outputclass") or "").split() if c != marker]
    if classes:
        el.set("outputclass", " ".join(classes))
    else:
        el.attrib.pop("outputclass", None)


def _fill_tokens(el: etree._Element, **values: str) -> None:
    """Replace {token} in text and tails, in place."""
    for node in el.iter():
        if not isinstance(node.tag, str):
            continue
        for attr in ("text", "tail"):
            text = getattr(node, attr)
            if not text:
                continue
            for name, value in values.items():
                text = text.replace("{" + name + "}", value)
            setattr(node, attr, text)


def template_errors(dita: str) -> List[str]:
    """What is wrong with a template, for the editor to show before it is saved.

    Checked here rather than at assembly time: a template that cannot build a topic should
    be refused when it is written, not discovered the next time a release runs.
    """
    text = (dita or "").strip()
    if not text:
        return []  # empty is only an error once the mode is chosen; TopicLayout says so

    try:
        root = etree.fromstring(_strip_wrappers(text), _parser())
    except etree.XMLSyntaxError as exc:
        return [f"Not well-formed XML: {exc}"]

    errors = []
    if root.tag != "topic":
        errors.append(f"The template must be a <topic>; this one is a <{root.tag}>.")
    if _marked(root, NOTES_MARKER) is None:
        errors.append(
            f'Nothing in the template says where the notes go. Put outputclass="{NOTES_MARKER}" '
            "on the element that should hold them."
        )
    if root.find("title") is None:
        errors.append("The template needs a <title>.")
    return errors


def build_topic_from_template(plan: TopicPlan, template: str) -> str:
    """A topic built by filling the writer's own template.

    The group block is repeated per group and the notes placed inside it. With no group
    block, every note goes into the notes host once — which is what a template that does
    not care about groups looks like.
    """
    root = etree.fromstring(_strip_wrappers(template), _parser())
    root.set("id", plan.slug)
    _fill_tokens(root, title=plan.title)

    group_block = _marked(root, GROUP_MARKER)
    notes_host = _marked(root, NOTES_MARKER)
    if notes_host is None:
        raise FragmentError("The topic template does not say where the notes go", template_errors(template))

    def place(host: etree._Element, items) -> None:
        tag = "li" if host.tag in _LIST_HOSTS else "div"
        for child in list(host):          # the author's sample content
            host.remove(child)
        host.text = None
        for item in items:
            host.append(note_element(item, tag))
        _strip_marker(host, NOTES_MARKER)

    if group_block is None:
        place(notes_host, plan.items)
        return _serialize_topic(root)

    parent = group_block.getparent()
    index = parent.index(group_block)
    parent.remove(group_block)

    for offset, (name, group_items) in enumerate(plan.groups):
        block = copy.deepcopy(group_block)
        _fill_tokens(block, group=name or "Other changes")
        host = _marked(block, NOTES_MARKER)
        if host is None:
            raise FragmentError(
                "The notes marker must be inside the repeated group block",
                [f'outputclass="{NOTES_MARKER}" was not found inside the group block'],
            )
        place(host, group_items)
        _strip_marker(block, GROUP_MARKER)
        parent.insert(index + offset, block)

    return _serialize_topic(root)


def _serialize_topic(root: etree._Element) -> str:
    xml = etree.tostring(root, encoding="unicode", pretty_print=True)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n{xml}'


def validate_topic(xml: str, validator: Optional[DitaValidator] = None) -> List[str]:
    validator = validator or DitaValidator()
    valid, errors = validator.validate_with_dtd(xml)
    return [] if valid else clean_errors(errors)


def render_topic_html(xml: str) -> Tuple[str, List[str]]:
    """Render a topic for the workspace; a render failure becomes a warning, not an error."""
    try:
        result = DitaRenderer(heading_offset=1).render(xml)
    except DitaParseError as exc:
        return f"<p class=\"render-error\">{escape(str(exc))}</p>", [str(exc)]
    return result.html, list(result.warnings)
