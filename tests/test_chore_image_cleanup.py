"""Chore images are deleted with the chore, and on replace (#750)."""

from __future__ import annotations

import pathlib
import re

SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
SRC = (SRC_DIR / "coord_chores.py").read_text(encoding="utf-8")


def _body(name: str) -> str:
    # "async def <name>(" only ever appears at the definition, so a plain
    # index() is safe here (unlike the JS method helpers, where the first
    # occurrence of a bare name is often a call site).
    start = SRC.index(f"async def {name}(")
    nxt = re.search(r"\n    (async def|def) ", SRC[start + 10 :])
    return SRC[start : start + 10 + nxt.start()] if nxt else SRC[start:]


def test_purging_a_deleted_chore_deletes_its_image():
    # A deleted chore waits 7 days in Recently deleted, picture and all; the
    # purge is what lets the file go.
    trash = (SRC_DIR / "coord_trash.py").read_text(encoding="utf-8")
    body = trash[trash.index("async def async_purge_recently_deleted(") :]
    assert "_async_release_image" in body, "taskmate_images is never orphan-swept, so an undeleted file leaks forever"


def test_replacing_an_image_deletes_the_previous_file():
    body = _body("async_update_chore")
    assert "_async_release_image" in body
    # Must compare against the pre-update value, which the method already
    # captures as `existing` for the calendar cleanup.
    assert "existing" in body


def test_cleanup_uses_the_value_captured_before_storage_is_mutated():
    # async_update_chore calls storage.update_chore early; the old URL must come
    # from the `existing` snapshot taken before that, not re-read afterwards.
    body = _body("async_update_chore")
    existing_at = body.index("existing = self.storage.get_chore")
    delete_at = body.index("_async_release_image")
    assert existing_at < delete_at


def test_the_release_helper_is_the_only_thing_that_unlinks():
    # Both cleanup paths must go through _async_release_image so the shared-file
    # check (#768) can never be bypassed by a new call site.
    assert SRC.count("images.async_delete_image") == 1
    assert "async_delete_image" in _body("_async_release_image")


def test_the_images_dir_is_not_in_the_photo_sweeper():
    coordinator = (
        pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "coordinator.py"
    ).read_text(encoding="utf-8")
    start = coordinator.index("async def _async_sweep_orphan_photos")
    body = coordinator[start : start + 800]
    assert "image" not in body, "chore images must not be swept — they are config, not evidence"
