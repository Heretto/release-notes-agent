"""Group ordering and note moves, on plain objects (no database)."""

from types import SimpleNamespace

from app.services.workspace_service import group_order, move_item, renumber_positions


def _job(*specs):
    items = [SimpleNamespace(id=n, group_name=g, position=p, title=t) for n, (t, g, p) in enumerate(specs)]
    return SimpleNamespace(items=items)


def _order(job):
    return [(i.title, i.group_name) for i in sorted(job.items, key=lambda i: i.position)]


class TestOrdering:
    def test_group_order_follows_first_appearance(self):
        job = _job(("a", "Fixes", 0), ("b", "Features", 1), ("c", "Fixes", 2))
        assert group_order(job) == ["Fixes", "Features"]

    def test_renumber_keeps_groups_together(self):
        job = _job(("a", "Fixes", 0), ("b", "Features", 1), ("c", "Fixes", 2), ("d", None, 3))
        renumber_positions(job, ["Features", "Fixes"])
        assert _order(job) == [("b", "Features"), ("a", "Fixes"), ("c", "Fixes"), ("d", None)]

    def test_move_to_position_within_group(self):
        job = _job(("a", "F", 0), ("b", "F", 1), ("c", "F", 2))
        move_item(job, job.items[2], None, 1)
        assert [t for t, _ in _order(job)] == ["c", "a", "b"]

    def test_move_to_another_group_appends_at_its_end(self):
        job = _job(("a", "F", 0), ("b", "F", 1), ("x", "G", 2))
        move_item(job, job.items[0], "G", None)
        assert _order(job) == [("b", "F"), ("x", "G"), ("a", "G")]

    def test_move_into_new_group_creates_it_last(self):
        job = _job(("a", "F", 0), ("b", "F", 1))
        move_item(job, job.items[1], "New", 1)
        assert _order(job) == [("a", "F"), ("b", "New")]
        assert group_order(job) == ["F", "New"]
