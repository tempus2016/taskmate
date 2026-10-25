"""scripts/build_manual.py — the wiki bundle behind the admin panel's Manual.

The page HTML goes into the panel with innerHTML, so the sanitiser is the
security boundary: these pin that it keeps plain document markup, drops
anything that runs, and writes the panel's own link attributes itself.

The full build needs the docs toolchain (markdown, pymdown-extensions); CI runs
it in the Data files job (`build_manual.py --check`). The sanitiser and the nav
reader need only the standard library and PyYAML, so they are tested here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_manual", ROOT / "scripts" / "build_manual.py")
bm = importlib.util.module_from_spec(_spec)
sys.modules["build_manual"] = bm
_spec.loader.exec_module(bm)

KNOWN = {"Chores", "Vacation-Mode", "index"}
SITE = bm.SITE


def clean(html: str, slug: str = "Chores") -> str:
    return bm.sanitize(html, slug, KNOWN)


def test_plain_markup_survives():
    html = '<h2 id="fields">Fields</h2><p><strong>Points</strong> and <code>due_days</code></p><table><tr><td style="text-align: left;">x</td></tr></table>'
    out = clean(html)
    assert '<h2 id="tmdoc-fields">Fields</h2>' in out
    assert "<strong>Points</strong>" in out
    assert "<code>due_days</code>" in out
    assert '<td style="text-align: left;">x</td>' in out


@pytest.mark.parametrize(
    "html",
    [
        "<script>alert(1)</script>",
        '<img src="images/a.png" onerror="alert(1)">',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="data:text/html,<script>alert(1)</script>">x</a>',
        '<p style="background:url(javascript:alert(1))">x</p>',
        "<iframe src=https://evil.example></iframe>",
        "<svg><script>alert(1)</script></svg>",
        '<a href="x" data-act="delete-child" data-id="k1">x</a>',
        "<style>body{display:none}</style>",
        '<form action="https://evil.example"><input name="q"></form>',
    ],
)
def test_nothing_that_runs_survives(html):
    out = clean(html).lower()
    for bad in (
        "<script",
        "onerror",
        "javascript:",
        "data:text",
        "<iframe",
        "<svg",
        "<style",
        "<form",
        "<input",
        "background",
        "delete-child",
    ):
        assert bad not in out, (bad, out)


def test_escaped_text_stays_escaped():
    assert clean("<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>") == "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"


def test_attribute_values_are_re_escaped():
    out = clean('<img src="images/a.png" alt="&quot; onload=&quot;x">')
    assert 'alt="&quot; onload=&quot;x"' in out
    assert "onload=" not in out.replace("&quot; onload=&quot;", "")


def test_links_to_other_manual_pages_open_in_the_panel():
    out = clean('<a href="Vacation-Mode.md#time-off">Vacation</a>')
    assert (
        f'<a href="{SITE}Vacation-Mode/#time-off" data-act="man-go" data-doc="Vacation-Mode" data-anchor="time-off">'
    ) in out


def test_same_page_anchors_stay_on_the_page():
    out = clean('<a href="#expiry-date">Expiry</a>', slug="Chores")
    assert f'href="{SITE}Chores/#expiry-date" data-act="man-go" data-doc="Chores" data-anchor="expiry-date"' in out


def test_outside_links_open_a_new_tab():
    out = clean('<a href="https://github.com/tempus2016/taskmate/issues">Issues</a>')
    assert 'href="https://github.com/tempus2016/taskmate/issues" target="_blank" rel="noopener noreferrer"' in out


def test_a_page_not_in_the_bundle_links_to_the_website():
    out = clean('<a href="Not-Bundled.md">x</a>')
    assert f'href="{SITE}Not-Bundled/" target="_blank"' in out
    assert "data-act" not in out


def test_screenshots_load_from_the_website_lazily():
    out = clean('<img alt="The Chores tab" src="images/panel-chores.png">')
    assert f'src="{SITE}images/panel-chores.png"' in out
    assert 'loading="lazy"' in out


def test_unclosed_tags_are_closed():
    assert clean("<ul><li>one<li>two").endswith("</li></ul>")


def test_nav_follows_mkdocs_order():
    nav = bm.build_nav(bm.load_mkdocs()["nav"])
    assert nav[0] == {"title": "Home", "page": "index"}
    pages = bm.nav_pages(nav)
    assert pages.index("Installation") < pages.index("Chores") < pages.index("FAQ")
    for page in pages:
        assert (ROOT / "wiki" / f"{page}.md").is_file(), page


def test_extensions_match_the_website():
    assert bm.mkdocs_extension_names(bm.load_mkdocs()) == bm.EXTENSIONS


def test_every_help_button_names_a_wiki_page():
    targets = bm.panel_help_targets()
    assert {"today", "chores", "rewards", "settings", "setup"} <= set(targets)
    for tab, (doc, _anchor) in targets.items():
        assert (ROOT / "wiki" / f"{doc}.md").is_file(), tab


def test_full_build(tmp_path):
    pytest.importorskip("pymdownx")
    bundle = bm.build(tmp_path)
    assert bm.check(bundle) == []
    assert (tmp_path / "manual.json").stat().st_size > 0
    assert (tmp_path / "manual.json.gz").stat().st_size > 0
    chores = bundle["pages"]["Chores"]
    assert chores["title"] == "Chores"
    assert chores["toc"][0]["id"].startswith("tmdoc-")
    assert "<script" not in "".join(p["html"] for p in bundle["pages"].values())
