# -*- coding: utf-8 -*-
"""Instance equipment for non-player living entities; trusted server API only.

The core owns this record. Providers own item acquisition/delivery and gameplay.
No player inventory or cursor is used here. Internal visual notifications follow commits.
"""
import copy
import mod.server.extraServerApi as serverApi
from chatelaine_aggregator.equipment import (
    _is_int, _item_name, _item_count, _item_lock_mode, _to_engine_value,
)

DATA_KEY = "chatelaine:entity_slots_v1"
CHANGED_EVENT = "ChatelaineEntitySlotsChangedServerEvent"


class EntityEquipmentService(object):
    def __init__(self, system, registry, on_change=None):
        self.system = system
        self.registry = registry
        self.factory = serverApi.GetEngineCompFactory()
        self.data = {}
        self.tokens = {}
        self.busy = set()
        self.pending_rollback = {}
        self.destroyed = False
        self.on_change = on_change

    def eligible(self, entity_id):
        if self.destroyed or not entity_id or entity_id in (serverApi.GetPlayerList() or ()):
            return False
        game = self.factory.CreateGame(serverApi.GetLevelId())
        if not game or not game.IsEntityAlive(entity_id):
            return False
        comp = self.factory.CreateEngineType(entity_id)
        kind = comp.GetEngineType() if comp else None
        return bool(_is_int(kind) and kind & serverApi.GetMinecraftEnum().EntityType.Mob)

    @staticmethod
    def valid_record(raw):
        if not isinstance(raw, dict) or set(raw) != set(("schemaVersion", "revision", "slots")):
            return False
        if type(raw["schemaVersion"]).__name__ not in ("int", "long") or raw["schemaVersion"] != 1:
            return False
        if not _is_int(raw["revision"]) or raw["revision"] < 0 or not isinstance(raw["slots"], dict):
            return False
        for slot_id, item in raw["slots"].items():
            if type(slot_id).__name__ not in ("str", "unicode") or not slot_id or not isinstance(item, dict):
                return False
            if item and (not _item_name(item) or not _is_int(item.get("count")) or item["count"] < 1):
                return False
        return True

    def adopt(self, entity_id, slot_ids=None):
        """Add/load boundary restores only; explicit slot_ids permits first creation."""
        if not self.eligible(entity_id) or not self.registry.is_ready() or entity_id in self.busy:
            return False
        if entity_id in self.pending_rollback:
            if not self._restore(entity_id, self.pending_rollback[entity_id]):
                return False
            self.pending_rollback.pop(entity_id, None)
        token = object()
        self.tokens[entity_id] = token
        self.data.pop(entity_id, None)
        self._visual_changed(entity_id, "adopting")
        self.busy.add(entity_id)
        try:
            extra = self.factory.CreateExtraData(entity_id)
            if extra is None:
                return False
            whole = extra.GetWholeExtraData()
            if whole is None:
                whole = {}
            if not isinstance(whole, dict):
                return False
            if DATA_KEY in whole:
                raw = copy.deepcopy(whole[DATA_KEY])
                if not self.valid_record(raw):
                    return False
            else:
                if slot_ids is None or not self._valid_slots(slot_ids):
                    return False
                raw = {"schemaVersion": 1, "revision": 0,
                       "slots": dict((slot, {}) for slot in slot_ids)}
                if not self._save(entity_id, raw, None, token):
                    return False
            if self.destroyed or self.tokens.get(entity_id) is not token:
                return False
            self.data[entity_id] = raw
        except Exception as error:
            print("[Chatelaine][Entity] adopt_failed %s: %s" % (entity_id, error))
            return False
        finally:
            self.busy.discard(entity_id)
        self._notify(entity_id, raw, "adopt")
        return True

    def _valid_slots(self, slot_ids):
        return (isinstance(slot_ids, (list, tuple))
                and all(type(slot).__name__ in ("str", "unicode") for slot in slot_ids)
                and len(set(slot_ids)) == len(slot_ids)
                and set(slot_ids).issubset(set(self.registry.get_slot_ids())))

    def snapshot(self, entity_id):
        if self.destroyed or not self.registry.is_ready() or entity_id in self.pending_rollback:
            return {}
        return copy.deepcopy(self.data.get(entity_id, {}))

    def item(self, entity_id, slot_id):
        item = self.snapshot(entity_id).get("slots", {}).get(slot_id, {})
        # Removed providers and newly incompatible declarations keep their raw
        # property for recovery, but cannot contribute an equipped capability.
        if item and self.system.CanEquipCurio(slot_id, item) and _item_count(item) <= self.system.GetCurioSlotCapacity(slot_id, item):
            return item
        return {}

    def configure(self, entity_id, slot_ids, expected_revision):
        raw = self.snapshot(entity_id)
        if not self._valid_slots(slot_ids):
            return self._result(False, "invalid_slots")
        if any(item for slot, item in raw.get("slots", {}).items() if slot not in slot_ids):
            return self._result(False, "occupied_slot")
        candidate = copy.deepcopy(raw)
        candidate["slots"] = dict((slot, raw.get("slots", {}).get(slot, {})) for slot in slot_ids)
        return self._commit(entity_id, raw, candidate, expected_revision, "configure")

    def exchange(self, entity_id, slot_id, item, expected_revision, data_only=False):
        raw = self.snapshot(entity_id)
        if slot_id not in raw.get("slots", {}):
            return self._result(False, "unknown_slot")
        if not isinstance(item, dict):
            return self._result(False, "invalid_item")
        current = raw["slots"][slot_id]
        if item and (not _is_int(item.get("count")) or item["count"] < 1
                     or not self.system.CanEquipCurio(slot_id, item)
                     or item["count"] > self.system.GetCurioSlotCapacity(slot_id, item)):
            return self._result(False, "item_rejected")
        if data_only:
            if not current or not item or _item_name(current) != _item_name(item) or _item_count(current) != _item_count(item):
                return self._result(False, "identity_changed")
        elif current != item and (_item_lock_mode(current) or _item_lock_mode(item)):
            return self._result(False, "item_locked")
        candidate = copy.deepcopy(raw)
        candidate["slots"][slot_id] = copy.deepcopy(item)
        result = self._commit(entity_id, raw, candidate, expected_revision, "item_data" if data_only else "exchange")
        if result["success"]:
            result["previousItem"] = copy.deepcopy(current)
        return result

    @staticmethod
    def _result(success, reason, revision=None):
        return {"success": success, "reason": reason, "revision": revision}

    def _commit(self, entity_id, raw, candidate, expected_revision, reason):
        if not self.eligible(entity_id) or entity_id in self.busy or not raw:
            return self._result(False, "not_ready")
        if not _is_int(expected_revision) or expected_revision != raw["revision"]:
            return self._result(False, "revision_conflict", raw["revision"])
        if candidate == raw:
            return self._result(True, "unchanged", raw["revision"])
        candidate["revision"] += 1
        token = self.tokens.get(entity_id)
        self.busy.add(entity_id)
        try:
            if not self._save(entity_id, candidate, raw, token):
                return self._result(False, "save_failed", raw["revision"])
            self.data[entity_id] = candidate
        finally:
            self.busy.discard(entity_id)
        self._notify(entity_id, candidate, reason)
        return self._result(True, "ok", candidate["revision"])

    def _write(self, entity_id, raw):
        extra = self.factory.CreateExtraData(entity_id)
        if extra is None:
            return False
        if raw is None:
            staged = extra.CleanExtraData(DATA_KEY)
        else:
            staged = extra.SetExtraData(DATA_KEY, _to_engine_value(raw), False)
        return bool(staged and extra.SaveExtraData())

    def _restore(self, entity_id, raw):
        for _attempt in range(2):
            try:
                if self._write(entity_id, raw):
                    return True
            except Exception:
                pass
        return False

    def _save(self, entity_id, candidate, old, token):
        try:
            if self._write(entity_id, candidate) and not self.destroyed and self.tokens.get(entity_id) is token:
                return True
        except Exception:
            pass
        if not self._restore(entity_id, old):
            self.pending_rollback[entity_id] = copy.deepcopy(old)
            self.data.pop(entity_id, None)
            self._visual_changed(entity_id, "isolated")
            print("[Chatelaine][Entity] rollback_pending %s" % entity_id)
        return False

    def _notify(self, entity_id, raw, reason):
        self._visual_changed(entity_id, reason)
        self.system.BroadcastChatelaineEvent(CHANGED_EVENT, {
            "entityId": entity_id, "revision": raw["revision"],
            "slots": copy.deepcopy(raw["slots"]), "reason": reason,
        })

    def remove(self, entity_id):
        self.data.pop(entity_id, None)
        self.tokens.pop(entity_id, None)
        self._visual_changed(entity_id, "removed")

    def _visual_changed(self, entity_id, reason):
        if self.on_change is not None:
            self.on_change(entity_id, reason)

    def destroy(self):
        self.destroyed = True
        self.data.clear()
        self.tokens.clear()
