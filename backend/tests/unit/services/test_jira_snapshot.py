"""Change detection between a job's issue snapshot and fresh Jira tickets."""

from types import SimpleNamespace

from app.models.schemas import JiraTicket
from app.services.jira_snapshot import content_hash, describe_diff, diff_fields, ticket_fields


def _ticket(**overrides):
    base = dict(
        key="MARS-1", summary="Faster search", description="Search is faster", issue_type="Story",
        status="Done", priority="High", labels=["search"], components=["Web"], fix_versions=["2026.10"],
        comments=["first comment"], custom_fields={"customfield_10020": "rank-1"},
        assignee="Pat", created="2026-01-01", updated="2026-01-02", url="https://x/browse/MARS-1",
    )
    base.update(overrides)
    return JiraTicket(**base)


def _snapshot(ticket):
    fields = ticket_fields(ticket)
    return SimpleNamespace(**fields, content_hash=content_hash(ticket))


class TestContentHash:
    def test_same_content_hashes_the_same(self):
        assert content_hash(_ticket()) == content_hash(_ticket())

    def test_custom_fields_and_bookkeeping_do_not_change_the_hash(self):
        a = _ticket()
        b = _ticket(custom_fields={"customfield_10020": "rank-99"}, updated="2026-05-05", assignee="Someone else")
        assert content_hash(a) == content_hash(b)

    def test_status_change_changes_the_hash(self):
        assert content_hash(_ticket()) != content_hash(_ticket(status="In Progress"))

    def test_new_comment_changes_the_hash(self):
        assert content_hash(_ticket()) != content_hash(_ticket(comments=["first comment", "second"]))


class TestDiff:
    def test_reports_each_changed_field(self):
        before = _snapshot(_ticket())
        after = _ticket(status="Released", summary="Much faster search", comments=["first comment", "ship it"])
        changes = diff_fields(before, after)
        assert set(changes) == {"status", "summary", "comments"}
        assert changes["status"] == {"label": "Status", "from": "Done", "to": "Released"}
        assert changes["comments"]["added"] == ["ship it"]

    def test_unchanged_ticket_has_no_diff(self):
        assert diff_fields(_snapshot(_ticket()), _ticket()) == {}

    def test_description_is_summarized_not_dumped(self):
        before = _snapshot(_ticket(description="x" * 1000))
        changes = diff_fields(before, _ticket(description="y" * 1000))
        assert len(changes["description"]["from"]) < 320

    def test_describe_diff_reads_like_a_sentence(self):
        before = _snapshot(_ticket())
        after = _ticket(status="Released", description="new text", comments=["first comment", "a", "b"])
        text = describe_diff(diff_fields(before, after))
        assert "Status: Done → Released" in text
        assert "Description changed" in text
        assert "2 new comments" in text
