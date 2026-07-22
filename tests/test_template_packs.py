"""Community template packs (#688).

Export custom templates as a shareable pack; import one that somebody else
made. A pack is arbitrary user-supplied JSON, so import validates everything
and drops every field it doesn't recognise.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from .test_coordinator_logic import _make_coord

PACK_FORMAT = "taskmate.template-pack"


def _coord(custom=()):
    coord = _make_coord()
    store = list(custom)
    coord.storage.get_custom_templates = MagicMock(return_value=store)
    coord.storage.add_custom_template = MagicMock(side_effect=store.append)
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord._store = store
    return coord


def _tpl(name="Morning", chores=None, tid="t1"):
    return {
        "id": tid, "name": name, "icon": "mdi:sun", "builtin": False,
        "chores": chores or [{"name": "Make bed", "points": 2, "time_category": "morning"}],
    }


def _pack(templates=None, **over):
    pack = {
        "format": PACK_FORMAT, "version": 1,
        "templates": templates if templates is not None else [
            {"name": "Shared routine", "icon": "mdi:sun",
             "chores": [{"name": "Make bed", "points": 2}]},
        ],
    }
    pack.update(over)
    return pack


class TestExport:
    def test_exports_custom_templates(self):
        pack = _coord([_tpl()]).export_templates()
        assert pack["format"] == PACK_FORMAT
        assert pack["version"] == 1
        assert [t["name"] for t in pack["templates"]] == ["Morning"]

    def test_can_export_a_subset(self):
        coord = _coord([_tpl(tid="t1"), _tpl(name="Bedtime", tid="t2")])
        pack = coord.export_templates(["t2"])
        assert [t["name"] for t in pack["templates"]] == ["Bedtime"]

    def test_unknown_chore_fields_are_stripped(self):
        """Runtime state must never travel in a shared pack."""
        tpl = _tpl(chores=[{"name": "Bed", "points": 2, "skip_date": "2026-01-01", "id": "x"}])
        chore = _coord([tpl]).export_templates()["templates"][0]["chores"][0]
        assert "skip_date" not in chore
        assert "id" not in chore
        assert chore["points"] == 2

    def test_no_custom_templates_exports_an_empty_pack(self):
        pack = _coord([]).export_templates()
        assert pack["templates"] == []


class TestImportValidation:
    def _fails(self, coord, pack, match):
        with pytest.raises(ValueError, match=match):
            coord._validate_pack(pack)

    def test_rejects_a_non_dict(self):
        self._fails(_coord(), ["nope"], "doesn't look like")

    def test_rejects_a_foreign_format(self):
        self._fails(_coord(), _pack(format="someone-elses-app"), "Not a TaskMate")

    def test_rejects_a_future_version(self):
        """Better to say "you need a newer TaskMate" than to guess."""
        self._fails(_coord(), _pack(version=99), "newer TaskMate")

    def test_rejects_a_non_numeric_version(self):
        self._fails(_coord(), _pack(version="two"), "not a number")

    def test_rejects_an_empty_pack(self):
        self._fails(_coord(), _pack(templates=[]), "no templates")

    def test_rejects_too_many_templates(self):
        many = [{"name": f"T{i}", "chores": [{"name": "c"}]} for i in range(51)]
        self._fails(_coord(), _pack(templates=many), "too many templates")

    def test_rejects_a_nameless_template(self):
        self._fails(_coord(), _pack(templates=[{"chores": [{"name": "c"}]}]), "no name")

    def test_rejects_a_template_with_no_chores(self):
        self._fails(_coord(), _pack(templates=[{"name": "T", "chores": []}]), "no chores")

    def test_rejects_a_nameless_chore(self):
        self._fails(_coord(), _pack(templates=[{"name": "T", "chores": [{"points": 1}]}]), "no name")

    def test_rejects_a_malformed_chore(self):
        self._fails(_coord(), _pack(templates=[{"name": "T", "chores": ["nope"]}]), "malformed chore")

    def test_drops_unknown_chore_fields(self):
        """A shared pack must not be able to set fields the panel wouldn't."""
        pack = _pack(templates=[{"name": "T", "chores": [
            {"name": "c", "points": 3, "assignment_current_child_id": "kid1", "enabled": False},
        ]}])
        chore = _coord()._validate_pack(pack)[0]["chores"][0]
        assert "assignment_current_child_id" not in chore
        assert chore["points"] == 3

    def test_long_names_are_truncated_not_rejected(self):
        pack = _pack(templates=[{"name": "N" * 500, "chores": [{"name": "c" * 500}]}])
        clean = _coord()._validate_pack(pack)[0]
        assert len(clean["name"]) == 120
        assert len(clean["chores"][0]["name"]) == 200


class TestImport:
    @pytest.mark.asyncio
    async def test_imports_a_pack(self):
        coord = _coord()
        result = await coord.async_import_pack(_pack())
        assert result["imported"] == 1
        assert coord._store[0]["name"] == "Shared routine"
        assert coord._store[0]["builtin"] is False
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_a_clashing_name_is_suffixed_not_overwritten(self):
        """An import must never silently replace something the family built."""
        coord = _coord([_tpl(name="Shared routine")])
        await coord.async_import_pack(_pack())
        assert [t["name"] for t in coord._store] == ["Shared routine", "Shared routine (2)"]

    @pytest.mark.asyncio
    async def test_repeated_imports_keep_counting_up(self):
        coord = _coord([_tpl(name="Shared routine")])
        await coord.async_import_pack(_pack())
        await coord.async_import_pack(_pack())
        assert [t["name"] for t in coord._store][-1] == "Shared routine (3)"

    @pytest.mark.asyncio
    async def test_imported_templates_get_fresh_ids(self):
        coord = _coord()
        await coord.async_import_pack(_pack())
        await coord.async_import_pack(_pack())
        assert coord._store[0]["id"] != coord._store[1]["id"]

    @pytest.mark.asyncio
    async def test_a_bad_pack_writes_nothing(self):
        coord = _coord()
        with pytest.raises(ValueError):
            await coord.async_import_pack(_pack(format="nope"))
        assert coord._store == []
        coord.storage.async_save.assert_not_awaited()


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_export_then_import_preserves_the_template(self):
        source = _coord([_tpl(chores=[
            {"name": "Make bed", "points": 2, "time_category": "morning",
             "due_days": ["monday"], "requires_approval": False},
        ])])
        pack = source.export_templates()

        target = _coord()
        await target.async_import_pack(pack)
        imported = target._store[0]
        assert imported["name"] == "Morning"
        assert imported["chores"][0]["points"] == 2
        assert imported["chores"][0]["due_days"] == ["monday"]
