"""The admin panel keeps clear of a phone's notch and home indicator (#1140).

HA 2026.8+ pads every custom panel by the safe-area insets unless the panel
opts out with ``handle_safe_area``. The panel is a 100dvh flex column, so that
padding pushed it — and its phone bottom bar — off the bottom of an iPhone.
The panel opts out where the core supports it and pads itself instead.
"""

from __future__ import annotations

import asyncio
import pathlib
import re
from types import SimpleNamespace

import pytest

from custom_components.taskmate import panel

PANEL_JS = (
    pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"
)


class _Hass:
    def __init__(self):
        self.data = {}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.fixture
def new_core(monkeypatch):
    calls = []

    async def async_register_panel(
        hass,
        frontend_url_path,
        webcomponent_name,
        sidebar_title=None,
        sidebar_icon=None,
        js_url=None,
        module_url=None,
        embed_iframe=False,
        trust_external=True,
        config=None,
        require_admin=False,
        config_panel_domain=None,
        handle_safe_area=False,
    ):
        calls.append({"handle_safe_area": handle_safe_area})

    monkeypatch.setattr(panel, "panel_custom", SimpleNamespace(async_register_panel=async_register_panel))
    return calls


@pytest.fixture
def old_core(monkeypatch):
    calls = []

    async def async_register_panel(
        hass,
        frontend_url_path,
        webcomponent_name,
        sidebar_title=None,
        sidebar_icon=None,
        js_url=None,
        module_url=None,
        embed_iframe=False,
        trust_external=True,
        config=None,
        require_admin=False,
        config_panel_domain=None,
    ):
        calls.append({})

    monkeypatch.setattr(panel, "panel_custom", SimpleNamespace(async_register_panel=async_register_panel))
    return calls


def test_opts_out_of_ha_safe_area_padding_where_supported(new_core):
    asyncio.run(panel.async_register_panel(_Hass()))
    assert new_core == [{"handle_safe_area": True}]


def test_older_core_without_the_argument_still_registers(old_core):
    # The 2024.7 floor has no handle_safe_area; passing it would TypeError
    # and leave the panel unregistered.
    asyncio.run(panel.async_register_panel(_Hass()))
    assert old_core == [{}]


def _rule(src: str, selector: str) -> str:
    match = re.search(r"(?:^|\n)\s*" + re.escape(selector) + r"\s*\{(.*?)\}", src, re.DOTALL)
    assert match, f"no CSS rule found for {selector}"
    return re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)


def test_panel_pads_itself_by_every_inset_using_has_variables():
    rules = _rule(PANEL_JS.read_text(encoding="utf-8"), "taskmate-panel")
    assert "box-sizing: border-box" in rules, "the insets must sit inside the 100dvh, not add to it"
    # HA's own variables first: they carry the app's insets and HA's debug
    # simulator, and the content-inset ones already allow for HA's sidebar.
    for var in (
        "--safe-area-inset-top",
        "--safe-area-inset-bottom",
        "--safe-area-content-inset-left",
        "--safe-area-content-inset-right",
    ):
        assert f"var({var}" in rules, f"panel padding ignores {var}"


def test_phone_bottom_bar_takes_the_bottom_inset():
    src = PANEL_JS.read_text(encoding="utf-8")
    phone = src[src.index("@media (max-width: 900px)", src.index("/* Phone bottom bar")) :]
    assert re.search(r"taskmate-panel\s*\{\s*padding-bottom:\s*0;", phone), (
        "on phones the host must drop its bottom padding, or the inset is counted twice"
    )
    bnav = _rule(phone, ".tm-bnav")
    assert "padding-bottom: var(--safe-area-inset-bottom" in bnav


def test_no_raw_env_insets_left_in_the_panel():
    # Raw env() misses HA's --safe-area-inset-* overrides; always go through
    # the variable with env() as the fallback.
    src = PANEL_JS.read_text(encoding="utf-8")
    raw = [m.start() for m in re.finditer(r"(?<!, )env\(safe-area-inset", src)]
    assert raw == [], "use var(--safe-area-inset-*, env(...)) rather than a bare env()"
