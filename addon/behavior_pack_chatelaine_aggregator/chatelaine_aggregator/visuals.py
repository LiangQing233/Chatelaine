# -*- coding: utf-8 -*-
"""Server authority for generic Chatelaine equipped visual visibility."""

import copy

import mod.server.extraServerApi as serverApi

from chatelaine_aggregator.registry import (
    MAX_VISUAL_REGISTRY_BYTES,
    MAX_VISUAL_STATE_BYTES,
    serialized_size,
)


VISUAL_REGISTRY_CLIENT_EVENT = "ChatelaineVisualRegistryClientEvent"
VISUAL_STATE_CLIENT_EVENT = "ChatelaineVisualStateClientEvent"


def _item_name(item):
    if not isinstance(item, dict):
        return ""
    return item.get("newItemName") or item.get("itemName") or ""


def _item_present(item):
    name = _item_name(item)
    return bool(name and name != "minecraft:air")


class ChatelaineVisualService(object):

    def __init__(self, system, registry, equipment):
        self.system = system
        self.registry = registry
        self.equipment = equipment
        self.comp_factory = serverApi.GetEngineCompFactory()
        self.last_core_by_player = {}

    def sync_registry_to_client(self, client_player_id):
        if not client_player_id:
            return False
        payload = self.registry.player_visual_registry()
        size = serialized_size(payload)
        if size is None or size > MAX_VISUAL_REGISTRY_BYTES:
            print("[Chatelaine][Network] REJECT visual_registry bytes=%s" % size)
            return False
        return bool(self.system.NotifyToClient(
            client_player_id,
            VISUAL_REGISTRY_CLIENT_EVENT,
            payload,
        ))

    def sync_all_to_client(self, client_player_id):
        if not client_player_id:
            return False
        self.sync_registry_to_client(client_player_id)
        sent = False
        for subject_id in tuple(serverApi.GetPlayerList() or ()):
            payload = self.build_payload(subject_id, False)
            size = serialized_size(payload)
            if size is None or size > MAX_VISUAL_STATE_BYTES:
                print("[Chatelaine][Network] REJECT visual_state player=%s bytes=%s" % (
                    subject_id,
                    size,
                ))
                continue
            sent = bool(self.system.NotifyToClient(
                client_player_id,
                VISUAL_STATE_CLIENT_EVENT,
                payload,
            )) or sent
        return sent

    def broadcast_registry(self):
        sent = False
        for player_id in tuple(serverApi.GetPlayerList() or ()):
            sent = self.sync_registry_to_client(player_id) or sent
        return sent

    def refresh_player(self, player_id, native_overrides=None):
        if not player_id:
            return False
        previous_core = copy.deepcopy(
            self.last_core_by_player.get(player_id)
        )
        payload = self.build_payload(player_id, True, native_overrides)
        if previous_core == self.last_core_by_player.get(player_id):
            return False
        size = serialized_size(payload)
        if size is None or size > MAX_VISUAL_STATE_BYTES:
            print("[Chatelaine][Network] REJECT visual_state player=%s bytes=%s" % (
                player_id,
                size,
            ))
            return False
        sent = False
        for client_id in tuple(serverApi.GetPlayerList() or ()):
            sent = bool(self.system.NotifyToClient(
                client_id,
                VISUAL_STATE_CLIENT_EVENT,
                payload,
            )) or sent
        return sent

    def get_slot_state(self, player_id, slot_id):
        payload = self.build_payload(player_id, False)
        state = payload.get("slots", {}).get(slot_id)
        if state is None:
            state = {
                "itemId": "",
                "visualId": None,
                "visible": False,
                "slotDisplayEnabled": self.system._visualSlotEnabled.get(
                    player_id,
                    {},
                ).get(slot_id, True),
                "blockedByNativeSlots": [],
            }
        result = copy.deepcopy(state)
        result.update({
            "playerId": player_id,
            "slotId": slot_id,
            "visualRevision": payload.get("visualRevision", 0),
        })
        return result

    def build_payload(
        self,
        player_id,
        update_revision,
        native_overrides=None,
    ):
        snapshot = self.registry.get_snapshot()
        slots = self.equipment.get_slots(player_id)
        occupied = self._native_occupied(player_id, native_overrides)
        result = {}
        runtime = self.system._visualSlotEnabled.get(player_id, {})
        for slot_id in sorted(slots.keys()):
            item = slots.get(slot_id, {})
            item_id = _item_name(item)
            item_config = snapshot.get("itemsById", {}).get(item_id, {})
            visual_id = item_config.get("equippedVisualId")
            if not visual_id:
                continue
            visual = snapshot.get("visualsById", {}).get(visual_id, {})
            blocked = self._blocked_slots(
                visual.get("nativeSlotBlock"),
                occupied,
            )
            enabled = bool(runtime.get(slot_id, True))
            result[slot_id] = {
                "itemId": item_id,
                "visualId": visual_id,
                "visible": bool(item_id and enabled and not blocked),
                "slotDisplayEnabled": enabled,
                "blockedByNativeSlots": blocked,
            }
        core = {
            "registryRevision": snapshot.get("registryRevision", 0),
            "slots": result,
        }
        if update_revision:
            previous = self.last_core_by_player.get(player_id)
            if previous != core:
                self.system._visualRevision[player_id] = (
                    int(self.system._visualRevision.get(player_id, 0)) + 1
                )
            self.last_core_by_player[player_id] = copy.deepcopy(core)
        return {
            "playerId": player_id,
            "registryRevision": core["registryRevision"],
            "visualRevision": int(
                self.system._visualRevision.get(player_id, 0)
            ),
            "slots": copy.deepcopy(result),
        }

    def clear_player(self, player_id):
        self.last_core_by_player.pop(player_id, None)

    @staticmethod
    def _blocked_slots(block, occupied):
        if not isinstance(block, dict):
            return []
        slots = list(block.get("slots", ()))
        occupied_slots = [slot for slot in slots if occupied.get(slot, False)]
        if not slots:
            return []
        operator = block.get("operator")
        blocked = (
            len(occupied_slots) == len(slots)
            if operator == "and"
            else bool(occupied_slots)
        )
        return occupied_slots if blocked else []

    def _native_occupied(self, player_id, native_overrides=None):
        result = dict(
            (name, False)
            for name in (
                "mainhand",
                "offhand",
                "head",
                "chest",
                "legs",
                "feet",
            )
        )
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return result
        enums = serverApi.GetMinecraftEnum()
        positions = enums.ItemPosType
        try:
            selected = item_comp.GetSelectSlotId()
            main = item_comp.GetPlayerItem(
                positions.INVENTORY,
                int(selected),
                True,
            )
            result["mainhand"] = _item_present(main)
        except Exception:
            pass
        try:
            offhand = item_comp.GetEntityItem(positions.OFFHAND, 0, True)
            result["offhand"] = _item_present(offhand)
        except Exception:
            pass
        armor_slots = getattr(enums, "ArmorSlotType", None)
        for name, enum_name, fallback in (
            ("head", "HEAD", 0),
            ("chest", "BODY", 1),
            ("legs", "LEG", 2),
            ("feet", "FOOT", 3),
        ):
            try:
                index = getattr(armor_slots, enum_name, fallback)
                item = item_comp.GetEntityItem(
                    positions.ARMOR,
                    index,
                    True,
                )
                result[name] = _item_present(item)
            except Exception:
                pass
        if isinstance(native_overrides, dict):
            for name, item in native_overrides.items():
                if name in result:
                    result[name] = _item_present(item)
        return result
