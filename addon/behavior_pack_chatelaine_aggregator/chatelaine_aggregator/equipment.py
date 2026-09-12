# -*- coding: utf-8 -*-
"""Server-authoritative player Chatelaine data and item transactions."""

import copy
import math
import random

import mod.server.extraServerApi as serverApi


DATA_KEY = "chatelaine:player_slots_v1"
SCHEMA_VERSION = 2
SLOT_CHANGED_EVENT = "ChatelainePlayerSlotChangedServerEvent"
SLOTS_RECONCILED_EVENT = "ChatelainePlayerSlotsReconciledServerEvent"
QUICK_EQUIP_CLIENT_EVENT = "ChatelaineQuickEquipSucceededClientEvent"
DEATH_DROP_HORIZONTAL_SPEED = 0.5
DEATH_DROP_VERTICAL_SPEED = 0.2
ACTIVE_DROP_FORWARD_SPEED = 0.3
ACTIVE_DROP_HORIZONTAL_SPREAD = 0.02
ACTIVE_DROP_HEIGHT = 1.12
INVENTORY_ROLLBACK_ATTEMPTS = 2


try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)


def _is_int(value):
    return isinstance(value, INTEGER_TYPES) and not isinstance(value, bool)


def _item_name(item):
    if not isinstance(item, dict):
        return ""
    return item.get("newItemName") or item.get("itemName") or ""


def _item_count(item):
    if not _item_name(item):
        return 0
    value = item.get("count", 1)
    return max(0, int(value)) if _is_int(value) else 1


def _copy_stack(item, count=None):
    if not _item_name(item):
        return {}
    result = copy.deepcopy(item)
    if count is not None:
        result["count"] = max(0, int(count))
    return result if _item_count(result) > 0 else {}


def _item_aux(item):
    if not isinstance(item, dict):
        return 0
    value = item.get("auxValue", 0)
    return int(value) if _is_int(value) else 0


def _same_stack(left, right):
    if not _item_name(left) or _item_name(left) != _item_name(right):
        return False
    if _item_aux(left) != _item_aux(right):
        return False
    for key in (
        "userData",
        "extraId",
        "customTips",
        "enchantData",
        "modEnchantData",
        "durability",
        "maxDurability",
    ):
        if left.get(key) != right.get(key):
            return False
    return True


def _should_play_equip_sound(old_item, new_item):
    """Sound follows new equipment, never count-only merge/split changes."""
    if not _item_name(new_item) or old_item == new_item:
        return False
    # Use the transaction's stack equivalence, not raw dictionary inequality:
    # a merge changes count but must remain silent even with extra fields.
    return not _same_stack(old_item, new_item)


def _matches_expected_item(expected, current):
    """Compare only transport-stable fields used as an intent guard."""
    if not isinstance(expected, dict):
        return True
    if _item_name(expected) != _item_name(current):
        return False
    if _item_count(expected) != _item_count(current):
        return False
    if _item_aux(expected) != _item_aux(current):
        return False
    if (
        "extraId" in expected
        and expected.get("extraId") != (current or {}).get("extraId")
    ):
        return False
    return True


def _item_lock_mode(item):
    if not isinstance(item, dict):
        return None
    value = item.get("itemLockMode")
    if value is None:
        user_data = item.get("userData")
        if isinstance(user_data, dict):
            value = user_data.get("minecraft:item_lock")
            if isinstance(value, dict):
                value = value.get("__value__")
    if (_is_int(value) and int(value) == 1) or value in (
        "slot",
        "lock_in_slot",
    ):
        return "lock_in_slot"
    if (_is_int(value) and int(value) == 2) or value in (
        "inventory",
        "lock_in_inventory",
    ):
        return "lock_in_inventory"
    return None


def _to_engine_value(value):
    value_type = type(value).__name__
    if value_type == "unicode":
        return value.encode("utf-8")
    if value_type == "dict":
        return dict(
            (_to_engine_value(key), _to_engine_value(item))
            for key, item in value.items()
        )
    if value_type in ("list", "tuple", "set", "frozenset"):
        return [_to_engine_value(item) for item in value]
    return value


def parse_clear_command_args(command_args):
    if not isinstance(command_args, (list, tuple)) or len(command_args) != 4:
        return None
    if any(not isinstance(entry, dict) for entry in command_args):
        return None
    target_ids = command_args[0].get("value")
    if not isinstance(target_ids, (list, tuple)):
        return None
    item_value = command_args[1].get("value")
    item_id = None
    if item_value is not None:
        item_id = _item_name(item_value)
        if not item_id:
            return None
    aux_value = command_args[2].get("value")
    if aux_value is not None and (
        not _is_int(aux_value) or int(aux_value) < 0
    ):
        return None
    max_count = command_args[3].get("value")
    if max_count is not None and (
        not _is_int(max_count) or int(max_count) < 0
    ):
        return None
    return {
        "targetIds": tuple(target_ids),
        "itemId": item_id,
        "auxValue": int(aux_value) if aux_value is not None else None,
        "maxCount": int(max_count) if max_count is not None else None,
    }


class ChatelaineEquipmentService(object):

    def __init__(self, system, registry):
        self.system = system
        self.registry = registry
        self.comp_factory = serverApi.GetEngineCompFactory()
        self.command_comp = self.comp_factory.CreateCommand(serverApi.GetLevelId())
        self._destroyed = False
        self._player_data = {}
        self._player_tokens = {}
        self._player_registry_revisions = {}
        self._pending_transactions = {}
        self._writing_players = set()
        self._loading_players = set()

    def on_player_join(self, player_id):
        if (
            self._destroyed or not player_id or not self.registry.is_ready()
            or player_id in self._pending_transactions
            or player_id in self._writing_players
            or player_id in self._loading_players
        ):
            return False
        token = object()
        self._player_tokens[player_id] = token
        self._player_data.pop(player_id, None)
        self._player_registry_revisions.pop(player_id, None)
        self._loading_players.add(player_id)
        try:
            raw = self._get_raw(player_id)
        finally:
            self._loading_players.discard(player_id)
        if (
            raw is None or self._destroyed
            or self._player_tokens.get(player_id) is not token
        ):
            return False
        data, changed = self._reconcile(raw)
        if changed and not self._save_raw(player_id, data):
            return False
        if self._destroyed or self._player_tokens.get(player_id) is not token:
            return False
        self._player_data[player_id] = copy.deepcopy(data)
        self._player_registry_revisions[player_id] = self.registry.get_revision()
        if changed:
            self._broadcast(
                SLOTS_RECONCILED_EVENT,
                {"playerId": player_id, "revision": data["revision"],
                 "slots": copy.deepcopy(data["slots"])},
            )
        return True

    def on_player_left(self, player_id):
        self._player_data.pop(player_id, None)
        self._player_tokens.pop(player_id, None)
        self._player_registry_revisions.pop(player_id, None)
        # An SDK callback can leave during a native inventory write. The
        # current operation retains its compensation lease until it returns;
        # a reentrant join must not adopt its uncommitted persistent candidate.

    def destroy(self):
        self._destroyed = True
        self._player_data.clear()
        self._player_tokens.clear()
        self._player_registry_revisions.clear()
        # In-flight callbacks finish/compensate their own pending transaction.
        # No ordinary getter or new transaction can use this retired instance.

    def reconcile_online_players(self):
        for player_id in tuple(serverApi.GetPlayerList() or ()):
            self.on_player_join(player_id)

    def get_snapshot(self, player_id):
        data = self._get_cached_data(player_id)
        return copy.deepcopy(data) if data is not None else self._empty_data()

    @staticmethod
    def _empty_data():
        return {"schemaVersion": SCHEMA_VERSION, "revision": 0,
                "slots": {}, "mouseCursor": {}}

    def _get_cached_data(self, player_id):
        if (
            self._destroyed or not self.registry.is_ready()
            or self._player_registry_revisions.get(player_id)
            != self.registry.get_revision()
        ):
            return None
        return self._player_data.get(player_id)

    def get_slots(self, player_id):
        return self.get_snapshot(player_id).get("slots", {})

    def get_item(self, player_id, slot_id):
        data = self._get_cached_data(player_id)
        return _copy_stack(data["slots"].get(slot_id)) if data is not None else {}

    def replace_item_data(self, player_id, slot_id, item_dict):
        """Replace one equipped stack's data without bypassing slot authority."""
        data = self._copy_transaction_data(player_id)
        if slot_id not in data.get("slots", {}):
            return False
        current = data["slots"].get(slot_id, {})
        replacement = _copy_stack(item_dict)
        if not current:
            return not replacement
        if not replacement:
            if _item_lock_mode(current) == "lock_in_slot":
                return False
        elif (
            _item_name(replacement) != _item_name(current)
            or _item_count(replacement) != _item_count(current)
            or not self.system.CanEquipCurio(slot_id, replacement)
            or _item_count(replacement)
            > self.system.GetCurioSlotCapacity(slot_id, replacement)
        ):
            return False
        if replacement == current:
            return True
        old_data = copy.deepcopy(data)
        data["slots"][slot_id] = replacement
        return self._save_transaction(
            player_id,
            old_data,
            data,
            "provider_item_data_update",
            ((slot_id, current, replacement),),
        )

    def get_mouse_cursor(self, player_id):
        data = self._get_cached_data(player_id)
        return copy.deepcopy(data.get("mouseCursor", {})) if data is not None else {}

    def mouse_cursor_pick_inventory(
        self, player_id, inventory_slot, take_count, expected_source=None
    ):
        if not self._valid_inventory_slot(inventory_slot):
            return "invalid_inventory_slot"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        data = self._copy_transaction_data(player_id)
        if _item_name(data.get("mouseCursor", {}).get("item")):
            return "cursor_not_empty"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        inventory_slot = int(inventory_slot)
        source = self._get_inventory_item(item_comp, inventory_slot)
        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not source:
            return "empty_source"
        if _item_lock_mode(source) == "lock_in_slot":
            return "locked_source"
        moved = min(_item_count(source), int(take_count))
        old_data = copy.deepcopy(data)
        data["mouseCursor"] = {
            "item": _copy_stack(source, moved),
            "origin": {
                "domain": "inventory",
                "inventorySlot": inventory_slot,
            },
        }
        if not self._save_transaction(
            player_id, old_data, data, "mouse_cursor_pick", (), False
        ):
            return "cursor_write_failed"
        snapshots = {inventory_slot: _copy_stack(source)}
        if not self._replace_inventory_slot(
            item_comp,
            player_id,
            inventory_slot,
            _copy_stack(source, _item_count(source) - moved),
        ):
            self._rollback_transaction(player_id, old_data)
            return self._inventory_write_failure(
                item_comp, player_id, snapshots
            )
        self._emit_changes(
            player_id, data["revision"], "mouse_cursor_pick", ()
        )
        return "ok"

    def mouse_cursor_pick_curio(
        self, player_id, slot_id, take_count, expected_source=None
    ):
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        data = self._copy_transaction_data(player_id)
        if _item_name(data.get("mouseCursor", {}).get("item")):
            return "cursor_not_empty"
        if slot_id not in data.get("slots", {}):
            return "unknown_slot"
        source = data["slots"].get(slot_id, {})
        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not source:
            return "empty_source"
        if _item_lock_mode(source) == "lock_in_slot":
            return "locked_source"
        moved = min(_item_count(source), int(take_count))
        source_after = _copy_stack(source, _item_count(source) - moved)
        old_data = copy.deepcopy(data)
        data["slots"][slot_id] = source_after
        data["mouseCursor"] = {
            "item": _copy_stack(source, moved),
            "origin": {"domain": "curio", "slotId": slot_id},
        }
        changes = ((slot_id, source, source_after),)
        if not self._save_transaction(
            player_id, old_data, data, "mouse_cursor_pick", changes
        ):
            return "cursor_write_failed"
        return "ok"

    def mouse_cursor_place_inventory(
        self,
        player_id,
        inventory_slot,
        take_count,
        expected_cursor=None,
        expected_target=None,
    ):
        if not self._valid_inventory_slot(inventory_slot):
            return "invalid_inventory_slot"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        data = self._copy_transaction_data(player_id)
        cursor = data.get("mouseCursor", {})
        source = cursor.get("item", {})
        if not _matches_expected_item(expected_cursor, source):
            return "cursor_changed"
        if not source:
            return "empty_cursor"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        inventory_slot = int(inventory_slot)
        target = self._get_inventory_item(item_comp, inventory_slot)
        if not _matches_expected_item(expected_target, target):
            return "target_changed"
        if _item_lock_mode(target) == "lock_in_slot":
            return "locked_target"
        source_count = _item_count(source)
        take_count = min(source_count, int(take_count))
        if not target:
            moved = min(take_count, self.system.GetNativeItemMaxStack(source))
            target_after = _copy_stack(source, moved)
            cursor_after = _copy_stack(source, source_count - moved)
        elif _same_stack(source, target):
            room = max(
                0,
                self.system.GetNativeItemMaxStack(target) - _item_count(target),
            )
            moved = min(take_count, room)
            if moved <= 0:
                return "full"
            target_after = _copy_stack(target, _item_count(target) + moved)
            cursor_after = _copy_stack(source, source_count - moved)
        else:
            if take_count != source_count:
                return "partial_swap_denied"
            target_after = _copy_stack(source)
            cursor_after = _copy_stack(target)
        old_data = copy.deepcopy(data)
        data["mouseCursor"] = self._cursor_after(cursor, cursor_after)
        if not self._save_transaction(
            player_id, old_data, data, "mouse_cursor_place", (), False
        ):
            return "cursor_write_failed"
        snapshots = {inventory_slot: _copy_stack(target)}
        if not self._replace_inventory_slot(
            item_comp, player_id, inventory_slot, target_after
        ):
            self._rollback_transaction(player_id, old_data)
            return self._inventory_write_failure(
                item_comp, player_id, snapshots
            )
        self._emit_changes(
            player_id, data["revision"], "mouse_cursor_place", ()
        )
        return "ok"

    def mouse_cursor_place_curio(
        self,
        player_id,
        slot_id,
        take_count,
        expected_cursor=None,
        expected_target=None,
    ):
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        data = self._copy_transaction_data(player_id)
        if slot_id not in data.get("slots", {}):
            return "unknown_slot"
        cursor = data.get("mouseCursor", {})
        source = cursor.get("item", {})
        target = data["slots"].get(slot_id, {})
        if not _matches_expected_item(expected_cursor, source):
            return "cursor_changed"
        if not _matches_expected_item(expected_target, target):
            return "target_changed"
        if not source:
            return "empty_cursor"
        if _item_lock_mode(source) == "lock_in_inventory":
            return "locked_source"
        if not self.system.CanEquipCurio(slot_id, source):
            return "incompatible"
        if _item_lock_mode(target) == "lock_in_slot":
            return "locked_target"
        source_count = _item_count(source)
        take_count = min(source_count, int(take_count))
        capacity = self.system.GetCurioSlotCapacity(slot_id, source)
        if not target:
            moved = min(take_count, capacity)
            if moved <= 0:
                return "full"
            target_after = _copy_stack(source, moved)
            cursor_after = _copy_stack(source, source_count - moved)
        elif _same_stack(source, target):
            moved = min(take_count, max(0, capacity - _item_count(target)))
            if moved <= 0:
                return "full"
            target_after = _copy_stack(target, _item_count(target) + moved)
            cursor_after = _copy_stack(source, source_count - moved)
        else:
            if take_count != source_count:
                return "partial_swap_denied"
            if source_count > capacity:
                return "source_over_capacity"
            target_after = _copy_stack(source)
            cursor_after = _copy_stack(target)
        old_data = copy.deepcopy(data)
        data["slots"][slot_id] = target_after
        data["mouseCursor"] = self._cursor_after(cursor, cursor_after)
        changes = ((slot_id, target, target_after),)
        if not self._save_transaction(
            player_id, old_data, data, "mouse_cursor_place", changes
        ):
            return "cursor_write_failed"
        return "ok"

    def mouse_cursor_coalesce_inventory(
        self, player_id, expected_cursor=None
    ):
        data = self._copy_transaction_data(player_id)
        cursor = data.get("mouseCursor", {})
        source = cursor.get("item", {})
        if not _matches_expected_item(expected_cursor, source) or not source:
            return "cursor_changed"
        wanted = self.system.GetNativeItemMaxStack(source) - _item_count(source)
        if wanted <= 0:
            return "full"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        snapshots = {}
        writes = []
        moved_total = 0
        for slot in range(36):
            if wanted <= 0:
                break
            current = self._get_inventory_item(item_comp, slot)
            if (
                not current
                or _item_lock_mode(current) == "lock_in_slot"
                or not _same_stack(source, current)
            ):
                continue
            moved = min(wanted, _item_count(current))
            snapshots[slot] = _copy_stack(current)
            writes.append((
                slot,
                _copy_stack(current, _item_count(current) - moved),
            ))
            moved_total += moved
            wanted -= moved
        if moved_total <= 0:
            return "nothing_to_coalesce"
        old_data = copy.deepcopy(data)
        data["mouseCursor"] = self._cursor_after(
            cursor,
            _copy_stack(source, _item_count(source) + moved_total),
        )
        if not self._save_transaction(
            player_id, old_data, data, "mouse_cursor_coalesce", (), False
        ):
            return "cursor_write_failed"
        for slot, after in writes:
            if not self._replace_inventory_slot(
                item_comp, player_id, slot, after
            ):
                self._rollback_transaction(player_id, old_data)
                return self._inventory_write_failure(
                    item_comp, player_id, snapshots
                )
        self._emit_changes(
            player_id, data["revision"], "mouse_cursor_coalesce", ()
        )
        return "ok"

    def mouse_cursor_distribute_inventory(
        self, player_id, expected_cursor, targets, mode
    ):
        if not isinstance(targets, list) or not targets or len(targets) > 36:
            return "invalid_targets"
        if mode not in ("even", "single"):
            return "invalid_distribution_mode"
        data = self._copy_transaction_data(player_id)
        cursor = data.get("mouseCursor", {})
        source = cursor.get("item", {})
        if not _matches_expected_item(expected_cursor, source) or not source:
            return "cursor_changed"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        ordered = []
        snapshots = {}
        seen = set()
        for entry in targets:
            slot = entry.get("slot") if isinstance(entry, dict) else None
            if not self._valid_inventory_slot(slot) or int(slot) in seen:
                return "invalid_targets"
            slot = int(slot)
            seen.add(slot)
            current = self._get_inventory_item(item_comp, slot)
            if (
                _item_lock_mode(current) == "lock_in_slot"
                or (current and not _same_stack(source, current))
                or not _matches_expected_item(entry.get("expected"), current)
            ):
                return "target_changed"
            snapshots[slot] = _copy_stack(current)
            ordered.append((slot, current))
        held = _item_count(source)
        quota = 1 if mode == "single" else held // len(ordered)
        if quota <= 0:
            return "nothing_to_distribute"
        remaining = held
        maximum = self.system.GetNativeItemMaxStack(source)
        writes = []
        for slot, current in ordered:
            moved = min(
                quota,
                max(0, maximum - _item_count(current)),
                remaining,
            )
            if moved <= 0:
                continue
            writes.append((
                slot,
                _copy_stack(current or source, _item_count(current) + moved),
            ))
            remaining -= moved
        if remaining == held:
            return "nothing_to_distribute"
        old_data = copy.deepcopy(data)
        data["mouseCursor"] = self._cursor_after(
            cursor, _copy_stack(source, remaining)
        )
        if not self._save_transaction(
            player_id, old_data, data, "mouse_cursor_distribute", (), False
        ):
            return "cursor_write_failed"
        for slot, after in writes:
            if not self._replace_inventory_slot(
                item_comp, player_id, slot, after
            ):
                self._rollback_transaction(player_id, old_data)
                return self._inventory_write_failure(
                    item_comp, player_id, snapshots
                )
        self._emit_changes(
            player_id, data["revision"], "mouse_cursor_distribute", ()
        )
        return "ok"

    def stream_distribution_update(
        self,
        player_id,
        context,
        distribution_id,
        cursor_owned,
        source_slot,
        expected_source,
        held_count,
        targets,
        mode,
    ):
        """Apply one cumulative drag path as an authoritative overwrite."""
        if not _is_int(distribution_id) or int(distribution_id) < 1:
            return ("invalid_distribution_id", context)
        if mode not in ("even", "single"):
            return ("invalid_distribution_mode", context)
        if not isinstance(targets, list) or not targets or len(targets) > 36:
            return ("invalid_targets", context)
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return ("no_item_component", context)

        data = None
        cursor = None
        if context is None:
            if not _is_int(held_count) or int(held_count) <= 0:
                return ("invalid_count", None)
            if cursor_owned:
                data = self._copy_transaction_data(player_id)
                cursor = data.get("mouseCursor", {})
                source = cursor.get("item", {})
                if (
                    not source
                    or not _matches_expected_item(expected_source, source)
                    or int(held_count) != _item_count(source)
                ):
                    return ("cursor_changed", None)
                source_slot = -1
                base_unheld = 0
            else:
                if not self._valid_inventory_slot(source_slot):
                    return ("invalid_source", None)
                source_slot = int(source_slot)
                source = self._get_inventory_item(item_comp, source_slot)
                if (
                    not source
                    or _item_lock_mode(source) == "lock_in_slot"
                    or not _matches_expected_item(expected_source, source)
                    or int(held_count) > _item_count(source)
                ):
                    return ("source_changed", None)
                base_unheld = _item_count(source) - int(held_count)
            next_context = {
                "distributionId": int(distribution_id),
                "cursorOwned": bool(cursor_owned),
                "sourceSlot": int(source_slot),
                "sourceItem": _copy_stack(source),
                "cursorOrigin": copy.deepcopy(
                    cursor.get("origin", {}) if cursor_owned else {}
                ),
                "heldCount": int(held_count),
                "baseUnheld": int(base_unheld),
                "mode": mode,
                "targetOrder": [],
                "targetBaselines": {},
                "weights": {},
                "allocations": {},
            }
        else:
            if (
                context.get("distributionId") != int(distribution_id)
                or bool(context.get("cursorOwned")) != bool(cursor_owned)
                or context.get("mode") != mode
            ):
                return ("distribution_changed", context)
            next_context = copy.deepcopy(context)
            source = next_context.get("sourceItem", {})
            held_count = int(next_context.get("heldCount", 0))
            source_slot = int(next_context.get("sourceSlot", -1))
            base_unheld = int(next_context.get("baseUnheld", 0))
            if cursor_owned:
                data = self._copy_transaction_data(player_id)
                cursor = data.get("mouseCursor", {})

        order = next_context["targetOrder"]
        baselines = next_context["targetBaselines"]
        previous_weights = next_context.get("weights", {})
        next_weights = {}
        seen = set()
        for entry in targets:
            if not isinstance(entry, dict):
                return ("invalid_targets", context)
            slot = entry.get("slot")
            weight = entry.get("weight")
            if (
                not self._valid_inventory_slot(slot)
                or int(slot) in seen
                or not _is_int(weight)
                or int(weight) < 1
                or (not cursor_owned and int(slot) == source_slot)
            ):
                return ("invalid_targets", context)
            slot = int(slot)
            seen.add(slot)
            weight = int(weight)
            if weight < int(previous_weights.get(slot, 0)):
                return ("invalid_target_weight", context)
            if slot not in baselines:
                current = self._get_inventory_item(item_comp, slot)
                if (
                    _item_lock_mode(current) == "lock_in_slot"
                    or (current and not _same_stack(source, current))
                    or not _matches_expected_item(entry.get("expected"), current)
                ):
                    return ("target_changed", context)
                baselines[slot] = _copy_stack(current)
                order.append(slot)
            next_weights[slot] = weight
        if set(order) != set(next_weights):
            return ("invalid_targets", context)
        # Every recorded target must receive at least one item. This prevents
        # floor division from accepting 11 zero-quota cells for 10 items.
        if len(order) > held_count:
            return ("invalid_targets", context)
        if mode == "single" and sum(next_weights.values()) > held_count:
            return ("invalid_target_weight", context)

        previous_allocations = next_context.get("allocations", {})
        for slot in order:
            baseline = baselines.get(slot, {})
            expected = _copy_stack(
                baseline or source,
                _item_count(baseline)
                + int(previous_allocations.get(slot, 0)),
            )
            if not self._inventory_items_equal(
                self._get_inventory_item(item_comp, slot), expected
            ):
                return ("target_changed", context)
        previous_total = sum(
            int(previous_allocations.get(slot, 0)) for slot in order
        )
        if cursor_owned:
            current_source = (cursor or {}).get("item", {})
            expected_source_now = _copy_stack(
                source, held_count - previous_total
            )
        else:
            current_source = self._get_inventory_item(item_comp, source_slot)
            expected_source_now = _copy_stack(
                source, base_unheld + held_count - previous_total
            )
        if not self._inventory_items_equal(
            current_source, expected_source_now
        ):
            return ("source_changed", context)

        total_weight = sum(next_weights.values())
        maximum = self.system.GetNativeItemMaxStack(source)
        if mode == "single":
            quotas = [next_weights[slot] for slot in order]
        else:
            quotas = [
                max(1, held_count * next_weights[slot] // total_weight)
                for slot in order
            ]
            overflow = max(0, sum(quotas) - held_count)
            while overflow > 0:
                largest = max(
                    range(len(quotas)), key=lambda index: quotas[index]
                )
                if quotas[largest] <= 1:
                    break
                quotas[largest] -= 1
                overflow -= 1
        remaining = held_count
        allocations = {}
        for index, slot in enumerate(order):
            moved = min(
                quotas[index],
                max(0, maximum - _item_count(baselines.get(slot, {}))),
                remaining,
            )
            if moved <= 0:
                return ("target_full", context)
            allocations[slot] = moved
            remaining -= moved

        snapshots = dict(
            (slot, self._get_inventory_item(item_comp, slot))
            for slot in order
        )
        if not cursor_owned:
            snapshots[source_slot] = self._get_inventory_item(
                item_comp, source_slot
            )
        old_data = copy.deepcopy(data) if cursor_owned else None
        if cursor_owned:
            data["mouseCursor"] = self._cursor_after(
                {
                    "origin": copy.deepcopy(
                        next_context.get("cursorOrigin", {})
                    )
                },
                _copy_stack(source, remaining),
            )
            if not self._save_transaction(
                player_id,
                old_data,
                data,
                "mouse_cursor_stream_distribute",
                (),
                False,
            ):
                return ("cursor_write_failed", context)

        writes = []
        for slot in order:
            baseline = baselines.get(slot, {})
            writes.append((
                slot,
                _copy_stack(
                    baseline or source,
                    _item_count(baseline) + allocations[slot],
                ),
            ))
        if not cursor_owned:
            writes.append((
                source_slot,
                _copy_stack(source, base_unheld + remaining),
            ))
        for slot, after in writes:
            if not self._replace_inventory_slot(
                item_comp, player_id, slot, after
            ):
                if cursor_owned:
                    self._rollback_transaction(player_id, old_data)
                return (
                    self._inventory_write_failure(
                        item_comp, player_id, snapshots
                    ),
                    context,
                )
        next_context["weights"] = next_weights
        next_context["allocations"] = allocations
        if cursor_owned:
            self._emit_changes(
                player_id,
                data["revision"],
                "mouse_cursor_stream_distribute",
                (),
            )
        return ("ok", next_context)

    def return_mouse_cursor(self, player_id):
        cursor = self.get_mouse_cursor(player_id)
        item = cursor.get("item", {})
        if not item:
            return "ok"
        origin = cursor.get("origin", {})
        if origin.get("domain") == "curio" and origin.get("slotId"):
            slot_id = origin.get("slotId")
            data = self.get_snapshot(player_id)
            target = data.get("slots", {}).get(slot_id, {})
            result = self.mouse_cursor_place_curio(
                player_id,
                slot_id,
                _item_count(item),
                item,
                target,
            )
            if result == "ok" and not self.get_mouse_cursor(player_id).get("item"):
                return "ok"
            cursor = self.get_mouse_cursor(player_id)
            item = cursor.get("item", {})
            if not item:
                return "ok"
        candidates = []
        if origin.get("domain") == "inventory":
            candidates.append(origin.get("inventorySlot"))
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        for same_pass in (True, False):
            for slot in range(36):
                if slot not in candidates:
                    candidates.append(slot)
            for slot in tuple(candidates):
                current_cursor = self.get_mouse_cursor(player_id)
                held = current_cursor.get("item", {})
                if not held:
                    return "ok"
                target = self._get_inventory_item(item_comp, slot)
                if same_pass and not (target and _same_stack(held, target)):
                    continue
                if not same_pass and target:
                    continue
                result = self.mouse_cursor_place_inventory(
                    player_id,
                    slot,
                    _item_count(held),
                    held,
                    target,
                )
                if result == "ok" and not self.get_mouse_cursor(player_id).get("item"):
                    return "ok"
        return "cursor_not_returned"

    @staticmethod
    def _cursor_after(cursor, item):
        if not _item_name(item):
            return {}
        return {
            "item": _copy_stack(item),
            "origin": copy.deepcopy(cursor.get("origin", {})),
        }

    def get_items_by_type(self, player_id, type_id):
        registry = self.registry.get_snapshot()
        result = {}
        for slot_id, item in self.get_slots(player_id).items():
            slot = registry.get("slotsById", {}).get(slot_id, {})
            if type_id in slot.get("acceptedTypes", ()) and item:
                result[slot_id] = _copy_stack(item)
        return result

    def _replace_inventory_slot(self, item_comp, player_id, slot, item):
        current = self._get_inventory_item(item_comp, slot)
        if item and current and _same_stack(current, item):
            return bool(item_comp.SetInvItemNum(slot, _item_count(item)))
        if current and not item_comp.SetInvItemNum(slot, 0):
            return False
        if not item:
            return True
        return bool(item_comp.SpawnItemToPlayerInv(
            _copy_stack(item),
            player_id,
            slot,
        ))

    @staticmethod
    def _inventory_items_equal(left, right):
        left_count = _item_count(left)
        right_count = _item_count(right)
        if left_count <= 0 or right_count <= 0:
            return left_count == right_count
        return left_count == right_count and _same_stack(left, right)

    def _restore_inventory_slots(self, item_comp, player_id, snapshots):
        for _attempt in range(INVENTORY_ROLLBACK_ATTEMPTS):
            for slot, item in snapshots.items():
                current = self._get_inventory_item(item_comp, slot)
                if self._inventory_items_equal(current, item):
                    continue
                self._replace_inventory_slot(
                    item_comp,
                    player_id,
                    slot,
                    _copy_stack(item),
                )
            if all(
                self._inventory_items_equal(
                    self._get_inventory_item(item_comp, slot),
                    item,
                )
                for slot, item in snapshots.items()
            ):
                return True
        return False

    def _inventory_write_failure(self, item_comp, player_id, snapshots):
        if self._restore_inventory_slots(item_comp, player_id, snapshots):
            return "inventory_write_failed"
        return "inventory_rollback_failed"

    def transfer_inventory_to_inventory(
        self,
        player_id,
        source_slot,
        target_slot,
        take_count,
        expected_source=None,
        expected_target=None,
    ):
        if (
            not self._valid_inventory_slot(source_slot)
            or not self._valid_inventory_slot(target_slot)
        ):
            return "invalid_inventory_slot"
        source_slot = int(source_slot)
        target_slot = int(target_slot)
        if source_slot == target_slot:
            return "same_slot"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        source = self._get_inventory_item(item_comp, source_slot)
        target = self._get_inventory_item(item_comp, target_slot)
        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not _matches_expected_item(expected_target, target):
            return "target_changed"
        if not source:
            return "empty_source"
        if _item_lock_mode(source) == "lock_in_slot":
            return "locked_source"
        if _item_lock_mode(target) == "lock_in_slot":
            return "locked_target"

        source_count = _item_count(source)
        take_count = min(source_count, int(take_count))
        if target and _same_stack(source, target):
            room = max(
                0,
                self.system.GetNativeItemMaxStack(target)
                - _item_count(target),
            )
            moved = min(take_count, room)
            if moved <= 0:
                return "full"
            source_after = _copy_stack(source, source_count - moved)
            target_after = _copy_stack(
                target,
                _item_count(target) + moved,
            )
        elif not target:
            moved = min(
                take_count,
                self.system.GetNativeItemMaxStack(source),
            )
            if moved <= 0:
                return "full"
            source_after = _copy_stack(source, source_count - moved)
            target_after = _copy_stack(source, moved)
        else:
            if take_count != source_count:
                return "partial_swap_denied"
            source_after = _copy_stack(target)
            target_after = _copy_stack(source)

        snapshots = {
            source_slot: _copy_stack(source),
            target_slot: _copy_stack(target),
        }
        if not self._replace_inventory_slot(
            item_comp,
            player_id,
            source_slot,
            source_after,
        ):
            return self._inventory_write_failure(
                item_comp,
                player_id,
                snapshots,
            )
        if not self._replace_inventory_slot(
            item_comp,
            player_id,
            target_slot,
            target_after,
        ):
            return self._inventory_write_failure(
                item_comp,
                player_id,
                snapshots,
            )
        return "ok"

    def coalesce_inventory(
        self,
        player_id,
        source_slot,
        expected_source=None,
    ):
        if not self._valid_inventory_slot(source_slot):
            return "invalid_source"
        source_slot = int(source_slot)
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        source = self._get_inventory_item(item_comp, source_slot)
        if (
            not source
            or _item_lock_mode(source) == "lock_in_slot"
            or not _matches_expected_item(expected_source, source)
        ):
            return "source_changed"
        wanted = (
            self.system.GetNativeItemMaxStack(source)
            - _item_count(source)
        )
        if wanted <= 0:
            return "full"

        snapshots = {source_slot: _copy_stack(source)}
        moves = []
        for slot in range(36):
            if slot == source_slot or wanted <= 0:
                continue
            current = self._get_inventory_item(item_comp, slot)
            if (
                not current
                or _item_lock_mode(current) == "lock_in_slot"
                or not _same_stack(source, current)
            ):
                continue
            moved = min(wanted, _item_count(current))
            snapshots[slot] = _copy_stack(current)
            moves.append((
                slot,
                _copy_stack(current, _item_count(current) - moved),
            ))
            wanted -= moved
        if not moves:
            return "nothing_to_coalesce"
        moved_total = sum(
            _item_count(snapshots[slot]) - _item_count(after)
            for slot, after in moves
        )
        for slot, after in moves:
            if not self._replace_inventory_slot(
                item_comp,
                player_id,
                slot,
                after,
            ):
                return self._inventory_write_failure(
                    item_comp,
                    player_id,
                    snapshots,
                )
        if not self._replace_inventory_slot(
            item_comp,
            player_id,
            source_slot,
            _copy_stack(source, _item_count(source) + moved_total),
        ):
            return self._inventory_write_failure(
                item_comp,
                player_id,
                snapshots,
            )
        return "ok"

    def distribute_inventory(
        self,
        player_id,
        source_slot,
        expected_source,
        held_count,
        targets,
        mode,
    ):
        if not self._valid_inventory_slot(source_slot):
            return "invalid_source"
        if not isinstance(targets, list) or not targets or len(targets) > 35:
            return "invalid_targets"
        if mode not in ("even", "single"):
            return "invalid_distribution_mode"
        if not _is_int(held_count) or int(held_count) <= 0:
            return "invalid_count"
        source_slot = int(source_slot)
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        source = self._get_inventory_item(item_comp, source_slot)
        if (
            not source
            or _item_lock_mode(source) == "lock_in_slot"
            or not _matches_expected_item(expected_source, source)
        ):
            return "source_changed"

        ordered = []
        seen = set()
        snapshots = {source_slot: _copy_stack(source)}
        for entry in targets:
            if not isinstance(entry, dict):
                return "invalid_targets"
            slot = entry.get("slot")
            if (
                not self._valid_inventory_slot(slot)
                or int(slot) == source_slot
                or int(slot) in seen
            ):
                return "invalid_targets"
            slot = int(slot)
            seen.add(slot)
            current = self._get_inventory_item(item_comp, slot)
            if (
                _item_lock_mode(current) == "lock_in_slot"
                or (current and not _same_stack(source, current))
                or not _matches_expected_item(entry.get("expected"), current)
            ):
                return "target_changed"
            snapshots[slot] = _copy_stack(current)
            ordered.append((slot, current))

        source_count = _item_count(source)
        held_count = int(held_count)
        if held_count > source_count:
            return "invalid_count"
        quota = 1 if mode == "single" else held_count // len(ordered)
        if quota <= 0:
            return "nothing_to_distribute"
        remaining = held_count
        writes = []
        maximum = self.system.GetNativeItemMaxStack(source)
        for slot, current in ordered:
            room = maximum - _item_count(current)
            moved = min(quota, max(0, room), remaining)
            if moved <= 0:
                continue
            writes.append((
                slot,
                _copy_stack(
                    current or source,
                    _item_count(current) + moved,
                ),
            ))
            remaining -= moved
        moved_total = held_count - remaining
        if moved_total <= 0:
            return "nothing_to_distribute"
        writes.append((
            source_slot,
            _copy_stack(source, source_count - moved_total),
        ))
        for slot, after in writes:
            if not self._replace_inventory_slot(
                item_comp,
                player_id,
                slot,
                after,
            ):
                return self._inventory_write_failure(
                    item_comp,
                    player_id,
                    snapshots,
                )
        return "ok"

    def transfer_inventory_to_curio(
        self,
        player_id,
        inventory_slot,
        slot_id,
        take_count,
        reason="inventory_transfer",
        expected_source=None,
        expected_target=None,
    ):
        if not self._valid_inventory_slot(inventory_slot):
            return "invalid_inventory_slot"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        source = self._get_inventory_item(item_comp, inventory_slot)
        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not source:
            return "empty_source"
        if _item_lock_mode(source) is not None:
            return "locked_source"
        if not self.system.CanEquipCurio(slot_id, source):
            return "incompatible"

        data = self._copy_transaction_data(player_id)
        if slot_id not in data["slots"]:
            return "unknown_slot"
        target = data["slots"].get(slot_id, {})
        if not _matches_expected_item(expected_target, target):
            return "target_changed"
        if _item_lock_mode(target) == "lock_in_slot":
            return "locked_target"
        source_count = _item_count(source)
        take_count = int(take_count)
        capacity = self.system.GetCurioSlotCapacity(slot_id, source)
        if capacity <= 0:
            return "incompatible"

        if not target:
            moved = min(take_count, source_count, capacity)
            if moved <= 0:
                return "full"
            new_target = _copy_stack(source, moved)
            new_source_count = source_count - moved
        elif _same_stack(source, target):
            room = capacity - _item_count(target)
            moved = min(take_count, source_count, room)
            if moved <= 0:
                return "full"
            new_target = _copy_stack(target, _item_count(target) + moved)
            new_source_count = source_count - moved
        else:
            if take_count != source_count:
                return "partial_swap_denied"
            if source_count > capacity:
                return "source_over_capacity"
            moved = source_count
            new_target = _copy_stack(source)
            new_source_count = 0

        old_data = copy.deepcopy(data)
        data["slots"][slot_id] = new_target
        if not self._save_transaction(
            player_id,
            old_data,
            data,
            reason,
            ((slot_id, target, new_target),),
            False,
        ):
            return "curio_write_failed"
        inventory_after = (
            _copy_stack(target)
            if target and not _same_stack(source, target)
            else _copy_stack(source, new_source_count)
        )
        snapshots = {inventory_slot: _copy_stack(source)}
        if not self._replace_inventory_slot(
            item_comp,
            player_id,
            inventory_slot,
            inventory_after,
        ):
            self._rollback_transaction(player_id, old_data)
            return self._inventory_write_failure(
                item_comp,
                player_id,
                snapshots,
            )
        self._emit_changes(
            player_id,
            data["revision"],
            reason,
            ((slot_id, target, new_target),),
        )
        return "ok"

    def transfer_curio_to_inventory(
        self,
        player_id,
        slot_id,
        inventory_slot,
        take_count,
        reason="inventory_transfer",
        expected_source=None,
        expected_target=None,
    ):
        if not self._valid_inventory_slot(inventory_slot):
            return "invalid_inventory_slot"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        data = self._copy_transaction_data(player_id)
        source = data.get("slots", {}).get(slot_id, {})
        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not source:
            return "empty_source"
        if _item_lock_mode(source) == "lock_in_slot":
            return "locked_source"
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return "no_item_component"
        target = self._get_inventory_item(item_comp, inventory_slot)
        if not _matches_expected_item(expected_target, target):
            return "target_changed"
        if _item_lock_mode(target) == "lock_in_slot":
            return "locked_target"
        source_count = _item_count(source)
        take_count = int(take_count)

        if not target:
            moved = min(take_count, source_count)
            new_source = _copy_stack(source, source_count - moved)
            new_inventory = _copy_stack(source, moved)
        elif _same_stack(source, target):
            native_capacity = self.system.GetNativeItemMaxStack(source)
            room = native_capacity - _item_count(target)
            moved = min(take_count, source_count, room)
            if moved <= 0:
                return "full"
            new_source = _copy_stack(source, source_count - moved)
            new_inventory = _copy_stack(
                target,
                _item_count(target) + moved,
            )
        else:
            if take_count != source_count:
                return "partial_swap_denied"
            if _item_lock_mode(target) is not None:
                return "locked_target"
            if not self.system.CanEquipCurio(slot_id, target):
                return "incompatible"
            capacity = self.system.GetCurioSlotCapacity(slot_id, target)
            if _item_count(target) > capacity:
                return "target_over_capacity"
            moved = source_count
            new_source = _copy_stack(target)
            new_inventory = _copy_stack(source)

        old_data = copy.deepcopy(data)
        data["slots"][slot_id] = new_source
        if not self._save_transaction(
            player_id,
            old_data,
            data,
            reason,
            ((slot_id, source, new_source),),
            False,
        ):
            return "curio_write_failed"
        snapshots = {inventory_slot: _copy_stack(target)}
        if not self._replace_inventory_slot(
            item_comp,
            player_id,
            inventory_slot,
            new_inventory,
        ):
            self._rollback_transaction(player_id, old_data)
            return self._inventory_write_failure(
                item_comp,
                player_id,
                snapshots,
            )
        self._emit_changes(
            player_id,
            data["revision"],
            reason,
            ((slot_id, source, new_source),),
        )
        return "ok"

    def transfer_curio_to_curio(
        self,
        player_id,
        source_slot_id,
        target_slot_id,
        take_count,
        reason="curio_transfer",
        expected_source=None,
        expected_target=None,
    ):
        if source_slot_id == target_slot_id:
            return "same_slot"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        data = self._copy_transaction_data(player_id)
        slots = data.get("slots", {})
        if source_slot_id not in slots or target_slot_id not in slots:
            return "unknown_slot"
        source = slots.get(source_slot_id, {})
        target = slots.get(target_slot_id, {})
        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not _matches_expected_item(expected_target, target):
            return "target_changed"
        if not source:
            return "empty_source"
        if _item_lock_mode(source) == "lock_in_slot":
            return "locked_source"
        if _item_lock_mode(target) == "lock_in_slot":
            return "locked_target"
        if not self.system.CanEquipCurio(target_slot_id, source):
            return "incompatible"

        source_count = _item_count(source)
        take_count = int(take_count)
        target_capacity = self.system.GetCurioSlotCapacity(
            target_slot_id,
            source,
        )
        if not target:
            moved = min(take_count, source_count, target_capacity)
            if moved <= 0:
                return "full"
            new_source = _copy_stack(source, source_count - moved)
            new_target = _copy_stack(source, moved)
        elif _same_stack(source, target):
            room = target_capacity - _item_count(target)
            moved = min(take_count, source_count, room)
            if moved <= 0:
                return "full"
            new_source = _copy_stack(source, source_count - moved)
            new_target = _copy_stack(target, _item_count(target) + moved)
        else:
            if take_count != source_count:
                return "partial_swap_denied"
            if not self.system.CanEquipCurio(source_slot_id, target):
                return "reverse_incompatible"
            source_capacity = self.system.GetCurioSlotCapacity(
                source_slot_id,
                target,
            )
            if (
                source_count > target_capacity
                or _item_count(target) > source_capacity
            ):
                return "swap_over_capacity"
            new_source = _copy_stack(target)
            new_target = _copy_stack(source)

        old_data = copy.deepcopy(data)
        slots[source_slot_id] = new_source
        slots[target_slot_id] = new_target
        changes = (
            (source_slot_id, source, new_source),
            (target_slot_id, target, new_target),
        )
        if not self._save_transaction(
            player_id,
            old_data,
            data,
            reason,
            changes,
        ):
            return "curio_write_failed"
        return "ok"

    def quick_equip_selected_item(self, player_id, expected_item=None):
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return False
        inventory_slot = item_comp.GetSelectSlotId()
        if not self._valid_inventory_slot(inventory_slot):
            return False
        source = self._get_inventory_item(item_comp, inventory_slot)
        item_id = _item_name(source)
        expected_id = _item_name(expected_item)
        if expected_id and expected_id != item_id:
            return False
        item_config = self.registry.get_snapshot().get(
            "itemsById",
            {},
        ).get(item_id)
        if not item_config or not item_config.get("equipOnUse"):
            return False
        if _item_lock_mode(source) is not None:
            return False

        candidates = self._ordered_compatible_slots(source)
        same_slots = []
        empty_slots = []
        replace_slots = []
        slots = self.get_slots(player_id)
        for slot_id in candidates:
            target = slots.get(slot_id, {})
            if _item_lock_mode(target) == "lock_in_slot":
                continue
            if target and _same_stack(source, target):
                if _item_count(target) < self.system.GetCurioSlotCapacity(
                    slot_id,
                    source,
                ):
                    same_slots.append(slot_id)
            elif not target:
                empty_slots.append(slot_id)
            else:
                replace_slots.append(slot_id)
        ordered = same_slots + empty_slots
        if _item_count(source) == 1:
            ordered += replace_slots
        if not ordered:
            return False
        result = self.transfer_inventory_to_curio(
            player_id,
            inventory_slot,
            ordered[0],
            1,
            "item_use_quick_equip",
        )
        if result != "ok":
            return False
        if _should_play_equip_sound(slots.get(ordered[0], {}), source):
            self._play_equip_sound(player_id, item_config.get("quickEquipSound"))
        self.system.NotifyToClient(
            player_id, QUICK_EQUIP_CLIENT_EVENT, {"slotId": ordered[0]},
        )
        return True

    def drop_inventory_selection(
        self,
        player_id,
        source_domain,
        source_value,
        take_count,
        expected_source=None,
    ):
        """Drop a selected stack portion with source-first rollback semantics."""
        if source_domain not in ("inventory", "curio", "cursor"):
            return "invalid_source_domain"
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        take_count = int(take_count)

        data = None
        old_data = None
        item_comp = None
        source = {}
        if source_domain == "inventory":
            if not self._valid_inventory_slot(source_value):
                return "invalid_inventory_slot"
            source_value = int(source_value)
            item_comp = self.comp_factory.CreateItem(player_id)
            if item_comp is None:
                return "no_item_component"
            source = self._get_inventory_item(item_comp, source_value)
        else:
            data = self._copy_transaction_data(player_id)
            old_data = copy.deepcopy(data)
            if source_domain == "cursor":
                source = _copy_stack(
                    data.get("mouseCursor", {}).get("item", {})
                )
            else:
                if source_value not in data.get("slots", {}):
                    return "invalid_curio_slot"
                source = _copy_stack(data["slots"].get(source_value, {}))

        if not _matches_expected_item(expected_source, source):
            return "source_changed"
        if not source:
            return "empty_source"
        # Both vanilla lock modes prohibit throwing the stack out of the
        # inventory.  Other inventory operations intentionally distinguish
        # these modes, but a world drop removes the item from both contexts.
        if _item_lock_mode(source) is not None:
            return "locked_source"

        drop_context = self._active_drop_context(player_id)
        if drop_context is None:
            return "drop_context_unavailable"
        take = min(take_count, _item_count(source))
        dropped = _copy_stack(source, take)
        remainder = _copy_stack(source, _item_count(source) - take)

        if source_domain == "inventory":
            snapshots = {source_value: _copy_stack(source)}
            if not self._replace_inventory_slot(
                item_comp,
                player_id,
                source_value,
                remainder,
            ):
                return self._inventory_write_failure(
                    item_comp,
                    player_id,
                    snapshots,
                )
        else:
            if source_domain == "cursor":
                cursor = data.get("mouseCursor", {})
                data["mouseCursor"] = self._cursor_after(cursor, remainder)
                changes = ()
            else:
                data["slots"][source_value] = remainder
                changes = ((source_value, source, remainder),)
            if not self._save_transaction(
                player_id,
                old_data,
                data,
                "inventory_drop",
                changes,
                emit=False,
            ):
                return "curio_write_failed"

        entity_id = self._spawn_active_drop(
            player_id,
            dropped,
            drop_context,
        )
        if not entity_id:
            if source_domain == "inventory":
                if self._restore_inventory_slots(
                    item_comp,
                    player_id,
                    snapshots,
                ):
                    return "drop_spawn_failed"
                return "inventory_rollback_failed"
            if self._rollback_transaction(player_id, old_data):
                return "drop_spawn_failed"
            return "drop_rollback_failed"

        if source_domain != "inventory":
            self._emit_changes(
                player_id,
                data["revision"],
                "inventory_drop",
                changes,
            )
        return "ok"

    def clear_items(
        self,
        player_id,
        item_name=None,
        aux_value=None,
        max_count=None,
    ):
        if max_count is not None and (
            not _is_int(max_count) or int(max_count) < 0
        ):
            return None
        if aux_value is not None and (
            not _is_int(aux_value) or int(aux_value) < 0
        ):
            return None
        data = self._copy_transaction_data(player_id)
        old_data = copy.deepcopy(data)
        remaining = int(max_count) if max_count is not None else None
        changes = []
        removed = 0
        for slot_id in sorted(data["slots"].keys()):
            if remaining is not None and remaining <= 0:
                break
            item = data["slots"].get(slot_id, {})
            if not item:
                continue
            if item_name is not None and _item_name(item) != item_name:
                continue
            if aux_value is not None and _item_aux(item) != int(aux_value):
                continue
            amount = _item_count(item)
            take = min(amount, remaining) if remaining is not None else amount
            if take <= 0:
                continue
            new_item = _copy_stack(item, amount - take)
            data["slots"][slot_id] = new_item
            changes.append((slot_id, item, new_item))
            removed += take
            if remaining is not None:
                remaining -= take
        if not changes:
            return 0
        if not self._save_transaction(
            player_id,
            old_data,
            data,
            "command_clear",
            tuple(changes),
        ):
            return None
        return removed

    def on_player_death(self, player_id):
        if not player_id or self._keep_inventory_enabled():
            return True
        data = self._copy_transaction_data(player_id)
        entries = []
        for slot_id in sorted(data["slots"].keys()):
            item = data["slots"].get(slot_id, {})
            if item:
                entries.append((slot_id, _copy_stack(item)))
        cursor_item = data.get("mouseCursor", {}).get("item", {})
        if cursor_item:
            entries.append(("__mouse_cursor__", _copy_stack(cursor_item)))
        if not entries:
            return True
        context = self._death_context(player_id)
        if context is None:
            return False
        dimension_id, position = context
        spawned = []
        for _slot_id, item in entries:
            entity_id = self.system.CreateEngineItemEntity(
                item,
                dimension_id,
                position,
            )
            if not entity_id or not self._set_drop_motion(entity_id):
                if entity_id:
                    spawned.append(entity_id)
                self._destroy_entities(spawned)
                return False
            spawned.append(entity_id)
        old_data = copy.deepcopy(data)
        changes = []
        for slot_id, item in entries:
            if slot_id == "__mouse_cursor__":
                data["mouseCursor"] = {}
            else:
                data["slots"][slot_id] = {}
                changes.append((slot_id, item, {}))
        if not self._save_transaction(
            player_id,
            old_data,
            data,
            "death_drop",
            tuple(changes),
        ):
            self._destroy_entities(spawned)
            return False
        return True

    def _copy_transaction_data(self, player_id):
        """Copy committed state for a transaction; only join reconciles storage."""
        data = self._get_cached_data(player_id)
        if data is None or player_id in self._pending_transactions:
            return self._empty_data()
        return copy.deepcopy(data)

    def _reconcile(self, raw):
        raw = raw if isinstance(raw, dict) else {}
        raw_slots = raw.get("slots")
        raw_slots = raw_slots if isinstance(raw_slots, dict) else {}
        revision = raw.get("revision", 0)
        revision = int(revision) if _is_int(revision) else 0
        active_ids = set(self.registry.get_slot_ids())
        slots = {}
        for slot_id, item in raw_slots.items():
            if slot_id in active_ids:
                slots[slot_id] = _copy_stack(item)
        for slot_id in sorted(active_ids):
            slots.setdefault(slot_id, {})
        data = {
            "schemaVersion": SCHEMA_VERSION,
            "revision": revision,
            "slots": slots,
            "mouseCursor": self._normalize_mouse_cursor(
                raw.get("mouseCursor"), active_ids
            ),
        }
        changed = data != raw
        return data, changed

    @staticmethod
    def _normalize_mouse_cursor(source, active_ids):
        if not isinstance(source, dict):
            return {}
        item = _copy_stack(source.get("item"))
        origin = source.get("origin")
        if not item or not isinstance(origin, dict):
            return {}
        domain = origin.get("domain")
        if domain == "inventory":
            slot = origin.get("inventorySlot")
            if not _is_int(slot) or int(slot) < 0 or int(slot) > 35:
                return {}
            normalized_origin = {
                "domain": "inventory",
                "inventorySlot": int(slot),
            }
        elif domain == "curio":
            slot_id = origin.get("slotId")
            if slot_id not in active_ids:
                normalized_origin = {"domain": "curio"}
            else:
                normalized_origin = {"domain": "curio", "slotId": slot_id}
        else:
            return {}
        return {"item": item, "origin": normalized_origin}

    def _get_raw(self, player_id):
        extra = self.comp_factory.CreateExtraData(player_id)
        if extra is None:
            return None
        try:
            value = extra.GetExtraData(DATA_KEY)
        except Exception:
            return None
        return value if isinstance(value, dict) else {}

    def _save_raw(self, player_id, data):
        if player_id in self._writing_players:
            return False
        self._writing_players.add(player_id)
        try:
            extra = self.comp_factory.CreateExtraData(player_id)
            if extra is None:
                return False
            return bool(extra.SetExtraData(
                DATA_KEY,
                _to_engine_value(data),
                True,
            ))
        except Exception:
            return False
        finally:
            self._writing_players.discard(player_id)

    def _rollback_transaction(self, player_id, old_data):
        pending = self._pending_transactions.get(player_id)
        if pending is None or pending["old_data"] != old_data:
            return False
        token = pending["token"]
        restored = False
        for _attempt in range(INVENTORY_ROLLBACK_ATTEMPTS):
            if self._save_raw(player_id, old_data):
                restored = True
                break
        if self._pending_transactions.get(player_id) is pending:
            self._pending_transactions.pop(player_id, None)
        if token is not None and self._player_tokens.get(player_id) is token:
            if restored and not self._destroyed:
                self._player_data[player_id] = copy.deepcopy(old_data)
            else:
                # A failed compensation is not a committed readable inventory.
                # Only a subsequent explicit join/load boundary can recover it.
                self._player_data.pop(player_id, None)
        return restored

    def _save_transaction(
        self,
        player_id,
        old_data,
        new_data,
        reason,
        changes,
        emit=True,
    ):
        current = self._get_cached_data(player_id)
        if (
            current is None or current != old_data
            or player_id in self._pending_transactions
            or player_id in self._writing_players
        ):
            return False
        new_data["revision"] = int(old_data.get("revision", 0)) + 1
        pending = {"token": self._player_tokens[player_id],
                   "old_data": copy.deepcopy(old_data),
                   "data": copy.deepcopy(new_data)}
        self._pending_transactions[player_id] = pending
        if not self._save_raw(player_id, new_data):
            if self._pending_transactions.get(player_id) is pending:
                self._pending_transactions.pop(player_id, None)
            return False
        if (
            self._destroyed
            or self._player_tokens.get(player_id) is not pending["token"]
        ):
            self._rollback_transaction(player_id, old_data)
            return False
        if emit:
            return self._emit_changes(
                player_id,
                new_data["revision"],
                reason,
                changes,
            )
        return True

    def _emit_changes(
        self,
        player_id,
        revision,
        reason,
        changes,
    ):
        pending = self._pending_transactions.get(player_id)
        if (
            pending is None
            or pending["data"]["revision"] != revision
        ):
            return False
        self._pending_transactions.pop(player_id, None)
        if (
            self._destroyed
            or self._player_tokens.get(player_id) is not pending["token"]
        ):
            return False
        self._player_data[player_id] = pending["data"]
        for slot_id, old_item, new_item in changes:
            self._broadcast(
                SLOT_CHANGED_EVENT,
                {
                    "playerId": player_id,
                    "slotId": slot_id,
                    "oldItem": _copy_stack(old_item),
                    "newItem": _copy_stack(new_item),
                    "revision": revision,
                    "reason": reason,
                },
            )
        if reason in (
            "inventory_transfer", "mouse_cursor_place", "curio_transfer"
        ):
            for _slot_id, old_item, new_item in changes:
                if not _should_play_equip_sound(old_item, new_item):
                    continue
                item_config = self.registry.get_snapshot().get(
                    "itemsById",
                    {},
                ).get(_item_name(new_item), {})
                sound = item_config.get("equipSound")
                self._play_equip_sound(player_id, sound)
        self.system.RefreshPlayerCurioVisuals(player_id)
        self.system.SyncPlayerChatelaineInventory(player_id, reason)
        return True

    def _play_equip_sound(self, player_id, sound):
        """One committed equip, one positional command in the wearer's dimension."""
        if (self._destroyed or self.command_comp is None or not sound
                or player_id not in self._player_tokens
                or player_id not in (serverApi.GetPlayerList() or ())):
            return False
        # Sound fields have already been normalized by the provider registry.
        volume, pitch = sound["volume"], sound["pitch"]
        if volume <= 0.0:
            return False
        radius = 16.0 * max(1.0, volume)
        command = (
            "/execute as @s at @s run playsound %s "
            "@a[r=%.3f] ~ ~ ~ %.3f %.3f 0"
        ) % (sound["sound"], radius, volume, pitch)
        # Resource identifiers are ASCII; convert only at the native API boundary.
        return bool(self.command_comp.SetCommand(str(command), player_id, False))

    def _ordered_compatible_slots(self, item):
        registry = self.registry.get_snapshot()
        result = []
        for page in registry.get("pages", ()):
            slot_ids = list(page.get("slotIds", ()))
            slot_ids.sort(key=lambda slot_id: (
                registry["slotsById"].get(slot_id, {}).get("order", 0),
                slot_id,
            ))
            for slot_id in slot_ids:
                if self.system.CanEquipCurio(slot_id, item):
                    result.append(slot_id)
        return result

    def _get_inventory_item(self, item_comp, inventory_slot):
        item_pos = serverApi.GetMinecraftEnum().ItemPosType.INVENTORY
        return _copy_stack(item_comp.GetPlayerItem(
            item_pos,
            int(inventory_slot),
            True,
        ))

    def _valid_inventory_slot(self, slot):
        return _is_int(slot) and 0 <= int(slot) <= 35

    def _keep_inventory_enabled(self):
        try:
            game = self.comp_factory.CreateGame(serverApi.GetLevelId())
            rules = game.GetGameRulesInfoServer() if game else None
        except Exception:
            return True
        if not isinstance(rules, dict):
            return True
        section = rules.get("cheat_info")
        if not isinstance(section, dict):
            return True
        return bool(section.get("keep_inventory", True))

    def _death_context(self, player_id):
        dimension = self.comp_factory.CreateDimension(player_id)
        position = self.comp_factory.CreatePos(player_id)
        if dimension is None or position is None:
            return None
        dimension_id = dimension.GetEntityDimensionId()
        foot_pos = position.GetFootPos()
        if not _is_int(dimension_id) or not isinstance(foot_pos, (list, tuple)):
            return None
        if len(foot_pos) != 3:
            return None
        return int(dimension_id), tuple(foot_pos)

    def _active_drop_context(self, player_id):
        dimension = self.comp_factory.CreateDimension(player_id)
        position = self.comp_factory.CreatePos(player_id)
        rotation = self.comp_factory.CreateRot(player_id)
        if dimension is None or position is None or rotation is None:
            return None
        try:
            dimension_id = dimension.GetEntityDimensionId()
            foot_pos = position.GetFootPos()
            rot = rotation.GetRot()
            direction = serverApi.GetDirFromRot(rot)
        except Exception:
            return None
        if not _is_int(dimension_id):
            return None
        if not isinstance(foot_pos, (list, tuple)) or len(foot_pos) != 3:
            return None
        if not isinstance(direction, (list, tuple)) or len(direction) != 3:
            return None
        try:
            position_value = (
                float(foot_pos[0]),
                float(foot_pos[1]) + ACTIVE_DROP_HEIGHT,
                float(foot_pos[2]),
            )
            direction_value = tuple(float(value) for value in direction)
        except (TypeError, ValueError):
            return None
        values = position_value + direction_value
        if any(math.isnan(value) or math.isinf(value) for value in values):
            return None
        spread_x = (
            random.random() - random.random()
        ) * ACTIVE_DROP_HORIZONTAL_SPREAD
        spread_z = (
            random.random() - random.random()
        ) * ACTIVE_DROP_HORIZONTAL_SPREAD
        motion = (
            direction_value[0] * ACTIVE_DROP_FORWARD_SPEED + spread_x,
            direction_value[1] * ACTIVE_DROP_FORWARD_SPEED,
            direction_value[2] * ACTIVE_DROP_FORWARD_SPEED + spread_z,
        )
        return int(dimension_id), position_value, motion

    def _spawn_active_drop(self, player_id, item, context):
        dimension_id, position, motion_value = context
        try:
            entity_id = self.system.CreateEngineItemEntity(
                _copy_stack(item),
                dimension_id,
                position,
            )
        except Exception:
            return None
        if not entity_id:
            return None
        # The item entity already exists from this point on.  Owner/motion are
        # best-effort presentation details and must never cause item rollback
        # (which would duplicate the successfully spawned stack).
        try:
            owner = self.comp_factory.CreateActorOwner(entity_id)
            if owner is not None:
                owner.SetEntityOwner(player_id)
        except Exception:
            pass
        try:
            motion = self.comp_factory.CreateActorMotion(entity_id)
            if motion is not None:
                motion.SetMotion(motion_value)
        except Exception:
            pass
        return entity_id

    def _set_drop_motion(self, entity_id):
        motion = self.comp_factory.CreateActorMotion(entity_id)
        if motion is None:
            return False
        radius = random.random() * DEATH_DROP_HORIZONTAL_SPEED
        angle = random.random() * math.pi * 2.0
        return motion.SetMotion((
            -math.sin(angle) * radius,
            DEATH_DROP_VERTICAL_SPEED,
            math.cos(angle) * radius,
        )) is not False

    def _destroy_entities(self, entity_ids):
        for entity_id in entity_ids:
            if entity_id:
                self.system.DestroyEntity(entity_id)

    def _broadcast(self, event_name, payload):
        return bool(self.system.BroadcastChatelaineEvent(event_name, payload))
