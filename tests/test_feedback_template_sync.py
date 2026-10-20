"""The panel's Help & feedback link must match the GitHub issue templates.

GitHub fills a form field from the link only when the query key is the
field's ``id``, and it never pre-selects a drop-down — so every required field
must be a text field, and the answers the panel sends must be the template's
own wording, word for word. Editing a template without the panel (or the other
way round) would silently stop pre-filling, so this pins the two together.
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PANEL = (ROOT / "custom_components/taskmate/www/taskmate-panel.js").read_text(encoding="utf-8")
TEMPLATES = ROOT / ".github/ISSUE_TEMPLATE"


def _template(name: str) -> dict:
    return yaml.safe_load((TEMPLATES / name).read_text(encoding="utf-8"))


def _field_ids(template: dict) -> set[str]:
    return {b["id"] for b in template["body"] if "id" in b}


def _field(template: dict, field_id: str) -> dict:
    return next(b for b in template["body"] if b.get("id") == field_id)


def _options(template: dict, field_id: str) -> list[str]:
    return _field(template, field_id)["attributes"]["options"]


def _listed_answers(template: dict, field_id: str) -> list[str]:
    """The answers a text field's description lists: "One of: a, b, c. Found in …"."""
    desc = _field(template, field_id)["attributes"]["description"]
    listed = desc.split("One of:", 1)[1].split(". Found in", 1)[0]
    return [a.strip() for a in listed.split(", ")]


def _panel_values(const: str) -> list[str]:
    start = PANEL.index(f"const {const} = [")
    block = PANEL[start:]
    if "].map(" in block[: block.index("];") + 2]:
        block = block[: block.index("].map(")]
        return re.findall(r'\["\w+", "([^"]+)"\]', block)
    return re.findall(r'v: "([^"]+)"', block[: block.index("];")])


def _object_keys(body: str) -> set[str]:
    """`key: value` pairs plus shorthand properties (`additional,`) of a fields object."""
    return set(re.findall(r"\b([a-z_]+):", body)) | set(re.findall(r"(?:^|,)\s*([a-z_]+),\s*\n\s*\};", body, re.M))


BUG = _template("bug_report.yml")
FEATURE = _template("feature_request.yml")


def test_template_file_names_match():
    assert 'feedbackIssueUrl("bug_report.yml"' in PANEL
    assert 'feedbackIssueUrl("feature_request.yml"' in PANEL


def test_bug_link_keys_are_bug_template_field_ids():
    start = PANEL.index("const fields = {\n      taskmate_version:")
    body = PANEL[start : PANEL.index("const title = `[Bug]:", start)]
    keys = _object_keys(body) | {"logs"}
    assert {"taskmate_version", "description", "steps", "additional"} <= keys, keys
    assert keys <= _field_ids(BUG), keys - _field_ids(BUG)


def test_feature_link_keys_are_feature_template_field_ids():
    start = PANEL.index("const fields = {\n        summary:")
    body = PANEL[start : PANEL.index('feedbackIssueUrl("feature_request.yml"', start)]
    keys = _object_keys(body)
    assert {"summary", "problem", "children_count", "use_case"} <= keys, keys
    assert keys <= _field_ids(FEATURE), keys - _field_ids(FEATURE)


def test_title_prefixes_match_the_templates():
    assert BUG["title"].strip() == "[Bug]:"
    assert FEATURE["title"].strip() == "[Feature]:"
    assert "`[Bug]: ${" in PANEL and "`[Feature]: ${" in PANEL


def test_no_required_field_is_a_dropdown():
    """GitHub can't pre-select a drop-down, so a required one would undo the panel's pre-fill."""
    for name, template in (("bug", BUG), ("feature", FEATURE)):
        required_dropdowns = [
            b["id"]
            for b in template["body"]
            if b["type"] == "dropdown" and (b.get("validations") or {}).get("required")
        ]
        assert not required_dropdowns, f"{name}: {required_dropdowns}"


def test_install_answers_are_the_ones_the_text_fields_list():
    for const, field_id in (
        ("FEEDBACK_INSTALL_TYPES", "ha_install_type"),
        ("FEEDBACK_INSTALL_METHODS", "install_method"),
        ("FEEDBACK_LOVELACE_MODES", "lovelace_mode"),
    ):
        assert _field(BUG, field_id)["type"] == "input", field_id
        assert _panel_values(const) == _listed_answers(BUG, field_id), const


def test_every_dropdown_answer_is_a_template_option():
    for const, template, field_id in (
        ("FEEDBACK_BUG_AREAS", BUG, "affected_area"),
        ("FEEDBACK_FEATURE_AREAS", FEATURE, "area"),
        ("FEEDBACK_REPRO", BUG, "reproducible"),
        ("FEEDBACK_PRIORITY", FEATURE, "priority"),
    ):
        values = _panel_values(const)
        assert values, const
        missing = [v for v in values if v not in _options(template, field_id)]
        assert not missing, f"{const}: {missing}"


def test_the_panel_offers_every_affected_area():
    assert _panel_values("FEEDBACK_BUG_AREAS") == _options(BUG, "affected_area")
    assert _panel_values("FEEDBACK_FEATURE_AREAS") == _options(FEATURE, "area")
