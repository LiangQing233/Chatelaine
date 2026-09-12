# -*- coding: utf-8 -*-
"""Synchronous provider decisions ahead of item-use quick equip."""

import copy


QUICK_EQUIP_DECISION_EVENT = "ChatelaineQuickEquipDecisionServerEvent"

try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)

try:
    STRING_TYPES = (basestring,)
except NameError:
    STRING_TYPES = (str,)


def _item_name(item):
    if not isinstance(item, dict):
        return ""
    return item.get("newItemName") or item.get("itemName") or ""


class QuickEquipDecisionService(object):
    """Collect every opted-in provider decision during the native event."""

    def __init__(self, system, registry):
        self.system = system
        self.registry = registry
        self._next_request_id = 1
        self._active = {}

    def request(self, player_id, item_dict):
        item_id = _item_name(item_dict)
        item_config = self.registry.get_snapshot().get(
            "itemsById",
            {},
        ).get(item_id, {})
        required = tuple(
            item_config.get("quickEquipDecisionSources", ())
        )
        if not required:
            return True
        request_id = self._next_request_id
        self._next_request_id += 1
        context = {
            "playerId": player_id,
            "itemId": item_id,
            "required": set(required),
            "decisions": {},
        }
        self._active[request_id] = context
        try:
            delivered = self.system.BroadcastChatelaineEvent(
                QUICK_EQUIP_DECISION_EVENT,
                {
                    "requestId": request_id,
                    "playerId": player_id,
                    "itemId": item_id,
                    "itemDict": copy.deepcopy(item_dict),
                    "decisionProviders": list(required),
                },
            )
            if not delivered:
                return False
            return all(
                context["decisions"].get(provider_id) is True
                for provider_id in required
            )
        finally:
            self._active.pop(request_id, None)

    def set_decision(
        self,
        request_id,
        provider_id,
        item_id,
        allowed,
    ):
        if (
            not isinstance(request_id, INTEGER_TYPES)
            or isinstance(request_id, bool)
            or not isinstance(provider_id, STRING_TYPES)
            or not isinstance(item_id, STRING_TYPES)
            or type(allowed).__name__ != "bool"
        ):
            return False
        context = self._active.get(request_id)
        if (
            context is None
            or context["itemId"] != item_id
            or provider_id not in context["required"]
        ):
            return False
        previous = context["decisions"].get(provider_id)
        context["decisions"][provider_id] = (
            False if previous is False else allowed
        )
        return True

    def clear_player(self, player_id):
        for request_id, context in list(self._active.items()):
            if context.get("playerId") == player_id:
                self._active.pop(request_id, None)
