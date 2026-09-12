# -*- coding: utf-8 -*-
"""Non-player visual authority. Reads only committed Chatelaine equipment."""
import copy
import time
import mod.server.extraServerApi as serverApi
from chatelaine_aggregator.registry import serialized_size, MAX_VISUAL_STATE_BYTES, STRING_TYPES, _is_int
from chatelaine_aggregator.equipment import _item_name, _item_count

REGISTRY_EVENT = "ChatelaineEntityVisualRegistryClientEvent"
STATE_EVENT = "ChatelaineEntityVisualStateClientEvent"
REQUEST_EVENT = "ChatelaineEntityVisualSyncRequestServerEvent"
MAX_TARGETS = 64
MAX_SUBSCRIPTIONS = 512
LEASE_SECONDS = 90.0


class EntityVisualService(object):
    def __init__(self, system, registry, equipment):
        self.system = system
        self.registry = registry
        self.equipment = equipment
        self.factory = serverApi.GetEngineCompFactory()
        self.game = self.factory.CreateGame(serverApi.GetLevelId())
        self.epoch = "%d:%s" % (int(time.time() * 1000000), id(self))
        self.entries = {}
        self.enabled = {}
        self.viewers = {}
        self.request_limits = {}
        self.serial = 0
        self.destroyed = False
        self.expiry_timer = None

    def _dimension(self, entity_id):
        comp = self.factory.CreateDimension(entity_id)
        return comp.GetEntityDimensionId() if comp else None

    def _can_observe(self, player_id, entity_id, dimension):
        if self._dimension(player_id) != dimension:
            return False
        player_pos = self.factory.CreatePos(player_id).GetFootPos()
        entity_pos = self.factory.CreatePos(entity_id).GetFootPos()
        return bool(player_pos and entity_pos and sum(
            (player_pos[i] - entity_pos[i]) ** 2 for i in range(3)) <= 256 ** 2)

    def change(self, entity_id, reason):
        if self.destroyed:
            return False
        if reason in ("adopting", "removed", "isolated"):
            self.remove(entity_id)
            return False
        return self.refresh(entity_id)

    def refresh(self, entity_id):
        if self.destroyed:
            return False
        raw = self.equipment.data.get(entity_id)
        if (raw is None or entity_id in self.equipment.pending_rollback
                or not self.registry.is_ready() or not self.equipment.eligible(entity_id)):
            self.remove(entity_id)
            return False
        identifier = self.factory.CreateEngineType(entity_id).GetEngineTypeStr()
        dimension = self._dimension(entity_id)
        if not identifier or dimension is None:
            self.remove(entity_id)
            return False
        token = self.equipment.tokens.get(entity_id)
        entry = self.entries.get(entity_id)
        if entry is None or entry["token"] is not token:
            self.remove(entity_id)
            self.serial += 1
            entry = {"token": token, "generation": self.serial, "revision": 0, "core": None}
            self.entries[entity_id] = entry
        overrides = self.enabled.get(entity_id, {})
        for slot in list(overrides):
            if slot not in raw["slots"]:
                del overrides[slot]
        slots = {}
        for slot_id, item in raw["slots"].items():
            item_id = _item_name(item)
            visual_id = self.registry.entity_visual_for_item(item_id)
            model = self.registry.entity_visual_model(visual_id, identifier)
            accepted = bool(item and self.system.CanEquipCurio(slot_id, item)
                and _item_count(item) <= self.system.GetCurioSlotCapacity(slot_id, item))
            display = overrides.get(slot_id, True)
            slots[slot_id] = {
                "itemId": item_id, "visualId": visual_id if model else None,
                "visible": bool(accepted and model and slot_id in model["slotIds"] and display),
                "slotDisplayEnabled": display,
                "modelKey": model["modelKey"] if model else None,
            }
        core = {"entityIdentifier": identifier, "dimensionId": dimension,
                "registryRevision": self.registry.get_revision(), "slots": slots}
        changed = core != entry["core"]
        entry["equipmentRevision"] = raw["revision"]
        if not changed:
            return True
        entry["core"] = core
        entry["revision"] += 1
        payload = self._payload(entity_id, entry)
        size = serialized_size(payload)
        if size is None or size > MAX_VISUAL_STATE_BYTES:
            self.remove(entity_id)
            print("[Chatelaine][EntityVisual] state_budget_exceeded %s" % entity_id)
            return False
        for player_id, viewer in list(self.viewers.items()):
            sub = viewer["targets"].get(entity_id)
            if sub and sub["expires"] > time.time() and self._can_observe(player_id, entity_id, dimension):
                self._send_state(player_id, viewer, entity_id, entry)
            elif any(state["visualId"] for state in slots.values()) and self._can_observe(player_id, entity_id, dimension):
                self._send_candidates(player_id, viewer, [entity_id])
        return True

    def _payload(self, entity_id, entry):
        payload = dict(entry["core"])
        payload.update(entityId=entity_id, coreEpoch=self.epoch,
            entityGeneration=entry["generation"], visualRevision=entry["revision"],
            equipmentRevision=entry["equipmentRevision"], active=True)
        return payload

    def _send_state(self, player_id, viewer, entity_id, entry):
        payload = self._payload(entity_id, entry)
        payload["clientSession"] = viewer["session"]
        payload["clientToken"] = viewer["targets"][entity_id]["token"]
        return self.system.NotifyToClient(player_id, STATE_EVENT, payload)

    def _send_candidates(self, player_id, viewer, entity_ids):
        for offset in range(0, len(entity_ids), MAX_TARGETS):
            self.system.NotifyToClient(player_id, STATE_EVENT, {
                "kind": "candidates", "coreEpoch": self.epoch,
                "clientSession": viewer["session"],
                "entityIds": entity_ids[offset:offset + MAX_TARGETS]})

    def get_slot(self, entity_id, slot_id):
        entry = self.entries.get(entity_id)
        if self.destroyed or entry is None or slot_id not in entry["core"]["slots"]:
            return {}
        result = copy.deepcopy(entry["core"]["slots"][slot_id])
        result.update(entityId=entity_id, slotId=slot_id, coreEpoch=self.epoch,
            entityGeneration=entry["generation"], visualRevision=entry["revision"],
            equipmentRevision=entry["equipmentRevision"])
        return result

    def set_enabled(self, entity_id, slot_id, value):
        if (self.destroyed or (value is not None and not isinstance(value, bool))
                or not self.equipment.eligible(entity_id)):
            return False
        raw = self.equipment.data.get(entity_id)
        if raw is None or entity_id in self.equipment.pending_rollback or slot_id not in raw["slots"]:
            return False
        overrides = self.enabled.setdefault(entity_id, {})
        if value is None:
            overrides.pop(slot_id, None)
        else:
            overrides[slot_id] = value
        return self.refresh(entity_id)

    def request(self, args):
        if self.destroyed or not self.registry.is_ready() or not isinstance(args, dict):
            return False
        player_id = args.get("__id__")
        if player_id not in (serverApi.GetPlayerList() or ()):
            return False
        size = serialized_size(args)
        if size is None or size > 16384:
            return False
        now = time.time()
        allowance, last = self.request_limits.get(player_id, (16.0, now))
        allowance = min(16.0, allowance + max(0.0, now - last) * 8.0)
        self.request_limits[player_id] = (allowance, now)
        if allowance < 1:
            return False
        self.request_limits[player_id] = (allowance - 1, now)
        session = args.get("clientSession")
        if not isinstance(session, STRING_TYPES) or not session or len(session) > 96:
            return False
        op = args.get("operation")
        viewer = self.viewers.get(player_id)
        if op == "hello":
            if not _is_int(args.get("helloToken")) or args["helloToken"] < 1:
                return False
            if viewer is None or viewer["session"] != session:
                viewer = {"session": session, "targets": {}, "expires": now + LEASE_SECONDS}
                self.viewers[player_id] = viewer
            viewer["expires"] = now + LEASE_SECONDS
            payload = self.registry.entity_visual_registry()
            payload.update(coreEpoch=self.epoch, clientSession=session, helloToken=args["helloToken"])
            self.system.NotifyToClient(player_id, REGISTRY_EVENT, payload)
            candidates = [entity_id for entity_id, entry in sorted(self.entries.items())
                          if any(v["visualId"] for v in entry["core"]["slots"].values())
                          and self._can_observe(player_id, entity_id, entry["core"]["dimensionId"])]
            self._send_candidates(player_id, viewer, candidates[:MAX_SUBSCRIPTIONS])
            self._schedule_expiry()
            return True
        targets = args.get("targets", [])
        if viewer is None and op in ("subscribe", "renew"):
            self.system.NotifyToClient(player_id, STATE_EVENT, {
                "kind": "resync", "clientSession": session})
            return False
        if (viewer is None or viewer["session"] != session
                or op not in ("subscribe", "unsubscribe", "renew")
                or not isinstance(targets, list) or len(targets) > MAX_TARGETS):
            return False
        if any(not isinstance(t, dict) or not isinstance(t.get("entityId"), STRING_TYPES)
               or not _is_int(t.get("clientToken")) or t["clientToken"] < 1 for t in targets):
            return False
        viewer["expires"] = now + LEASE_SECONDS
        for target in targets:
            entity_id, client_token = target["entityId"], target["clientToken"]
            if op == "unsubscribe":
                old = viewer["targets"].get(entity_id)
                if old and old["token"] == client_token:
                    viewer["targets"].pop(entity_id, None)
                continue
            entry = self.entries.get(entity_id)
            if entry is None:
                if op == "subscribe":
                    self.system.NotifyToClient(player_id, STATE_EVENT, {
                        "coreEpoch": self.epoch, "clientSession": session,
                        "entityId": entity_id, "clientToken": client_token,
                        "entityGeneration": 0, "visualRevision": 0,
                        "active": False, "slots": {}})
                continue
            if (not self._can_observe(player_id, entity_id, entry["core"]["dimensionId"])
                    or not self.equipment.eligible(entity_id)):
                continue
            if entity_id not in viewer["targets"] and len(viewer["targets"]) >= MAX_SUBSCRIPTIONS:
                continue
            old = viewer["targets"].get(entity_id)
            if old and client_token < old["token"]:
                continue
            viewer["targets"][entity_id] = {"token": client_token, "expires": now + LEASE_SECONDS}
            if op == "subscribe" or not old:
                self._send_state(player_id, viewer, entity_id, entry)
        self._schedule_expiry()
        return True

    def remove(self, entity_id):
        entry = self.entries.pop(entity_id, None)
        self.enabled.pop(entity_id, None)
        for player_id, viewer in list(self.viewers.items()):
            sub = viewer["targets"].pop(entity_id, None)
            if entry and sub:
                self.system.NotifyToClient(player_id, STATE_EVENT, {
                    "coreEpoch": self.epoch, "clientSession": viewer["session"],
                    "entityId": entity_id, "clientToken": sub["token"],
                    "entityGeneration": entry["generation"], "visualRevision": entry["revision"] + 1,
                    "registryRevision": self.registry.get_revision(),
                    "dimensionId": entry["core"]["dimensionId"], "active": False, "slots": {}})

    def clear_player(self, player_id):
        self.viewers.pop(player_id, None)
        self.request_limits.pop(player_id, None)

    def _schedule_expiry(self):
        if not self.destroyed and self.viewers and self.expiry_timer is None:
            self.expiry_timer = self.game.AddTimer(30.0, self._expire)

    def _expire(self):
        self.expiry_timer = None
        if self.destroyed:
            return
        now = time.time()
        online = set(serverApi.GetPlayerList() or ())
        for player_id, viewer in list(self.viewers.items()):
            if player_id not in online or viewer["expires"] <= now:
                self.clear_player(player_id)
                continue
            for entity_id, sub in list(viewer["targets"].items()):
                entry = self.entries.get(entity_id)
                if (sub["expires"] <= now or entry is None
                        or self._dimension(player_id) != entry["core"]["dimensionId"]):
                    viewer["targets"].pop(entity_id, None)
        self._schedule_expiry()

    def destroy(self):
        if self.destroyed:
            return
        self.destroyed = True
        if self.expiry_timer is not None:
            self.game.CancelTimer(self.expiry_timer)
            self.expiry_timer = None
        self.entries.clear()
        self.enabled.clear()
        self.viewers.clear()
        self.request_limits.clear()
