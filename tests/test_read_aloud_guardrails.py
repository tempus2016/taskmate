"""read_aloud speaks through a household speaker, so its inputs are guarded.

A child may have *their own chore list* read out. Choosing the words, and
picking which speaker says them, is a parent action — otherwise any account
that can act as a child can make a speaker in the house say anything.
"""

from __future__ import annotations

import pathlib
import re

SRC = (pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "__init__.py").read_text(
    encoding="utf-8"
)


def _read_aloud_schema_block() -> str:
    # The constant also appears in the import block, so anchor on the
    # registration call instead.
    idx = SRC.index("hass.services.async_register(")
    while "SERVICE_READ_ALOUD" not in SRC[idx : idx + 400]:
        idx = SRC.index("hass.services.async_register(", idx + 1)
    return SRC[idx : idx + 1400]


def test_media_player_must_be_a_media_player_entity():
    block = _read_aloud_schema_block()
    assert 'cv.entity_domain("media_player")' in block


def test_tts_entity_must_be_a_tts_entity():
    block = _read_aloud_schema_block()
    assert 'cv.entity_domain("tts")' in block


def test_blank_target_is_still_allowed():
    """Blank means "use the configured default" — that must keep working."""
    block = _read_aloud_schema_block()
    assert 'vol.Any("", cv.entity_domain("media_player"))' in block


def test_message_length_is_bounded():
    block = _read_aloud_schema_block()
    assert "vol.Length(max=500)" in block


def test_custom_message_requires_a_parent():
    """The handler drops a caller-supplied message from a non-parent."""
    idx = SRC.index("async def handle_read_aloud")
    handler = SRC[idx : SRC.index("async def handle_spin_roulette")]
    assert "authz.async_context_is_parent" in handler
    # …and what it drops it to is the empty string, i.e. the generated text.
    assert re.search(r"message = \"\"", handler)
    # The context is forwarded so HA can apply the caller's entity policy.
    assert "context=call.context" in handler
