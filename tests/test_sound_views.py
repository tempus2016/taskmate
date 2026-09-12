"""The custom-sound HTTP views and frontend wiring (#856).

Like ``test_image_views.py``, the view assertions read the source text rather
than importing the module: aiohttp is not installed in the test environment and
conftest does not stub it. The behaviour that *can* run without aiohttp — the
storage helpers the views delegate to — is covered by ``test_sound_storage.py``.
"""

from __future__ import annotations

import pathlib
import re

from custom_components.taskmate import sounds

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
SRC = (ROOT / "http_sounds.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "frontend.py").read_text(encoding="utf-8")
ENGINE = (ROOT / "www" / "taskmate-sounds.js").read_text(encoding="utf-8")
CHILD_CARD = (ROOT / "www" / "taskmate-child-card.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP views
# ---------------------------------------------------------------------------


def test_views_are_bound_to_the_sound_prefix():
    assert "url = sounds.URL_PREFIX" in SRC
    assert 'url = sounds.URL_PREFIX + "/{filename}"' in SRC
    assert sounds.URL_PREFIX == "/api/taskmate/sound"


def test_upload_view_is_admin_gated():
    # Writing files to disk is admin-only, matching the chore-image upload.
    assert 'request.get("hass_user")' in SRC
    assert "is_admin" in SRC
    assert re.search(r"HTTPStatus\.FORBIDDEN", SRC)


def test_the_admin_check_precedes_any_body_read():
    # A 403 must not require streaming the upload first.
    assert SRC.index("is_admin") < SRC.index("await request.multipart()")


def test_upload_enforces_the_sound_caps():
    assert "sounds.MAX_UPLOAD_BYTES" in SRC
    assert "sounds.MAX_TOTAL_BYTES" in SRC


def test_upload_sniffs_magic_bytes_rather_than_trusting_the_client():
    assert "sounds.detect_allowed_ext" in SRC
    assert "content_type" not in SRC.split("def post")[1].split("def ")[0]


def test_upload_streams_with_a_running_size_check():
    # The declared content-length is attacker-controlled, so the cap has to be
    # re-checked as chunks arrive, not only up front.
    post_body = SRC.split("async def post")[1]
    assert post_body.count("MAX_UPLOAD_BYTES") >= 2


def test_serve_view_validates_the_filename_before_touching_disk():
    get_body = SRC.split("async def get")[1]
    assert get_body.index("FILENAME_RE.match") < get_body.index("sounds_path")


def test_serve_view_sets_the_sniffed_content_type():
    assert "sounds.content_type_for(filename)" in SRC


def test_views_register_once():
    assert "SOUND_HTTP_VIEWS_REGISTERED" in SRC
    assert "hass.data.setdefault(DOMAIN, {})[SOUND_HTTP_VIEWS_REGISTERED] = True" in SRC


# ---------------------------------------------------------------------------
# Frontend wiring
# ---------------------------------------------------------------------------


def test_sound_views_are_registered_with_the_frontend():
    assert "async_register_sound_views" in FRONTEND


def test_shared_engine_ships_as_both_a_card_resource_and_a_global_module():
    # Cards need it as a Lovelace resource; the admin panel is a panel_custom
    # page that never loads Lovelace resources, so it needs the global too.
    assert FRONTEND.count('"taskmate-sounds.js"') == 2


def test_engine_loads_before_the_preview_bridge():
    # The bridge calls window.__taskmate_sounds, which the engine defines.
    globals_block = FRONTEND.split("GLOBAL_MODULES")[1]
    assert globals_block.index('"taskmate-sounds.js"') < globals_block.index('"taskmate-config-sounds.js"')


# ---------------------------------------------------------------------------
# The shared engine
# ---------------------------------------------------------------------------


def test_engine_serves_bundled_files_from_the_integration_path():
    # Regression: these mp3s ship in custom_components/taskmate/www, which is
    # registered at /taskmate — NOT /local (config/www), where they have never
    # lived. That mismatch silently 404'd every fart sound.
    assert 'const FILE_BASE = "/taskmate"' in ENGINE
    assert "/local/taskmate" not in ENGINE
    assert "/local/taskmate" not in CHILD_CARD


def test_engine_knows_the_same_builtins_as_the_backend():
    listed = re.search(r"const BUILTIN = \[(.*?)\];", ENGINE, re.S).group(1)
    names = set(re.findall(r'"([^"]+)"', listed))
    from custom_components.taskmate.const import COMPLETION_SOUND_OPTIONS

    assert names == set(COMPLETION_SOUND_OPTIONS)


def test_engine_custom_pattern_matches_the_python_one():
    # Both sides gate on the same shape; a drift here means the panel offers a
    # sound the backend rejects, or vice versa.
    assert r"/^[0-9a-f]{32}\.(mp3|ogg|wav|m4a)$/" in ENGINE
    assert sounds.FILENAME_RE.pattern == r"^[0-9a-f]{32}\.(mp3|ogg|wav|m4a)$"


def test_child_card_delegates_to_the_shared_engine():
    # The card used to carry its own copy of every synthesised sound, which
    # drifted from the copy in taskmate-config-sounds.js.
    assert "window.__taskmate_sounds" in CHILD_CARD
    assert "_playCoinSound" not in CHILD_CARD
    assert "createOscillator" not in CHILD_CARD


def test_child_card_reads_custom_sounds_from_the_sensor():
    assert "_customSounds()" in CHILD_CARD
    assert "custom_sounds" in CHILD_CARD


def test_serve_view_sets_sniffing_protections():
    """User-supplied bytes served from the HA origin need nosniff, like photos."""
    assert '"X-Content-Type-Options": "nosniff"' in SRC
    assert '"Content-Disposition": "inline"' in SRC


def test_upload_bounds_the_form_part_scan():
    assert "parts_scanned > 16" in SRC
