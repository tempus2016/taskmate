"""Localised push notification text and action buttons (#1037)."""

from __future__ import annotations

import asyncio
import json
import string
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import notify_strings
from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import NotificationRoute, ParentRecipient
from custom_components.taskmate.storage import TaskMateStorage

LOCALES = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www" / "locales"


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _notify_keys(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k[len("notify.") :]: v for k, v in data.items() if k.startswith("notify.")}


@pytest.fixture(autouse=True)
def _fresh_cache():
    notify_strings._cache.clear()
    yield
    notify_strings._cache.clear()


def asyncio_run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _lang(hass, language: str):
    """Give the fake hass a language and a (synchronous) executor."""
    hass.config = MagicMock(language=language)

    async def _run(func, *args):
        return func(*args)

    hass.async_add_executor_job = _run
    return hass


def test_en_json_matches_the_baked_in_english():
    assert _notify_keys(LOCALES / "en.json") == notify_strings.DEFAULTS


@pytest.mark.parametrize("path", sorted(LOCALES.glob("*.json")), ids=lambda p: p.stem)
def test_every_translation_keeps_the_english_placeholders(path):
    strings = _notify_keys(path)
    assert set(strings) == set(notify_strings.DEFAULTS)
    for key, english in notify_strings.DEFAULTS.items():
        assert _placeholders(strings[key]) == _placeholders(english), f"{path.name}: notify.{key}"


@pytest.mark.asyncio
async def test_german_message_and_buttons(hass):
    _lang(hass, "de")
    await notify_strings.async_load(hass)
    msg = notify_strings.render(
        hass,
        "pending_chore_approval",
        {"child_name": "Alex", "chore_name": "Spülmaschine ausräumen", "points": 5, "points_name": "Punkte"},
    )
    assert msg == "Alex hat „Spülmaschine ausräumen“ erledigt (+5 Punkte) – wartet auf Freigabe."
    assert notify_strings.text(hass, "action_approve") == "Genehmigen"
    assert notify_strings.text(hass, "action_reject") == "Ablehnen"


@pytest.mark.asyncio
async def test_regional_language_uses_its_base_file(hass):
    _lang(hass, "de-CH")
    await notify_strings.async_load(hass)
    assert notify_strings.text(hass, "action_approve") == "Genehmigen"


@pytest.mark.asyncio
async def test_unknown_language_and_no_language_fall_back_to_english(hass):
    _lang(hass, "xx")
    await notify_strings.async_load(hass)
    assert notify_strings.text(hass, "action_approve") == "Approve"
    # The plain test hass has no config at all.
    assert notify_strings.text(object(), "action_reject") == "Reject"


@pytest.mark.asyncio
async def test_broken_translation_falls_back_to_english(hass):
    _lang(hass, "de")
    await notify_strings.async_load(hass)
    notify_strings._cache["de"]["level_up"] = "{child_name Level {level}"
    assert notify_strings.render(hass, "level_up", {"child_name": "Alex", "level": 3}) == "Alex reached level 3! 🎉"


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "notify_strings")
    await storage.async_load()
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = MagicMock()
    return NotificationCoordinator(hass, storage)


def _route_parent(coord, service: str) -> None:
    parent = ParentRecipient(name="Sam", notify_service=service)
    coord.storage.upsert_parent_recipient(parent)
    coord.storage.set_notification_master("pending_chore_approval", True)
    coord.storage.set_notification_route("pending_chore_approval", parent.id, NotificationRoute(enabled=True))


def _sent(hass) -> dict:
    return next(c for c in hass.services.async_call.call_args_list if c[0][0] == "notify")[0][2]


@pytest.mark.asyncio
async def test_approval_push_is_sent_in_ha_language(coord, hass):
    _lang(hass, "de")
    _route_parent(coord, "notify.mobile_app_phone")
    await coord.fire(
        "pending_chore_approval",
        {"entry_id": "c1", "child_name": "Alex", "chore_name": "Bad putzen", "points": 5, "points_name": "Punkte"},
    )
    data = _sent(hass)
    assert data["message"] == "Alex hat „Bad putzen“ erledigt (+5 Punkte) – wartet auf Freigabe."
    approve, reject = data["data"]["actions"]
    assert approve == {"action": "TASKMATE_APPROVE_c1", "title": "Genehmigen"}
    assert reject["action"] == "TASKMATE_REJECT_c1"
    assert reject["title"] == reject["textInputButtonTitle"] == "Ablehnen"
    assert reject["textInputPlaceholder"] == "Grund (optional)"


@pytest.mark.asyncio
async def test_panel_hint_is_translated_for_non_mobile_backends(coord, hass):
    _lang(hass, "fr")
    _route_parent(coord, "notify.telegram")
    await coord.fire(
        "pending_chore_approval",
        {"entry_id": "c1", "child_name": "Alex", "chore_name": "Lit", "points": 5, "points_name": "étoiles"},
    )
    assert _sent(hass)["message"].endswith("Ouvre le panneau TaskMate pour valider ou refuser.")


@pytest.mark.asyncio
async def test_custom_message_template_is_left_alone(coord, hass):
    _lang(hass, "de")
    _route_parent(coord, "notify.phone")
    await coord.fire(
        "pending_chore_approval",
        {"entry_id": "c1", "child_name": "Alex", "message_template": "Hey {child_name}"},
    )
    assert _sent(hass)["message"].startswith("Hey Alex")


def test_german_dates_months_and_name_lists(hass):
    from datetime import date

    _lang(hass, "de")
    asyncio_run(notify_strings.async_load(hass))
    assert notify_strings.short_date(hass, date(2026, 10, 4)) == "So, 4. Okt"
    assert notify_strings.month_year(hass, date(2026, 3, 1)) == "März 2026"
    assert notify_strings.join_names(hass, ["Malia", "Vaiha", "Alex"]) == "Malia, Vaiha und Alex"
    assert notify_strings.join_names(hass, ["Malia"]) == "Malia"


def test_english_dates_and_name_lists_without_a_language():
    from datetime import date

    assert notify_strings.short_date(None, date(2026, 10, 4)) == "Sun 4 Oct"
    assert notify_strings.month_year(None, date(2026, 9, 1)) == "September 2026"
    assert notify_strings.join_names(None, ["Malia", "Vaiha"]) == "Malia and Vaiha"


def test_german_recap_labels(hass):
    from datetime import date

    from custom_components.taskmate.coord_recaps import period_label

    _lang(hass, "de")
    asyncio_run(notify_strings.async_load(hass))
    assert period_label("weekly", date(2026, 9, 7), date(2026, 9, 13), hass) == "Woche"
    assert period_label("monthly", date(2026, 3, 1), date(2026, 3, 31), hass) == "März"
    assert period_label("every_3_months", date(2026, 7, 1), date(2026, 9, 30), hass) == "Jul–Sep"


def test_language_change_reloads_the_strings(hass):
    _lang(hass, "en")
    listeners = {}
    hass.bus.async_listen = lambda event, cb: listeners.setdefault(event, cb)
    tasks = []
    hass.async_create_task = tasks.append
    notify_strings.async_watch_language(hass)
    hass.config.language = "fr"
    listeners["core_config_updated"](None)
    asyncio_run(tasks[0])
    assert notify_strings.text(hass, "action_approve") == "Valider"


@pytest.mark.parametrize("path", sorted(LOCALES.glob("*.json")), ids=lambda p: p.stem)
@pytest.mark.asyncio
async def test_every_test_push_fills_its_placeholders(coord, hass, path):
    """A test push of each type, in each language, leaves no {placeholder} behind."""
    from custom_components.taskmate.coord_notifications import NOTIFICATION_TYPES

    _lang(hass, path.stem)
    parent = ParentRecipient(name="Sam", notify_service="notify.mobile_app_phone")
    coord.storage.upsert_parent_recipient(parent)
    for meta in NOTIFICATION_TYPES:
        coord.storage.set_notification_route(meta.id, parent.id, NotificationRoute(enabled=True))
        hass.services.async_call.reset_mock()
        await coord.send_test(meta.id)
        message = _sent(hass)["message"]
        assert "{" not in message, f"{path.name} {meta.id}: {message}"
        if path.stem not in ("en", "en-GB"):
            assert "Tidy room" not in message and "Movie night" not in message, f"{path.name} {meta.id}: {message}"
