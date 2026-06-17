"""Coordinator ValueErrors surface as clean ServiceValidationErrors.

Coordinator methods raise ``ValueError`` for bad/rejected input (locked
avatar, insufficient gift balance, unknown id, ...). The service layer wraps
handlers in ``_safe`` so the frontend/WebSocket caller gets a clean failure
result with the message instead of an unhandled error + traceback. A handler
that already raises ``ServiceValidationError`` must pass through untouched.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

import custom_components.taskmate as tm


@pytest.mark.asyncio
async def test_value_error_becomes_service_validation_error():
    handler = AsyncMock(side_effect=ValueError("That avatar is not unlocked yet"))
    wrapped = tm._safe(handler)
    with pytest.raises(tm.ServiceValidationError, match="not unlocked yet"):
        await wrapped(object())


@pytest.mark.asyncio
async def test_clean_call_passes_through():
    handler = AsyncMock(return_value=None)
    call = object()
    await tm._safe(handler)(call)
    handler.assert_awaited_once_with(call)


@pytest.mark.asyncio
async def test_service_validation_error_not_double_wrapped():
    """A handler that already raises ServiceValidationError is left as-is."""
    original = tm.ServiceValidationError("already clean")
    handler = AsyncMock(side_effect=original)
    with pytest.raises(tm.ServiceValidationError) as excinfo:
        await tm._safe(handler)(object())
    assert excinfo.value is original
