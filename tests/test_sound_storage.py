"""Tests for the pure custom-sound storage helpers (custom_components.taskmate.sounds)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.taskmate import sounds
from custom_components.taskmate.const import COMPLETION_SOUND_OPTIONS, is_valid_completion_sound


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _hass(tmp_path: Path):
    hass = MagicMock()
    hass.config.path = MagicMock(side_effect=lambda *p: str(Path(tmp_path, *p)))

    async def _exec(func, *args):
        return func(*args)

    hass.async_add_executor_job = _exec
    return hass


MP3_ID3 = b"ID3\x03\x00" + b"\x00" * 32
MP3_BARE = b"\xff\xfb\x90\x00" + b"\x00" * 32
OGG = b"OggS" + b"\x00" * 32
WAV = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32
M4A = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 32

NAME = "a" * 32 + ".mp3"


# ---------------------------------------------------------------------------
# Magic-byte sniffing
# ---------------------------------------------------------------------------


def test_detect_allowed_ext_accepts_supported_formats():
    assert sounds.detect_allowed_ext(MP3_ID3) == "mp3"
    assert sounds.detect_allowed_ext(MP3_BARE) == "mp3"
    assert sounds.detect_allowed_ext(OGG) == "ogg"
    assert sounds.detect_allowed_ext(WAV) == "wav"
    assert sounds.detect_allowed_ext(M4A) == "m4a"


def test_detect_allowed_ext_rejects_non_audio():
    assert sounds.detect_allowed_ext(b"not audio at all") is None
    assert sounds.detect_allowed_ext(b"") is None
    # A JPEG must not sneak through as audio just because it starts with 0xFF:
    # the MPEG frame sync needs the top 11 bits set, and 0xD8 does not qualify.
    assert sounds.detect_allowed_ext(b"\xff\xd8\xff" + b"\x00" * 32) is None


def test_wav_needs_the_wave_marker_not_just_riff():
    # RIFF alone is also WebP; only RIFF....WAVE is audio.
    assert sounds.detect_allowed_ext(b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 32) is None


def test_content_type_for_maps_each_extension():
    assert sounds.content_type_for("x.mp3") == "audio/mpeg"
    assert sounds.content_type_for("x.ogg") == "audio/ogg"
    assert sounds.content_type_for("x.wav") == "audio/wav"
    assert sounds.content_type_for("x.m4a") == "audio/mp4"
    assert sounds.content_type_for("x.unknown") == "audio/mpeg"


# ---------------------------------------------------------------------------
# The custom: reference format
# ---------------------------------------------------------------------------


def test_is_custom_sound_accepts_well_formed():
    assert sounds.is_custom_sound(f"custom:{NAME}")
    assert sounds.is_custom_sound("custom:" + "0" * 32 + ".ogg")


def test_is_custom_sound_rejects_malformed_and_hostile():
    assert not sounds.is_custom_sound("")
    assert not sounds.is_custom_sound(None)
    assert not sounds.is_custom_sound("coin")
    assert not sounds.is_custom_sound("custom:")
    # Path traversal, wrong length, wrong charset, disallowed extension.
    assert not sounds.is_custom_sound("custom:../../secrets.yaml")
    assert not sounds.is_custom_sound("custom:" + "a" * 31 + ".mp3")
    assert not sounds.is_custom_sound("custom:" + "A" * 32 + ".mp3")
    assert not sounds.is_custom_sound("custom:" + "a" * 32 + ".exe")
    assert not sounds.is_custom_sound("custom:" + "a" * 32 + ".mp3/../x")


def test_sound_id_for_value_round_trips():
    assert sounds.sound_id_for_value(f"custom:{NAME}") == NAME
    assert sounds.sound_id_for_value("coin") is None


def test_sound_url_for_name():
    assert sounds.sound_url_for_name(NAME) == f"/api/taskmate/sound/{NAME}"


def test_sound_file_for_name_rejects_traversal(tmp_path):
    hass = _hass(tmp_path)
    assert sounds.sound_file_for_name(hass, NAME) is not None
    assert sounds.sound_file_for_name(hass, "../../secrets.yaml") is None
    assert sounds.sound_file_for_name(hass, "") is None


# ---------------------------------------------------------------------------
# Completion-sound validation (the websocket + service boundary)
# ---------------------------------------------------------------------------


def test_is_valid_completion_sound_accepts_every_builtin():
    for name in COMPLETION_SOUND_OPTIONS:
        assert is_valid_completion_sound(name), name


def test_is_valid_completion_sound_accepts_custom_reference():
    assert is_valid_completion_sound(f"custom:{NAME}")


def test_is_valid_completion_sound_rejects_junk():
    assert not is_valid_completion_sound("")
    assert not is_valid_completion_sound(None)
    assert not is_valid_completion_sound("definitely-not-a-sound")
    assert not is_valid_completion_sound("custom:../../etc/passwd")


# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------


def test_clean_sound_name_trims_and_collapses():
    assert sounds.clean_sound_name("  Burp   Noise  ") == "Burp Noise"


def test_clean_sound_name_truncates():
    assert len(sounds.clean_sound_name("x" * 200)) == sounds.MAX_NAME_LEN


def test_clean_sound_name_strips_control_characters():
    # A stray newline or ESC would scramble a line of panel/log output. What
    # survives is inert literal text — "[31m" without its ESC is just letters.
    cleaned = sounds.clean_sound_name("Good\n\x1b[31mBad")
    assert "\n" not in cleaned
    assert "\x1b" not in cleaned
    assert cleaned == "Good[31mBad"


def test_clean_sound_name_never_returns_empty():
    # An unnamed sound would be an unclickable blank row in the dropdown.
    assert sounds.clean_sound_name("") == "Sound"
    assert sounds.clean_sound_name(None) == "Sound"
    assert sounds.clean_sound_name("\x00\x01") == "Sound"


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def test_total_sounds_bytes_counts_only_matching_files(tmp_path):
    hass = _hass(tmp_path)
    directory = sounds.sounds_path(hass)
    directory.mkdir(parents=True)
    (directory / NAME).write_bytes(b"x" * 10)
    (directory / ("b" * 32 + ".ogg")).write_bytes(b"y" * 5)
    (directory / "notes.txt").write_bytes(b"z" * 1000)
    assert sounds.total_sounds_bytes(hass) == 15


def test_total_sounds_bytes_is_zero_without_the_directory(tmp_path):
    assert sounds.total_sounds_bytes(_hass(tmp_path)) == 0


def test_async_delete_sound_file_removes_it(tmp_path):
    hass = _hass(tmp_path)
    directory = sounds.sounds_path(hass)
    directory.mkdir(parents=True)
    target = directory / NAME
    target.write_bytes(b"x")
    run(sounds.async_delete_sound_file(hass, NAME))
    assert not target.exists()


def test_async_delete_sound_file_ignores_missing_and_invalid(tmp_path):
    hass = _hass(tmp_path)
    # Neither should raise.
    run(sounds.async_delete_sound_file(hass, NAME))
    run(sounds.async_delete_sound_file(hass, "../../secrets.yaml"))


def test_delete_cannot_escape_the_sounds_directory(tmp_path):
    hass = _hass(tmp_path)
    outside = tmp_path / "secrets.yaml"
    outside.write_bytes(b"token")
    run(sounds.async_delete_sound_file(hass, "../secrets.yaml"))
    assert outside.exists()


def test_sign_sound_url_passes_through_foreign_urls(tmp_path):
    hass = _hass(tmp_path)
    # No real HA here, so signing falls back to the original URL; what matters
    # is that a non-TaskMate URL is never handed to the signer at all.
    assert sounds.sign_sound_url(hass, "") == ""
    assert sounds.sign_sound_url(hass, "https://example.com/a.mp3") == "https://example.com/a.mp3"
