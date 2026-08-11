"""Tests for the photo-gallery sensor slice (FEAT-13)."""

from __future__ import annotations

import datetime as dt
from datetime import timezone

from custom_components.taskmate.models import Child, ChoreCompletion
from custom_components.taskmate.sensor import _build_photo_gallery

UTC = timezone.utc


def _common(children, completions):
    return {
        "child_lookup": {c.id: c for c in children},
        "chore_lookup": {},
        "all_completions": completions,
    }


def _comp(cid, when, photo="", approved=True):
    return ChoreCompletion(chore_id="x", child_id=cid, completed_at=when, approved=approved, photo_url=photo)


def test_gallery_includes_only_photos_newest_first():
    kids = [Child(name="Alex", id="k1")]
    comps = [
        _comp("k1", dt.datetime(2026, 4, 1, 9, 0, tzinfo=UTC), photo="/api/taskmate/photo/a.jpg"),
        _comp("k1", dt.datetime(2026, 4, 3, 9, 0, tzinfo=UTC), photo="/api/taskmate/photo/b.jpg"),
        _comp("k1", dt.datetime(2026, 4, 2, 9, 0, tzinfo=UTC)),  # no photo -> excluded
    ]
    out = _build_photo_gallery(_common(kids, comps))
    assert [o["photo_url"] for o in out] == ["/api/taskmate/photo/b.jpg", "/api/taskmate/photo/a.jpg"]
    assert out[0]["child_name"] == "Alex"


def test_gallery_respects_limit():
    kids = [Child(name="Alex", id="k1")]
    comps = [
        _comp("k1", dt.datetime(2026, 4, d, 9, 0, tzinfo=UTC), photo=f"/api/taskmate/photo/{d}.jpg")
        for d in range(1, 10)
    ]
    out = _build_photo_gallery(_common(kids, comps), limit=3)
    assert len(out) == 3


def test_gallery_empty_when_no_photos():
    kids = [Child(name="Alex", id="k1")]
    comps = [_comp("k1", dt.datetime(2026, 4, 1, 9, 0, tzinfo=UTC))]
    assert _build_photo_gallery(_common(kids, comps)) == []
