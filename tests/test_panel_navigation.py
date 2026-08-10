"""Every panel view must be reachable from the sidebar.

The audit view shipped fully implemented — render function, clear-log button,
styles, websocket commands and a wiki page — but it was missing from
`_sidebarGroups()`. The nav is built solely from that list, so there was no way
to open it. Nothing failed; the tab was simply invisible.
"""

from __future__ import annotations

import pathlib
import re

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")


def _tab_ids() -> list[str]:
    """The ids declared in the TABS constant."""
    block = re.search(r"const TABS = \[(.*?)\n\];", PANEL, re.S)
    assert block, "could not find the TABS constant"
    return re.findall(r'id:\s*"([a-z_]+)"', block.group(1))


def _rendered_ids() -> set[str]:
    """Ids the render switch actually has a case for."""
    return set(re.findall(r'case "([a-z_]+)":\s*return this\._render', PANEL))


def _sidebar_ids() -> set[str]:
    """Ids listed in the sidebar groups — the only source the nav renders from."""
    start = PANEL.index("_sidebarGroups() {")
    end = PANEL.index("_sidebar() {", start)
    return set(re.findall(r'\{\s*id:\s*"([a-z_]+)"', PANEL[start:end]))


class TestEveryViewIsReachable:
    def test_audit_is_in_the_sidebar(self):
        assert "audit" in _sidebar_ids(), (
            "the audit view has a render case but no sidebar entry, so it cannot be opened"
        )

    def test_every_rendered_view_has_a_sidebar_entry(self):
        rendered = _rendered_ids()
        sidebar = _sidebar_ids()
        assert rendered, "expected to find render cases"
        unreachable = sorted(rendered - sidebar)
        assert unreachable == [], f"views with a render case but no way to navigate to them: {unreachable}"

    def test_no_sidebar_entry_points_at_a_missing_view(self):
        """The mirror image: a nav item that renders nothing."""
        dangling = sorted(_sidebar_ids() - _rendered_ids())
        assert dangling == [], f"sidebar entries with no render case: {dangling}"

    def test_every_sidebar_label_key_exists_in_every_locale(self):
        import json

        start = PANEL.index("_sidebarGroups() {")
        end = PANEL.index("_sidebar() {", start)
        keys = set(re.findall(r'this\._t\("(panel\.tab_[a-z_]+)"\)', PANEL[start:end]))
        assert keys, "expected sidebar labels to come from translation keys"

        for path in sorted((WWW / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = sorted(k for k in keys if k not in data)
            assert missing == [], f"{path.name} is missing {missing}"


class TestNarrowWidthAffordances:
    """Faults found auditing the panel and cards down to a 320px viewport."""

    def test_entity_id_chips_truncate_rather_than_wrap(self):
        """An entity id left to wrap splits mid-token and tears the pill
        background across two lines."""
        rule = re.search(r"\.tm-meta code \{([^}]*)\}", PANEL)
        assert rule, "could not find the .tm-meta code rule"
        body = rule.group(1)
        assert "text-overflow: ellipsis" in body
        assert "white-space: nowrap" in body

    def test_the_approval_pill_is_a_usable_tap_target(self):
        """It is the panel's only route into the pending-approvals queue."""
        rule = re.search(r"\.tm-approval-pill \{([^}]*)\}", PANEL)
        assert rule
        m = re.search(r"min-height:\s*(\d+)px", rule.group(1))
        assert m and int(m.group(1)) >= 32, "approval pill is too small to tap"

    def test_parent_dashboard_tabs_stay_reachable_when_narrow(self):
        """Flex items refuse to shrink below their content, so the last tab was
        clipped off the card edge with no way to scroll to it."""
        src = (WWW / "taskmate-parent-dashboard-card.js").read_text(encoding="utf-8")
        rule = re.search(r"\.tab-nav \{([^}]*)\}", src)
        assert rule
        assert "flex-wrap: wrap" in rule.group(1)
