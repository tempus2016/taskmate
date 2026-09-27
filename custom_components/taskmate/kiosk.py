"""Kiosk mode (#930): per-child PINs and the WebSocket API for the kiosk card.

A shared wall tablet runs one Home Assistant account for the whole family, so
the kiosk card lets each child pick their own face and, optionally, type a
4-digit PIN before seeing their chores. What lives here:

* PIN storage. A parent sets the PIN in the admin panel; only a salted PBKDF2
  hash is kept (``storage.kiosk_pins``), never the digits. The hash is never
  published in a sensor attribute or in ``get_state`` — the panel only learns
  *which* children have a PIN.
* PIN checks. ``taskmate/kiosk/verify_pin`` compares server-side, behind a
  per-child rate limit (5 wrong tries lock that child's pad, for longer each
  time), so the card can't be used to brute-force a PIN.
* ``taskmate/kiosk/status`` — what the card needs that isn't in the sensors:
  which children have a PIN, whether this tablet's HA user may act for each
  child, and each child's outstanding chores for today.

The PIN is a hand-over gate between siblings on one tablet, not an
authorisation boundary: completions still go through ``complete_chore`` and
its linked-child rule (``authz.async_context_allows_child``). When that rule
says the tablet's user may not act for a child — the child is linked to a
different account, or "Require a linked account per child" is on and the
tablet user isn't a parent — ``can_act`` is False and the card explains why
instead of offering buttons that would be refused.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
from types import SimpleNamespace
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from . import authz
from .const import DOMAIN
from .websocket import _admin_only, _get_coordinator

_LOGGER = logging.getLogger(__name__)

WS_KIOSK_STATUS: Final = "taskmate/kiosk/status"
WS_KIOSK_VERIFY_PIN: Final = "taskmate/kiosk/verify_pin"
WS_KIOSK_SET_PIN: Final = "taskmate/kiosk/set_pin"

PIN_PATTERN: Final = re.compile(r"[0-9]{4}")

_HASH_NAME: Final = "sha256"
_ITERATIONS: Final = 120_000
_SCHEME: Final = "pbkdf2_sha256"

# Rate limit: this many wrong tries in a row lock the child's pad. The first
# lock lasts BASE seconds and each further one doubles, up to MAX, so a 4-digit
# PIN takes days rather than minutes to walk. A right PIN clears it all.
MAX_FAILURES: Final = 5
BASE_LOCK_SECONDS: Final = 30
MAX_LOCK_SECONDS: Final = 900

_LIMITER_KEY: Final = "kiosk_pin_limiter"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def is_valid_pin(pin: Any) -> bool:
    """True for exactly four ASCII digits."""
    return isinstance(pin, str) and bool(PIN_PATTERN.fullmatch(pin))


def hash_pin(pin: str, *, salt: bytes | None = None, iterations: int = _ITERATIONS) -> str:
    """Return ``pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>`` for ``pin``.

    CPU-bound (~0.1 s); call it through ``hass.async_add_executor_job``.
    """
    if not is_valid_pin(pin):
        raise ValueError("A kiosk PIN must be exactly 4 digits")
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(_HASH_NAME, pin.encode(), salt, iterations)
    return f"{_SCHEME}${iterations}${salt.hex()}${digest.hex()}"


def verify_pin_hash(pin: Any, stored: Any) -> bool:
    """True if ``pin`` matches the stored hash. Anything malformed is a miss."""
    if not is_valid_pin(pin) or not isinstance(stored, str):
        return False
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
        if scheme != _SCHEME:
            return False
        rounds = int(iterations)
        if not 1 <= rounds <= 10_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(_HASH_NAME, pin.encode(), salt, rounds)
    return hmac.compare_digest(actual, expected)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class PinRateLimiter:
    """Per-child wrong-PIN counter, kept in memory (a restart clears it).

    An attempt is counted *before* the hash is checked, so a burst of
    concurrent guesses can't all slip in while the first is still hashing; a
    right PIN then wipes the child's record.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._state: dict[str, dict[str, float]] = {}

    def locked_for(self, key: str) -> int:
        """Whole seconds until ``key`` may try again (0 when not locked)."""
        entry = self._state.get(key)
        if not entry:
            return 0
        remaining = entry.get("lock_until", 0.0) - self._clock()
        return max(0, int(remaining + 0.999)) if remaining > 0 else 0

    def begin_attempt(self, key: str) -> int:
        """Register a try. Returns the lock remaining if refused, else 0."""
        locked = self.locked_for(key)
        if locked:
            return locked
        entry = self._state.setdefault(key, {"failures": 0, "lockouts": 0, "lock_until": 0.0})
        entry["failures"] += 1
        if entry["failures"] >= MAX_FAILURES:
            entry["lockouts"] += 1
            seconds = min(BASE_LOCK_SECONDS * 2 ** (int(entry["lockouts"]) - 1), MAX_LOCK_SECONDS)
            entry["lock_until"] = self._clock() + seconds
            entry["failures"] = 0
        return 0

    def attempts_left(self, key: str) -> int:
        entry = self._state.get(key)
        return MAX_FAILURES - int(entry["failures"]) if entry else MAX_FAILURES

    def reset(self, key: str) -> None:
        self._state.pop(key, None)


def _limiter(hass: HomeAssistant) -> PinRateLimiter:
    domain = hass.data.setdefault(DOMAIN, {})
    limiter = domain.get(_LIMITER_KEY)
    if not isinstance(limiter, PinRateLimiter):
        limiter = domain[_LIMITER_KEY] = PinRateLimiter()
    return limiter


# ---------------------------------------------------------------------------
# WebSocket commands
# ---------------------------------------------------------------------------


def _signed_in(handler):
    """For the kiosk card's own commands: any signed-in user, not just admins.

    The tablet usually runs a non-admin account, so these can't sit behind
    ``_admin_only``. Nothing they return is more than the sensors already show
    that user, apart from the yes/no answers about PINs and permissions.
    """

    async def wrapper(hass, connection, msg):
        coordinator = _get_coordinator(hass)
        if not coordinator:
            connection.send_error(msg["id"], "no_coordinator", "TaskMate not initialised")
            return
        try:
            await handler(hass, connection, msg, coordinator)
        except ValueError as err:
            connection.send_error(msg["id"], "invalid", str(err))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("WS handler %s failed", msg.get("type"))
            connection.send_error(msg["id"], "handler_failed", str(err))

    wrapper.__name__ = handler.__name__
    wrapper.__doc__ = handler.__doc__
    return wrapper


@websocket_api.websocket_command({vol.Required("type"): WS_KIOSK_STATUS})
@websocket_api.async_response
@_signed_in
async def ws_kiosk_status(hass, connection, msg, coordinator):
    """Per child: PIN set?, may this user act for them?, today's outstanding chores."""
    context = SimpleNamespace(user_id=getattr(connection.user, "id", "") or "")
    pinned = set(coordinator.storage.get_kiosk_pin_child_ids())
    children = []
    for child in coordinator.storage.get_children():
        children.append(
            {
                "id": child.id,
                "has_pin": child.id in pinned,
                "can_act": await authz.async_context_allows_child(hass, coordinator, context, child.id),
                "due": [chore.id for chore in coordinator.get_due_chores_for_child(child.id)],
            }
        )
    connection.send_result(msg["id"], {"children": children})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_KIOSK_VERIFY_PIN,
        vol.Required("child_id"): str,
        vol.Required("pin"): vol.All(str, vol.Length(max=16)),
    }
)
@websocket_api.async_response
@_signed_in
async def ws_kiosk_verify_pin(hass, connection, msg, coordinator):
    """Check a child's PIN. Returns ok, plus locked_for / attempts_left on a miss."""
    child_id = msg["child_id"]
    if not coordinator.storage.get_child(child_id):
        connection.send_error(msg["id"], "not_found", f"Child {child_id} not found")
        return
    stored = coordinator.storage.get_kiosk_pin_hash(child_id)
    if not stored:
        # No PIN set: nothing to guess, so the pad isn't shown at all.
        connection.send_result(msg["id"], {"ok": True})
        return
    limiter = _limiter(hass)
    locked = limiter.begin_attempt(child_id)
    if locked:
        connection.send_result(msg["id"], {"ok": False, "locked_for": locked, "attempts_left": 0})
        return
    ok = await hass.async_add_executor_job(verify_pin_hash, msg["pin"], stored)
    if ok:
        limiter.reset(child_id)
        connection.send_result(msg["id"], {"ok": True})
        return
    locked = limiter.locked_for(child_id)
    connection.send_result(
        msg["id"],
        {"ok": False, "locked_for": locked, "attempts_left": 0 if locked else limiter.attempts_left(child_id)},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_KIOSK_SET_PIN,
        vol.Required("child_id"): str,
        # "" removes the PIN.
        vol.Required("pin"): vol.All(str, vol.Length(max=16)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_kiosk_set_pin(hass, connection, msg, coordinator):
    """Set (4 digits) or clear ("") a child's kiosk PIN. Admin only, like the child dialog."""
    child_id = msg["child_id"]
    if not coordinator.storage.get_child(child_id):
        connection.send_error(msg["id"], "not_found", f"Child {child_id} not found")
        return
    pin = msg["pin"]
    if pin and not is_valid_pin(pin):
        connection.send_error(msg["id"], "invalid_format", "A kiosk PIN must be exactly 4 digits")
        return
    stored = await hass.async_add_executor_job(hash_pin, pin) if pin else ""
    coordinator.storage.set_kiosk_pin_hash(child_id, stored)
    await coordinator.storage.async_save()
    # A new PIN starts with a clean slate.
    _limiter(hass).reset(child_id)
    connection.send_result(msg["id"], {"id": child_id, "has_pin": bool(stored)})


KIOSK_COMMANDS: Final = (ws_kiosk_status, ws_kiosk_verify_pin, ws_kiosk_set_pin)
