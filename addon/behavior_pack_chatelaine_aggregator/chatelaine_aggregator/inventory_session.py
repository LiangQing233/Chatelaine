# -*- coding: utf-8 -*-
"""Server-owned native-inventory Chatelaine page sessions."""

import copy

import mod.server.extraServerApi as serverApi

from chatelaine_aggregator.registry import (
    MAX_INVENTORY_ACTION_BYTES,
    MAX_INVENTORY_STATE_BYTES,
    serialized_size,
)


OPEN_EVENT = "ChatelaineInventoryOpenServerEvent"
ACTION_EVENT = "ChatelaineInventoryActionServerEvent"
CLOSE_EVENT = "ChatelaineInventoryCloseServerEvent"
STATE_CLIENT_EVENT = "ChatelaineInventoryStateClientEvent"


try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)


def _is_int(value):
    return isinstance(value, INTEGER_TYPES) and not isinstance(value, bool)


def _copy_item(item):
    if not isinstance(item, dict):
        return {}
    name = item.get("newItemName") or item.get("itemName")
    return copy.deepcopy(item) if name else {}


class ChatelaineInventorySessionService(object):

    def __init__(self, system, registry, equipment):
        self.system = system
        self.registry = registry
        self.equipment = equipment
        self.comp_factory = serverApi.GetEngineCompFactory()
        self.sessions = {}
        self.active_page_by_player = {}
        self.next_session_id = 1

    def open(self, args):
        player_id = args.get("__id__")
        request_id = args.get("openRequestId")
        if not player_id or not _is_int(request_id) or int(request_id) < 1:
            return False
        # Recover a cursor left by a disconnect/crash before exposing a new
        # UI session. If the inventory cannot accept it, the hidden cursor is
        # retained and included in the authoritative state below.
        self.equipment.return_mouse_cursor(player_id)
        session = {
            "sessionId": self.next_session_id,
            "openRequestId": int(request_id),
            "lastRequestId": 0,
        }
        self.next_session_id += 1
        self.sessions[player_id] = session
        self._normalize_active_page(player_id)
        self._sync(player_id, session, "opened")
        return True

    def close(self, args):
        player_id = args.get("__id__")
        session = self.sessions.get(player_id)
        if session is None:
            return False
        if args.get("sessionId") != session.get("sessionId"):
            return False
        self.sessions.pop(player_id, None)
        self.equipment.return_mouse_cursor(player_id)
        return True

    def on_player_left(self, player_id):
        self.sessions.pop(player_id, None)
        self.active_page_by_player.pop(player_id, None)
        self.equipment.return_mouse_cursor(player_id)

    def handle_action(self, args):
        player_id = args.get("__id__")
        session = self.sessions.get(player_id)
        if session is None:
            return False
        if args.get("sessionId") != session.get("sessionId"):
            return False
        request_id = args.get("requestId")
        if not _is_int(request_id):
            return False
        request_id = int(request_id)
        if request_id <= int(session.get("lastRequestId", 0)):
            return False
        action_size = serialized_size(args)
        if (
            action_size is None
            or action_size > MAX_INVENTORY_ACTION_BYTES
        ):
            print("[Chatelaine][Network] REJECT inventory_action player=%s bytes=%s" % (
                player_id,
                action_size,
            ))
            session["lastRequestId"] = request_id
            self._sync(
                player_id,
                session,
                "action_budget_exceeded",
                request_id,
            )
            return False
        session["lastRequestId"] = request_id

        action = args.get("action")
        active_distribution = session.get("distribution")
        if (
            active_distribution is not None
            and action in ("next_page", "set_page")
        ):
            # Page-local slot coordinates cannot change underneath an active
            # cumulative distribution. The client must release/finish first.
            self._sync(
                player_id, session, "distribution_active", request_id
            )
            return False
        if action == "refresh":
            self._sync(player_id, session, "refreshed", request_id)
            return True
        if action == "next_page":
            self._advance_page(player_id)
            self._sync(player_id, session, "page_changed", request_id)
            return True
        if action == "set_page":
            if not self._set_page(player_id, args.get("pageId")):
                self._sync(player_id, session, "invalid_page", request_id)
                return False
            self._sync(player_id, session, "page_changed", request_id)
            return True
        if action not in (
            "transfer",
            "coalesce",
            "distribute",
            "cursor_pick",
            "cursor_place",
            "cursor_coalesce",
            "cursor_distribute",
            "cursor_return",
            "drop",
            "distribute_update",
            "distribute_finish",
        ):
            self._sync(player_id, session, "invalid_action", request_id)
            return False

        if self.active_page_by_player.get(player_id) is None:
            self._sync(player_id, session, "page_inactive", request_id)
            return False

        continuing_distribution = bool(
            action in ("distribute_update", "distribute_finish")
            and active_distribution is not None
            and active_distribution.get("distributionId")
            == args.get("distributionId")
        )
        if not continuing_distribution:
            expected_revision = args.get("revision")
            current = self.equipment.get_snapshot(player_id)
            if (
                not _is_int(expected_revision)
                or int(expected_revision)
                != int(current.get("revision", 0))
            ):
                self._sync(player_id, session, "stale_revision", request_id)
                return False
        if (
            active_distribution is not None
            and action not in ("distribute_update", "distribute_finish")
        ):
            self._sync(
                player_id, session, "distribution_active", request_id
            )
            return False
        self.system._chatelaineSessionActionPlayer = player_id
        try:
            if action == "transfer":
                result = self._transfer(player_id, args)
            elif action == "coalesce":
                result = self.equipment.coalesce_inventory(
                    player_id,
                    args.get("sourceInventorySlot"),
                    args.get("expectedSource"),
                )
            elif action == "distribute":
                result = self.equipment.distribute_inventory(
                    player_id,
                    args.get("sourceInventorySlot"),
                    args.get("expectedSource"),
                    args.get("heldCount"),
                    args.get("targets"),
                    args.get("mode"),
                )
            elif action == "cursor_pick":
                result = self._cursor_pick(player_id, args)
            elif action == "cursor_place":
                result = self._cursor_place(player_id, args)
            elif action == "cursor_coalesce":
                result = self.equipment.mouse_cursor_coalesce_inventory(
                    player_id,
                    args.get("expectedCursor"),
                )
            elif action == "cursor_distribute":
                result = self.equipment.mouse_cursor_distribute_inventory(
                    player_id,
                    args.get("expectedCursor"),
                    args.get("targets"),
                    args.get("mode"),
                )
            elif action == "drop":
                result = self._drop(player_id, args)
            elif action == "distribute_update":
                result, next_distribution = (
                    self.equipment.stream_distribution_update(
                        player_id,
                        active_distribution,
                        args.get("distributionId"),
                        bool(args.get("cursorOwned")),
                        args.get("sourceInventorySlot"),
                        args.get("expectedSource"),
                        args.get("heldCount"),
                        args.get("targets"),
                        args.get("mode"),
                    )
                )
                if result == "ok":
                    session["distribution"] = next_distribution
            elif action == "distribute_finish":
                if not continuing_distribution:
                    result = "distribution_changed"
                else:
                    session.pop("distribution", None)
                    result = "ok"
            else:
                result = self.equipment.return_mouse_cursor(player_id)
        finally:
            self.system._chatelaineSessionActionPlayer = None
        self._sync(player_id, session, result, request_id)
        return result == "ok"

    def _cursor_pick(self, player_id, args):
        domain = args.get("sourceDomain")
        take_count = args.get("takeCount")
        if domain == "inventory":
            return self.equipment.mouse_cursor_pick_inventory(
                player_id,
                args.get("sourceInventorySlot"),
                take_count,
                args.get("expectedSource"),
            )
        if domain == "curio":
            slot_id = args.get("sourceSlotId")
            if slot_id not in self._active_page_slot_ids(player_id):
                return "source_slot_not_on_page"
            return self.equipment.mouse_cursor_pick_curio(
                player_id,
                slot_id,
                take_count,
                args.get("expectedSource"),
            )
        return "invalid_source_domain"

    def _cursor_place(self, player_id, args):
        domain = args.get("targetDomain")
        take_count = args.get("takeCount")
        if domain == "inventory":
            return self.equipment.mouse_cursor_place_inventory(
                player_id,
                args.get("targetInventorySlot"),
                take_count,
                args.get("expectedCursor"),
                args.get("expectedTarget"),
            )
        if domain == "curio":
            slot_id = args.get("targetSlotId")
            if slot_id not in self._active_page_slot_ids(player_id):
                return "target_slot_not_on_page"
            return self.equipment.mouse_cursor_place_curio(
                player_id,
                slot_id,
                take_count,
                args.get("expectedCursor"),
                args.get("expectedTarget"),
            )
        return "invalid_target_domain"

    def _drop(self, player_id, args):
        domain = args.get("sourceDomain")
        if domain == "inventory":
            source_value = args.get("sourceInventorySlot")
        elif domain == "curio":
            source_value = args.get("sourceSlotId")
            if source_value not in self._active_page_slot_ids(player_id):
                return "source_slot_not_on_page"
        elif domain == "cursor":
            source_value = None
        else:
            return "invalid_source_domain"
        return self.equipment.drop_inventory_selection(
            player_id,
            domain,
            source_value,
            args.get("takeCount"),
            args.get("expectedSource"),
        )

    def sync_open_session(self, player_id, result="external_change"):
        session = self.sessions.get(player_id)
        if session is not None:
            self._sync(player_id, session, result)

    def reconcile_pages(self):
        for player_id in tuple(self.active_page_by_player.keys()):
            self._normalize_active_page(player_id)
            self.sync_open_session(player_id, "registry_changed")

    def _transfer(self, player_id, args):
        source_domain = args.get("sourceDomain")
        target_domain = args.get("targetDomain")
        take_count = args.get("takeCount")
        if not _is_int(take_count) or int(take_count) < 1:
            return "invalid_take_count"
        if source_domain not in ("inventory", "curio"):
            return "invalid_source_domain"
        if target_domain not in ("inventory", "curio"):
            return "invalid_target_domain"
        if source_domain == target_domain:
            source_value = (
                args.get("sourceInventorySlot")
                if source_domain == "inventory"
                else args.get("sourceSlotId")
            )
            target_value = (
                args.get("targetInventorySlot")
                if target_domain == "inventory"
                else args.get("targetSlotId")
            )
            if source_value == target_value:
                return "same_slot"

        page_slot_ids = self._active_page_slot_ids(player_id)
        source_slot_id = args.get("sourceSlotId")
        target_slot_id = args.get("targetSlotId")
        if source_domain == "curio" and source_slot_id not in page_slot_ids:
            return "source_slot_not_on_page"
        if target_domain == "curio" and target_slot_id not in page_slot_ids:
            return "target_slot_not_on_page"

        if source_domain == "inventory" and target_domain == "inventory":
            return self.equipment.transfer_inventory_to_inventory(
                player_id,
                args.get("sourceInventorySlot"),
                args.get("targetInventorySlot"),
                int(take_count),
                args.get("expectedSource"),
                args.get("expectedTarget"),
            )
        if source_domain == "inventory" and target_domain == "curio":
            return self.equipment.transfer_inventory_to_curio(
                player_id,
                args.get("sourceInventorySlot"),
                target_slot_id,
                int(take_count),
                expected_source=args.get("expectedSource"),
                expected_target=args.get("expectedTarget"),
            )
        if source_domain == "curio" and target_domain == "inventory":
            return self.equipment.transfer_curio_to_inventory(
                player_id,
                source_slot_id,
                args.get("targetInventorySlot"),
                int(take_count),
                expected_source=args.get("expectedSource"),
                expected_target=args.get("expectedTarget"),
            )
        if source_domain == "curio" and target_domain == "curio":
            return self.equipment.transfer_curio_to_curio(
                player_id,
                source_slot_id,
                target_slot_id,
                int(take_count),
                expected_source=args.get("expectedSource"),
                expected_target=args.get("expectedTarget"),
            )
        return "invalid_domains"

    def _active_page_slot_ids(self, player_id):
        active_page_id = self.active_page_by_player.get(player_id)
        for page in self.registry.get_snapshot().get("pages", ()):
            if page.get("pageId") == active_page_id:
                return set(page.get("slotIds", ()))
        return set()

    def _advance_page(self, player_id):
        pages = self.registry.get_snapshot().get("pages", ())
        page_ids = [page["pageId"] for page in pages]
        current = self.active_page_by_player.get(player_id)
        if not page_ids:
            self.active_page_by_player[player_id] = None
        elif current not in page_ids:
            self.active_page_by_player[player_id] = page_ids[0]
        else:
            index = page_ids.index(current) + 1
            self.active_page_by_player[player_id] = (
                page_ids[index] if index < len(page_ids) else None
            )

    def _set_page(self, player_id, page_id):
        pages = self.registry.get_snapshot().get("pages", ())
        page_ids = [page["pageId"] for page in pages]
        if page_id == "__first__":
            self.active_page_by_player[player_id] = (
                page_ids[0] if page_ids else None
            )
            return True
        if page_id is None or page_id in page_ids:
            self.active_page_by_player[player_id] = page_id
            return True
        return False

    def _normalize_active_page(self, player_id):
        page_ids = set(
            page["pageId"]
            for page in self.registry.get_snapshot().get("pages", ())
        )
        current = self.active_page_by_player.get(player_id)
        if current not in page_ids:
            self.active_page_by_player[player_id] = None

    def _build_state(self, player_id, session, result, request_id=None):
        registry = self.registry.get_snapshot()
        equipment = self.equipment.get_snapshot(player_id)
        pages = registry.get("pages", ())
        active_page_id = self.active_page_by_player.get(player_id)
        active_page = next(
            (
                page for page in pages
                if page.get("pageId") == active_page_id
            ),
            None,
        )
        slots = []
        if active_page is not None:
            for slot_id in active_page.get("slotIds", ()):
                definition = registry.get("slotsById", {}).get(slot_id)
                if definition is None:
                    continue
                slots.append({
                    "slotId": slot_id,
                    "label": definition.get("label", slot_id),
                    "emptyTexture": definition.get("emptyTexture", ""),
                    "acceptedTypes": list(
                        definition.get("acceptedTypes", ())
                    ),
                    "maxStack": int(definition.get("maxStack", 1)),
                    "item": _copy_item(
                        equipment.get("slots", {}).get(slot_id)
                    ),
                })
        page_index = 0
        if active_page is not None:
            page_index = list(pages).index(active_page) + 1
        next_page_id = None
        if pages:
            if active_page is None:
                next_page_id = pages[0].get("pageId")
            elif page_index < len(pages):
                next_page_id = pages[page_index].get("pageId")
        inventory = self._inventory_snapshot(player_id)
        mouse_cursor = equipment.get("mouseCursor", {})
        return {
            "sessionId": session["sessionId"],
            "openRequestId": session["openRequestId"],
            "requestId": request_id,
            "result": result,
            "equipmentRevision": equipment.get("revision", 0),
            "registryRevision": registry.get("registryRevision", 0),
            "activePageId": active_page_id,
            "pageIndex": page_index,
            "pageCount": len(pages),
            "pageLabel": (
                active_page.get("label", "")
                if active_page is not None else ""
            ),
            "nextPageId": next_page_id,
            "layout": (
                "expanded" if len(slots) > 4 else "compact"
            ),
            "playerDollVisible": bool(
                active_page is None or len(slots) <= 4
            ),
            "slots": slots,
            "inventory": inventory,
            "cursorItem": _copy_item(mouse_cursor.get("item")),
            "cursorOrigin": copy.deepcopy(
                mouse_cursor.get("origin", {})
            ),
        }

    def _inventory_snapshot(self, player_id):
        item_comp = self.comp_factory.CreateItem(player_id)
        if item_comp is None:
            return [{} for _index in range(36)]
        item_pos = serverApi.GetMinecraftEnum().ItemPosType.INVENTORY
        return [
            _copy_item(item_comp.GetPlayerItem(item_pos, index, True))
            for index in range(36)
        ]

    def _sync(self, player_id, session, result, request_id=None):
        payload = self._build_state(
            player_id,
            session,
            result,
            request_id,
        )
        size = serialized_size(payload)
        if size is None or size > MAX_INVENTORY_STATE_BYTES:
            print("[Chatelaine][Network] LIMIT inventory_state player=%s bytes=%s" % (
                player_id,
                size,
            ))
            payload = {
                "sessionId": session["sessionId"],
                "openRequestId": session["openRequestId"],
                "requestId": request_id,
                "result": result,
                "networkError": "state_budget_exceeded",
                "networkLimited": True,
                "equipmentRevision": 0,
                "registryRevision": 0,
                "activePageId": None,
                "pageIndex": 0,
                "pageCount": 0,
                "pageLabel": "",
                "nextPageId": None,
                "layout": "compact",
                "playerDollVisible": True,
                "slots": [],
                "inventory": [],
                "cursorItem": {},
                "cursorOrigin": {},
            }
        return bool(self.system.NotifyToClient(
            player_id,
            STATE_CLIENT_EVENT,
            payload,
        ))
