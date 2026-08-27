"""Chore.image_url flows through model, websocket and sensor (#750)."""

from __future__ import annotations

import pathlib

import pytest
import voluptuous as vol

from custom_components.taskmate.models import Chore

WS = (pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "websocket.py").read_text(
    encoding="utf-8"
)
SENSOR = (pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "sensor.py").read_text(
    encoding="utf-8"
)

GOOD = "/api/taskmate/image/" + "a" * 32 + ".jpg"


def test_chore_defaults_to_no_image():
    assert Chore(name="Bins").image_url == ""


def test_chore_image_url_round_trips():
    chore = Chore(name="Bins", image_url=GOOD)
    assert chore.to_dict()["image_url"] == GOOD
    assert Chore.from_dict(chore.to_dict()).image_url == GOOD


def test_chore_from_dict_coerces_missing_and_none():
    assert Chore.from_dict({"name": "Bins"}).image_url == ""
    assert Chore.from_dict({"name": "Bins", "image_url": None}).image_url == ""


def test_image_url_is_in_the_shared_chore_payload_schema():
    # _chore_payload_schema() is spread into BOTH the add and update schemas,
    # so one entry there covers both by construction.
    start = WS.index("def _chore_payload_schema(")
    end = WS.index("\ndef ", start + 10)
    assert 'vol.Optional("image_url")' in WS[start:end]


def test_image_url_is_an_editable_field():
    # THE bug this test exists for: _CHORE_EDITABLE_FIELDS gates what actually
    # reaches the Chore object in both add and update. A field that passes the
    # schema but is missing here is silently dropped — exactly what #755 fixed
    # for `icon` on the browser side.
    from custom_components.taskmate.websocket import _CHORE_EDITABLE_FIELDS

    assert "image_url" in _CHORE_EDITABLE_FIELDS


def test_websocket_validates_the_url():
    assert "normalize_taskmate_image_url" in WS, "an unvalidated image_url would let a chore point at any URL"


def test_state_snapshot_signs_the_image_url():
    # _build_state_snapshot returns raw stored chore dicts; an unsigned URL
    # 401s in the panel's <img>.
    assert "sign_image_url" in WS


def test_chores_sensor_emits_a_signed_image_url():
    # Cards read chores from _build_chores_list; a field absent there is
    # invisible to every card no matter how good the rendering is.
    assert "image_url" in SENSOR
    assert "sign_image_url" in SENSOR


def test_image_url_is_only_emitted_when_set():
    # Mirrors how `icon` is handled — keeps records compact under the 16KB
    # recorder limit.
    assert 'record["image_url"] = ' in SENSOR


@pytest.mark.parametrize(
    "bad",
    [
        "https://evil.example/x.jpg",
        "javascript:alert(1)",
        "/api/taskmate/photo/" + "a" * 32 + ".jpg",
        "/api/taskmate/image/../../etc/passwd",
    ],
)
def test_bad_urls_are_rejected_by_the_validator(bad):
    # Test the real validator, not a vol.Any() wrapper around the predicate:
    # voluptuous treats a bare callable as a coercer, so a predicate returning
    # False is a *value*, not a failure — vol.Any("", is_taskmate_image_url)
    # would happily return False and reject nothing.
    from custom_components.taskmate.websocket import _image_url_or_blank

    with pytest.raises(vol.Invalid):
        _image_url_or_blank(bad)


@pytest.mark.parametrize("ok", ["", None, "/api/taskmate/image/" + "a" * 32 + ".png"])
def test_validator_accepts_blank_and_our_urls(ok):
    from custom_components.taskmate.websocket import _image_url_or_blank

    assert _image_url_or_blank(ok) == (ok or "")


# --- #827: the panel round-trips the *signed* URL it was given ---------------
#
# _build_state_snapshot hands the panel a signed URL so its <img> loads without
# a bearer token. The chore editor seeds its dialog straight from that state
# and posts the same value back on save, so the validator saw
# `<our url>?authSig=<jwt>` and rejected every edit of a chore with an image.

SIGNED = GOOD + (
    "?authSig=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiIxNzJlZDRjYTNmNTA0OGQ4YmNiNGFiNzcyMTE4NTIyNSJ9"
    ".Sd5AmNlzLX_46dqdzfv2iCIdCUnA-srciXw71yUtU0E"
)


def test_validator_accepts_the_signed_url_the_panel_was_handed():
    from custom_components.taskmate.websocket import _image_url_or_blank

    assert _image_url_or_blank(SIGNED) == GOOD


def test_validator_strips_the_signature_before_storing():
    # A signature expires in 24h and is per-user; persisting one would rot the
    # stored chore and break image deletion, which compares URLs by equality.
    from custom_components.taskmate.websocket import _image_url_or_blank

    assert "authSig" not in _image_url_or_blank(SIGNED)


def test_validator_still_rejects_a_foreign_url_with_a_query():
    from custom_components.taskmate.websocket import _image_url_or_blank

    with pytest.raises(vol.Invalid):
        _image_url_or_blank("https://evil.example/x.jpg?authSig=abc")
