"""Turning release note items into DITA topics.

Every note is a body-level fragment — one ``<div outputclass="release-note">`` — so notes can
be grouped under ``<section>`` headings, split across topics, and re-split later without the
writer agent rewriting anything. This module owns that fragment shape (normalizing what a
model returns into it, validating it against the DITA 1.3 DTD), the chunking strategies that
decide which notes share a topic, and the topic XML itself.
"""

from __future__ import annotations

import copy
import re
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
    """Coerce a model's output into one ``<div id=... outputclass="release-note">``.

    Accepts a bare ``<div>``, several sibling elements, or a fragment wrapped in a
    ``<section>``/``<topic>``; rejects anything that is not well-formed XML.
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

    for attr in list(div.attrib):
        if attr not in ("outputclass",):
            del div.attrib[attr]
    div.set("id", fragment_id)
    div.set("outputclass", "release-note")

    if not len(div) and not (div.text or "").strip():
        raise FragmentError("The fragment has no content")

    return etree.tostring(div, encoding="unicode", pretty_print=True).strip()


def plain_text_fragment(fragment_id: str, title: str, summary: str) -> str:
    """The fallback when a model cannot produce valid DITA: the plain summary, escaped."""
    body = escape((summary or "").strip() or title)
    return (
        f'<div id="{fragment_id}" outputclass="release-note">\n'
        f"  <p><b>{escape(title)}</b></p>\n"
        f"  <p>{body}</p>\n"
        f"</div>"
    )


def fragment_title(fragment: str) -> Optional[str]:
    """The bold lead of a fragment, if it has one."""
    try:
        div = etree.fromstring(fragment, _parser())
    except etree.XMLSyntaxError:
        return None
    first = next((c for c in div if isinstance(c.tag, str)), None)
    if first is not None and first.tag == "p" and len(first) and first[0].tag == "b":
        return "".join(first[0].itertext()).strip() or None
    return None


def _wrap_for_validation(fragment: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n'
        f'<topic id="validation"><title>Validation</title><body>{fragment}</body></topic>'
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

def _fragment_element(item: ReleaseNoteItem) -> etree._Element:
    """The item's fragment as an element, falling back to plain text if it will not parse."""
    source = item.dita_content or plain_text_fragment(item.fragment_id, item.title, item.summary)
    try:
        el = etree.fromstring(source, _parser())
    except etree.XMLSyntaxError:
        el = etree.fromstring(plain_text_fragment(item.fragment_id, item.title, item.summary), _parser())
    el.set("id", item.fragment_id)
    el.set("outputclass", "release-note")
    return el


def build_topic_xml(plan: TopicPlan, shortdesc: Optional[str] = None) -> str:
    """A complete, DTD-valid DITA topic for one plan."""
    topic = etree.Element("topic", id=plan.slug)
    title = etree.SubElement(topic, "title")
    title.text = plan.title
    if shortdesc:
        sd = etree.SubElement(topic, "shortdesc")
        sd.text = shortdesc
    body = etree.SubElement(topic, "body")

    has_groups = any(name for name, _ in plan.groups)
    if not plan.items:
        para = etree.SubElement(body, "p")
        para.text = "No release notes."
    elif has_groups:
        for index, (name, group_items) in enumerate(plan.groups, start=1):
            section = etree.SubElement(body, "section", id=f"{plan.slug}-g{index}")
            section_title = etree.SubElement(section, "title")
            section_title.text = name or "Other changes"
            for item in group_items:
                section.append(_fragment_element(item))
    else:
        for _, group_items in plan.groups:
            for item in group_items:
                body.append(_fragment_element(item))

    xml = etree.tostring(topic, encoding="unicode", pretty_print=True)
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
