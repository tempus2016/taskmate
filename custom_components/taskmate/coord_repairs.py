"""Repairs (Settings → Repairs) for setups that can't work.

The admin panel's health page (#682) only helps a parent who goes looking.
These checks raise a Home Assistant repair issue instead, so a removed phone
app, a renamed person entity or a chore left assigned to nobody shows up in
the place HA users already check — and the issue clears itself once fixed.

Checks only run once Home Assistant has finished starting (and a couple of
minutes after TaskMate loaded): notify services and entities from other
integrations register late, and a repair that flashes up at every boot is
worse than none.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Seconds after TaskMate loads before the first check.
REPAIRS_GRACE_SECONDS = 120

# Issue codes (translation keys under "issues" in strings.json).
ISSUE_NOTIFY_SERVICE = "notify_service_missing"
ISSUE_CHILD_ENTITY = "child_entity_missing"
ISSUE_CHORE_ENTITY = "chore_entity_missing"
ISSUE_CHORE_NOBODY = "chore_assigned_to_nobody"
ISSUE_CHORE_DEPENDENCY = "chore_dependency_missing"
ISSUE_REWARD_NOBODY = "reward_assigned_to_nobody"
ISSUE_UNLOCK_NOT_ALLOWED = "reward_unlock_not_allowed"

_CHILD_ENTITY_FIELDS = ("availability_entity", "unavailability_entity", "presence_entity", "picture_entity")
_CHORE_ENTITY_FIELDS = ("visibility_entity", "weather_entity")


class RepairsMixin:
    """Keeps TaskMate's repair issues in step with its configuration."""

    _repairs_loaded_at: float | None = None
    _repairs_active: dict[str, dict[str, Any]] | None = None

    def _notify_service_exists(self, service: str) -> bool:
        domain, name = service.split(".", 1) if "." in service else ("notify", service)
        return bool(name) and self.hass.services.has_service(domain, name)

    def _entity_exists(self, entity_id: str) -> bool:
        return self.hass.states.get(entity_id) is not None

    def find_repair_issues(self) -> dict[str, dict[str, Any]]:
        """Every repair issue the current configuration deserves.

        ``{issue_id: {"key": translation key, "placeholders": {...},
        "severity": "warning" | "error"}}``. Issue ids are stable per object, so
        the same problem never stacks up as duplicates.
        """
        found: dict[str, dict[str, Any]] = {}

        def add(key: str, obj_id: str, placeholders: dict[str, str], severity: str = "warning") -> None:
            found[f"{key}_{obj_id}"] = {"key": key, "placeholders": placeholders, "severity": severity}

        storage = self.storage
        children = storage.get_children()
        child_ids = {c.id for c in children}

        # ── notify services ──────────────────────────────────────────────
        targets: list[tuple[str, str]] = []
        legacy = str(storage.get_setting("notify_service", "") or "").strip()
        if legacy:
            targets.append(("TaskMate", legacy))
        for parent in storage.get_parent_recipients():
            if getattr(parent, "enabled", True) and (parent.notify_service or "").strip():
                targets.append((parent.name or "Parent", parent.notify_service.strip()))
        for child in children:
            if (child.notify_service or "").strip():
                targets.append((child.name, child.notify_service.strip()))
        seen: set[str] = set()
        for who, service in targets:
            if service in seen or self._notify_service_exists(service):
                continue
            seen.add(service)
            add(ISSUE_NOTIFY_SERVICE, service.replace(".", "_"), {"service": service, "who": who})

        # ── child entities ───────────────────────────────────────────────
        for child in children:
            for field in _CHILD_ENTITY_FIELDS:
                entity_id = str(getattr(child, field, "") or "").strip()
                if entity_id and not self._entity_exists(entity_id):
                    add(ISSUE_CHILD_ENTITY, f"{child.id}_{field}", {"child": child.name, "entity": entity_id})

        # ── chores ───────────────────────────────────────────────────────
        chores = storage.get_chores()
        chore_ids = {c.id for c in chores}
        for chore in chores:
            if not getattr(chore, "enabled", True):
                continue
            assigned = list(getattr(chore, "assigned_to", []) or [])
            if assigned and not any(cid in child_ids for cid in assigned):
                add(ISSUE_CHORE_NOBODY, chore.id, {"chore": chore.name})
            for field in _CHORE_ENTITY_FIELDS:
                entity_id = str(getattr(chore, field, "") or "").strip()
                if entity_id and not self._entity_exists(entity_id):
                    add(ISSUE_CHORE_ENTITY, f"{chore.id}_{field}", {"chore": chore.name, "entity": entity_id})
            missing_deps = [d for d in (getattr(chore, "depends_on", []) or []) if d not in chore_ids]
            if missing_deps:
                add(ISSUE_CHORE_DEPENDENCY, chore.id, {"chore": chore.name}, "error")

        # ── rewards ──────────────────────────────────────────────────────
        for reward in storage.get_rewards():
            assigned = list(getattr(reward, "assigned_to", []) or [])
            if assigned and not any(cid in child_ids for cid in assigned):
                add(ISSUE_REWARD_NOBODY, reward.id, {"reward": reward.name})
            unlock = str(getattr(reward, "unlock_entity", "") or "")
            if unlock and not self.is_unlock_allowed(unlock):
                add(ISSUE_UNLOCK_NOT_ALLOWED, reward.id, {"reward": reward.name, "entity": unlock})

        return found

    def _repairs_ready(self) -> bool:
        hass = getattr(self, "hass", None)
        if hass is None or getattr(hass, "is_running", False) is not True:
            return False
        if self._repairs_loaded_at is None:
            self._repairs_loaded_at = time.monotonic()
        return time.monotonic() - self._repairs_loaded_at >= REPAIRS_GRACE_SECONDS

    def async_update_repairs(self) -> None:
        """Create the issues that are new and delete the ones now fixed."""
        if not self._repairs_ready():
            return
        try:
            found = self.find_repair_issues()
        except Exception:  # noqa: BLE001 — a broken check must never stop the refresh
            _LOGGER.exception("TaskMate repair checks failed")
            return
        if self._repairs_active is None:
            # First run since load: forget issues an earlier run raised and
            # this configuration no longer has.
            registry = ir.async_get(self.hass)
            self._repairs_active = {issue_id: {} for (domain, issue_id) in list(registry.issues) if domain == DOMAIN}
        for issue_id, issue in found.items():
            if self._repairs_active.get(issue_id) == issue:
                continue
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.ERROR if issue["severity"] == "error" else ir.IssueSeverity.WARNING,
                translation_key=issue["key"],
                translation_placeholders=issue["placeholders"],
            )
        for issue_id in set(self._repairs_active) - set(found):
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        self._repairs_active = found

    def clear_repairs(self) -> None:
        """Remove every TaskMate repair issue (integration unloaded)."""
        for issue_id in self._repairs_active or ():
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        self._repairs_active = None
