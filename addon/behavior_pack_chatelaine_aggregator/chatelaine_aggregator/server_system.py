# -*- coding: utf-8 -*-
"""Official Chatelaine server System and cross-mod public API."""

import mod.server.extraServerApi as serverApi

from chatelaine_aggregator.equipment import (
    ChatelaineEquipmentService,
    parse_clear_command_args,
)
from chatelaine_aggregator.inventory_session import (
    ACTION_EVENT,
    CLOSE_EVENT,
    OPEN_EVENT,
    ChatelaineInventorySessionService,
)
from chatelaine_aggregator.registry import (
    CONTRACT_NAME,
    CONTRACT_VERSION,
    ChatelaineRegistry,
)
from chatelaine_aggregator.quick_equip_policy import (
    QuickEquipDecisionService,
)
from chatelaine_aggregator.visuals import ChatelaineVisualService
from chatelaine_aggregator.entity_equipment import EntityEquipmentService
from chatelaine_aggregator.entity_visuals import EntityVisualService, REQUEST_EVENT as ENTITY_VISUAL_REQUEST_EVENT


ServerSystem = serverApi.GetServerSystemCls()
VISUAL_SYNC_REQUEST_SERVER_EVENT = "ChatelaineVisualSyncRequestServerEvent"


def _item_name(item_or_name):
    if isinstance(item_or_name, dict):
        return (
            item_or_name.get("newItemName")
            or item_or_name.get("itemName")
            or ""
        )
    try:
        return item_or_name if isinstance(item_or_name, basestring) else ""
    except NameError:
        return item_or_name if isinstance(item_or_name, str) else ""


class ChatelaineServerSystem(ServerSystem):
    _destroyed = False

    CONTRACT_NAME = CONTRACT_NAME
    CONTRACT_VERSION = CONTRACT_VERSION

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)
        self._destroyed = False
        self._serverTick = 0
        self._finalizeAfterTick = None
        self._visualSlotEnabled = {}
        self._visualRevision = {}
        self._chatelaineSessionActionPlayer = None
        self._quickEquipPressGate = None
        self._eventDeliveryAttempts = 0
        self._eventDeliveryFailures = {}
        self._itemComponent = self._create_level_item_component()
        self._registry = ChatelaineRegistry(self._item_exists)
        self._equipment = ChatelaineEquipmentService(self, self._registry)
        self._entityEquipment = EntityEquipmentService(self, self._registry, self._on_entity_equipment_visual_changed)
        self._entityVisuals = EntityVisualService(self, self._registry, self._entityEquipment)
        self._quickEquipPolicy = QuickEquipDecisionService(
            self,
            self._registry,
        )
        self._visuals = ChatelaineVisualService(
            self,
            self._registry,
            self._equipment,
        )
        self._inventorySessions = ChatelaineInventorySessionService(
            self,
            self._registry,
            self._equipment,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "LoadServerAddonScriptsAfter",
            self,
            self.OnAllServerAddonsLoaded,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "OnScriptTickServer",
            self,
            self.OnScriptTickServer,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "AddServerPlayerEvent",
            self,
            self.OnAddServerPlayer,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "DelServerPlayerEvent",
            self,
            self.OnDelServerPlayer,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "PlayerDieEvent",
            self,
            self.OnPlayerDie,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "ServerItemTryUseEvent",
            self,
            self.OnServerItemTryUse,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "CustomCommandTriggerServerEvent",
            self,
            self.OnCustomCommand,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "OnCarriedNewItemChangedServerEvent",
            self,
            self.OnNativeMainhandChanged,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "OnOffhandItemChangedServerEvent",
            self,
            self.OnNativeOffhandChanged,
        )
        self.ListenForEvent(
            serverApi.GetEngineNamespace(),
            serverApi.GetEngineSystemName(),
            "OnNewArmorExchangeServerEvent",
            self,
            self.OnNativeArmorChanged,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineClientSystem",
            VISUAL_SYNC_REQUEST_SERVER_EVENT,
            self,
            self.OnVisualSyncRequest,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineClientSystem",
            OPEN_EVENT,
            self,
            self.OnChatelaineInventoryOpen,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineClientSystem",
            ACTION_EVENT,
            self,
            self.OnChatelaineInventoryAction,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineClientSystem",
            CLOSE_EVENT,
            self,
            self.OnChatelaineInventoryClose,
        )
        for event_name, callback in (
            ("AddEntityServerEvent", self.OnEntityAdded),
            ("EntityLoadScriptEvent", self.OnEntityLoaded),
            ("EntityRemoveEvent", self.OnEntityRemoved),
            ("MobDieEvent", self.OnEntityVisualDied),
            ("DimensionChangeServerEvent", self.OnEntityVisualViewerDimension),
        ):
            self.ListenForEvent(serverApi.GetEngineNamespace(),
                                serverApi.GetEngineSystemName(),
                                event_name, self, callback)
        self.ListenForEvent("chatelaine_api", "ChatelaineClientSystem", ENTITY_VISUAL_REQUEST_EVENT,
                            self, self.OnEntityVisualRequest)
        print "[Chatelaine][Core] READY contract=%s version=%s" % (
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
        )

    def OnAllServerAddonsLoaded(self, args=None):
        if self._destroyed:
            return
        # This event runs after every behavior-pack System exists. Chatelaine may
        # receive it before provider callbacks in the same dispatch, so freeze
        # on the following tick; provider registrations merely refresh that
        # same deadline. A provider-less install follows the identical path.
        self._finalizeAfterTick = self._serverTick + 1

    def RegisterContribution(
        self,
        contractName,
        contractVersion,
        providerId,
        payload,
    ):
        if self._destroyed:
            return {"accepted": False, "reason": "system_destroyed"}
        result = self._registry.register(
            contractName,
            contractVersion,
            providerId,
            payload,
        )
        if result.get("accepted"):
            self._finalizeAfterTick = self._serverTick + 1
            print "[Chatelaine][Core] REGISTER provider=%s idempotent=%s" % (
                providerId,
                result.get("idempotent", False),
            )
        else:
            print "[Chatelaine][Core] REJECT provider=%s reason=%s" % (
                providerId,
                result.get("reason", "unknown"),
            )
        return result

    def UnregisterContribution(self, providerId):
        if self._destroyed:
            return False
        result = self._registry.unregister(providerId)
        if result:
            self._finalizeAfterTick = self._serverTick + 1
        return result

    def GetChatelaineRegistrySnapshot(self):
        if self._destroyed:
            return {}
        return self._registry.get_snapshot()

    def GetRegistryStatus(self):
        if self._destroyed:
            return {}
        return self._registry.get_status()

    def GetContributions(self):
        if self._destroyed:
            return {}
        return self._registry.get_contributions()

    def GetEventDeliveryStatus(self):
        if self._destroyed:
            return {}
        return {
            "attempts": int(self._eventDeliveryAttempts),
            "failureCount": sum(
                entry.get("count", 0)
                for entry in self._eventDeliveryFailures.values()
            ),
            "failuresByEvent": dict(
                (event_name, dict(entry))
                for event_name, entry in self._eventDeliveryFailures.items()
            ),
        }

    def BroadcastChatelaineEvent(self, eventName, payload):
        if self._destroyed:
            return False
        self._eventDeliveryAttempts += 1
        try:
            result = self.BroadcastEvent(eventName, payload)
            if result is False:
                raise RuntimeError("BroadcastEvent returned False")
            return True
        except Exception as error:
            entry = self._eventDeliveryFailures.setdefault(eventName, {
                "count": 0,
                "lastErrorType": "",
                "lastError": "",
            })
            entry["count"] += 1
            entry["lastErrorType"] = type(error).__name__
            entry["lastError"] = repr(error)[:160]
            count = entry["count"]
            if count <= 3 or (count & (count - 1)) == 0:
                print "[Chatelaine][Event] DELIVERY_FAILED event=%s count=%s error=%s:%s" % (
                    eventName,
                    count,
                    entry["lastErrorType"],
                    entry["lastError"],
                )
            return False

    def CanEquipCurio(self, slotId, itemDictOrItemId):
        if self._destroyed:
            return False
        snapshot = self._registry.get_snapshot()
        slot = snapshot["slotsById"].get(slotId)
        item_id = _item_name(itemDictOrItemId)
        item_types = snapshot["itemTypesByItemId"].get(item_id)
        if slot is None or not item_types:
            return False
        accepted = set(slot.get("acceptedTypes", ()))
        return any(type_id in accepted for type_id in item_types)

    def GetCurioSlotCapacity(self, slotId, itemDictOrItemId):
        if self._destroyed:
            return 0
        if not self.CanEquipCurio(slotId, itemDictOrItemId):
            return 0
        snapshot = self._registry.get_snapshot()
        slot_limit = int(
            snapshot["slotsById"][slotId].get("maxStack", 1)
        )
        native_limit = self._native_max_stack(itemDictOrItemId)
        return max(1, min(slot_limit, native_limit))

    def GetNativeItemMaxStack(self, itemDictOrItemId):
        if self._destroyed:
            return 0
        return self._native_max_stack(itemDictOrItemId)

    def GetPlayerChatelaineSnapshot(self, playerId):
        if self._destroyed:
            return {}
        return self._equipment.get_snapshot(playerId)

    def InitializeEntityChatelaine(self, entityId, slotIds):
        if self._destroyed:
            return False
        """Explicit server-owned first equipment initialization, or restore."""
        return self._entityEquipment.adopt(entityId, slotIds)

    def _on_entity_equipment_visual_changed(self, entity_id, reason):
        if not self._destroyed:
            self._entityVisuals.change(entity_id, reason)

    def SetEntityCurioSlotVisualEnabled(self, entityId, slotId, enabled):
        if self._destroyed:
            return False
        if not isinstance(enabled, bool):
            return False
        return self._entityVisuals.set_enabled(entityId, slotId, enabled)

    def ResetEntityCurioSlotVisualEnabled(self, entityId, slotId):
        if self._destroyed:
            return False
        return self._entityVisuals.set_enabled(entityId, slotId, None)

    def GetEntityCurioSlotVisualState(self, entityId, slotId):
        if self._destroyed:
            return {}
        return self._entityVisuals.get_slot(entityId, slotId)

    def RefreshEntityCurioVisuals(self, entityId):
        if self._destroyed:
            return False
        return self._entityVisuals.refresh(entityId)

    def OnEntityVisualRequest(self, args):
        if self._destroyed:
            return False
        return self._entityVisuals.request(args)

    def OnEntityVisualDied(self, args):
        if self._destroyed:
            return False
        self._entityVisuals.remove(args.get("id"))

    def OnEntityVisualViewerDimension(self, args):
        if self._destroyed:
            return False
        self._entityVisuals.clear_player(args.get("playerId"))

    def GetEntityChatelaineSnapshot(self, entityId):
        if self._destroyed:
            return {}
        return self._entityEquipment.snapshot(entityId)

    def GetEntityCurioItem(self, entityId, slotId):
        if self._destroyed:
            return {}
        return self._entityEquipment.item(entityId, slotId)

    def ConfigureEntityChatelaineSlots(self, entityId, slotIds, expectedRevision):
        if self._destroyed:
            return {}
        return self._entityEquipment.configure(entityId, slotIds, expectedRevision)

    def ExchangeEntityCurioItem(self, entityId, slotId, itemDict, expectedRevision):
        if self._destroyed:
            return {}
        """Trusted item handoff: caller supplies new item and owns returned old item."""
        return self._entityEquipment.exchange(entityId, slotId, itemDict, expectedRevision)

    def ReplaceEntityCurioItemData(self, entityId, slotId, itemDict, expectedRevision):
        if self._destroyed:
            return {}
        return self._entityEquipment.exchange(entityId, slotId, itemDict, expectedRevision, True)

    def OnEntityAdded(self, args):
        if self._destroyed:
            return
        self._entityEquipment.adopt(args.get("id"))

    def OnEntityLoaded(self, args):
        if self._destroyed:
            return
        entity_id = args[0] if isinstance(args, (list, tuple)) and args else args.get("id") if isinstance(args, dict) else None
        self._entityEquipment.adopt(entity_id)

    def OnEntityRemoved(self, args):
        if self._destroyed:
            return
        self._entityEquipment.remove(args.get("id"))

    def GetPlayerChatelaineSlots(self, playerId):
        if self._destroyed:
            return {}
        return self._equipment.get_slots(playerId)

    def GetPlayerCurioItem(self, playerId, slotId):
        if self._destroyed:
            return {}
        return self._equipment.get_item(playerId, slotId)

    def ReplacePlayerCurioItemData(self, playerId, slotId, itemDict):
        if self._destroyed:
            return False
        return self._equipment.replace_item_data(
            playerId,
            slotId,
            itemDict,
        )

    def SetQuickEquipDecision(
        self,
        requestId,
        providerId,
        itemId,
        allowed,
    ):
        if self._destroyed:
            return False
        return self._quickEquipPolicy.set_decision(
            requestId,
            providerId,
            itemId,
            allowed,
        )

    def SetQuickEquipPressGate(
        self, gateId, claim, shouldCancel, markCancel, yieldClaim
    ):
        if self._destroyed:
            return False
        """Bind a host's physical-press policy without owning its input API."""
        if not gateId or not all(callable(value) for value in (
            claim, shouldCancel, markCancel, yieldClaim
        )):
            return False
        current = self._quickEquipPressGate
        if current is not None and current[0] != gateId:
            return False
        self._quickEquipPressGate = (
            gateId, claim, shouldCancel, markCancel, yieldClaim
        )
        return True

    def ClearQuickEquipPressGate(self, gateId):
        if self._destroyed:
            return False
        current = self._quickEquipPressGate
        if current is None or current[0] != gateId:
            return False
        self._quickEquipPressGate = None
        return True

    def GetPlayerCurioItemsByType(self, playerId, typeId):
        if self._destroyed:
            return []
        return self._equipment.get_items_by_type(playerId, typeId)

    def TransferInventoryToCurio(
        self,
        playerId,
        inventorySlot,
        slotId,
        takeCount,
    ):
        if self._destroyed:
            return False
        return self._equipment.transfer_inventory_to_curio(
            playerId,
            inventorySlot,
            slotId,
            takeCount,
        )

    def TransferCurioToInventory(
        self,
        playerId,
        slotId,
        inventorySlot,
        takeCount,
    ):
        if self._destroyed:
            return False
        return self._equipment.transfer_curio_to_inventory(
            playerId,
            slotId,
            inventorySlot,
            takeCount,
        )

    def TransferCurioToCurio(
        self,
        playerId,
        sourceSlotId,
        targetSlotId,
        takeCount,
    ):
        if self._destroyed:
            return False
        return self._equipment.transfer_curio_to_curio(
            playerId,
            sourceSlotId,
            targetSlotId,
            takeCount,
        )

    def ClearPlayerChatelaine(
        self,
        playerId,
        itemId=None,
        auxValue=None,
        maxCount=None,
    ):
        if self._destroyed:
            return False
        return self._equipment.clear_items(
            playerId,
            itemId,
            auxValue,
            maxCount,
        )

    def SetCurioSlotVisualEnabled(self, playerId, slotId, enabled):
        if self._destroyed:
            return False
        if (
            not playerId
            or type(enabled).__name__ != "bool"
            or slotId not in self._registry.get_snapshot()["slotsById"]
        ):
            return False
        states = self._visualSlotEnabled.setdefault(playerId, {})
        previous = states.get(slotId, True)
        states[slotId] = enabled
        if previous != enabled:
            self.RefreshPlayerCurioVisuals(playerId)
        return True

    def ResetCurioSlotVisualEnabled(self, playerId, slotId):
        if self._destroyed:
            return False
        if not playerId:
            return False
        states = self._visualSlotEnabled.get(playerId)
        previous = states.get(slotId, True) if states is not None else True
        if states is not None:
            states.pop(slotId, None)
            if not states:
                self._visualSlotEnabled.pop(playerId, None)
        if previous is not True:
            self.RefreshPlayerCurioVisuals(playerId)
        return True

    def GetCurioSlotVisualState(self, playerId, slotId):
        if self._destroyed:
            return {}
        return self._visuals.get_slot_state(playerId, slotId)

    def RefreshPlayerCurioVisuals(self, playerId, nativeOverrides=None):
        if self._destroyed:
            return False
        return self._visuals.refresh_player(playerId, nativeOverrides)

    def SyncPlayerChatelaineInventory(self, playerId, result="external_change"):
        if self._destroyed:
            return False
        if self._chatelaineSessionActionPlayer == playerId:
            return
        self._inventorySessions.sync_open_session(playerId, result)

    def OnScriptTickServer(self, args=None):
        if self._destroyed:
            return
        self._serverTick += 1
        if (
            self._finalizeAfterTick is not None
            and self._serverTick >= self._finalizeAfterTick
        ):
            self._finalizeAfterTick = None
            if self._registry.finalize():
                snapshot = self._registry.get_snapshot()
                print "[Chatelaine][Core] READY providers=%s pages=%s slots=%s items=%s revision=%s" % (
                    self._registry.get_status()["providerCount"],
                    len(snapshot["pages"]),
                    len(snapshot["slotsById"]),
                    len(snapshot["itemsById"]),
                    snapshot["registryRevision"],
                )
                self._equipment.reconcile_online_players()
                for entity_id in set(serverApi.GetEngineActor() or ()) | set(self._entityEquipment.data):
                    self._entityEquipment.adopt(entity_id)
                self._inventorySessions.reconcile_pages()
                self._broadcast_registry_ready(snapshot)
                self._visuals.broadcast_registry()
                for player_id in tuple(serverApi.GetPlayerList() or ()):
                    self.RefreshPlayerCurioVisuals(player_id)
            else:
                print "[Chatelaine][Core] FINALIZE_FAILED errors=%s" % (
                    self._registry.get_status()["errors"],
                )

    def OnAddServerPlayer(self, args):
        if self._destroyed:
            return
        player_id = args.get("id")
        self._equipment.on_player_join(player_id)
        self.RefreshPlayerCurioVisuals(player_id)
        self._visuals.sync_all_to_client(player_id)

    def OnDelServerPlayer(self, args):
        if self._destroyed:
            return
        player_id = args.get("id") or args.get("playerId")
        if not player_id:
            return
        self._visualSlotEnabled.pop(player_id, None)
        self._entityVisuals.clear_player(player_id)
        self._visualRevision.pop(player_id, None)
        self._quickEquipPolicy.clear_player(player_id)
        self._visuals.clear_player(player_id)
        try:
            self._inventorySessions.on_player_left(player_id)
        finally:
            self._equipment.on_player_left(player_id)

    def OnPlayerDie(self, args):
        if self._destroyed:
            return
        self._equipment.on_player_death(args.get("id"))

    def OnServerItemTryUse(self, args):
        if self._destroyed:
            return
        if args.get("cancel"):
            return
        player_id = args.get("playerId")
        item_id = _item_name(args.get("itemDict"))
        config = self._registry.get_snapshot().get("itemsById", {}).get(
            item_id, {}
        )
        if not player_id or not config.get("equipOnUse"):
            return
        gate = self._quickEquipPressGate
        owner = "chatelaine_quick_equip"
        if gate is not None and not gate[1](player_id, owner):
            if gate[2](player_id, owner):
                args["cancel"] = True
            return
        accepted = False
        try:
            if not self._quickEquipPolicy.request(
                player_id,
                args.get("itemDict"),
            ):
                return
            # Mark takeover before the transaction's synchronous callbacks;
            # a reentrant native event may cancel, but cannot query or equip.
            if gate is not None:
                gate[3](player_id, owner)
            accepted = bool(self._equipment.quick_equip_selected_item(
                player_id,
                args.get("itemDict"),
            ))
        finally:
            if gate is not None and not accepted:
                gate[4](player_id, owner)
        if accepted:
            args["cancel"] = True

    def OnNativeMainhandChanged(self, args):
        if self._destroyed:
            return
        player_id = args.get("playerId")
        if player_id:
            self.RefreshPlayerCurioVisuals(
                player_id,
                {"mainhand": args.get("newItemDict") or {}},
            )

    def OnNativeOffhandChanged(self, args):
        if self._destroyed:
            return
        player_id = args.get("playerId")
        if player_id:
            self.RefreshPlayerCurioVisuals(
                player_id,
                {
                    "offhand": (
                        args.get("newItemDict")
                        or args.get("itemDict")
                        or {}
                    ),
                },
            )

    def OnNativeArmorChanged(self, args):
        if self._destroyed:
            return
        player_id = args.get("playerId")
        try:
            slot = int(args.get("slot", -1))
        except (TypeError, ValueError):
            return
        slot_name = {
            0: "head",
            1: "chest",
            2: "legs",
            3: "feet",
        }.get(slot)
        if player_id and slot_name:
            self.RefreshPlayerCurioVisuals(
                player_id,
                {slot_name: args.get("newArmorDict") or {}},
            )

    def OnVisualSyncRequest(self, args):
        if self._destroyed:
            return
        player_id = args.get("__id__") if isinstance(args, dict) else None
        if not player_id:
            return
        self._visuals.sync_all_to_client(player_id)

    def OnChatelaineInventoryOpen(self, args):
        if self._destroyed:
            return
        self._inventorySessions.open(args)

    def OnChatelaineInventoryAction(self, args):
        if self._destroyed:
            return
        self._inventorySessions.handle_action(args)

    def OnChatelaineInventoryClose(self, args):
        if self._destroyed:
            return
        self._inventorySessions.close(args)

    def OnCustomCommand(self, args):
        if self._destroyed:
            return
        if args.get("command") != "chatelaine_clear":
            return
        parsed = parse_clear_command_args(args.get("args", ()))
        if parsed is None:
            self._set_command_failed(
                args,
                u"垂佩清除指令参数无效；auxvalue 和 maxcount 必须为非负整数",
            )
            return
        online = set(serverApi.GetPlayerList() or ())
        processed = 0
        failed = 0
        removed = 0
        for player_id in parsed["targetIds"]:
            if player_id not in online:
                continue
            processed += 1
            result = self._equipment.clear_items(
                player_id,
                parsed["itemId"],
                parsed["auxValue"],
                parsed["maxCount"],
            )
            if result is None:
                failed += 1
            else:
                removed += int(result)
        if processed == 0:
            self._set_command_failed(args, u"没有可处理的在线目标玩家")
        elif failed:
            self._set_command_failed(
                args,
                u"部分目标玩家垂佩写入失败；已清除 %s 个物品" % removed,
            )
        else:
            args["return_msg_key"] = (
                u"已从目标玩家的全部垂佩槽清除 %s 个物品" % removed
            )

    def Destroy(self):
        self.destroy()

    def destroy(self):
        self._destroyed = True
        self._entityVisuals.destroy()
        # Detach first, before any service cleanup can fail. Repeated calls
        # remain safe and can retry detachment after an engine-side failure.
        try:
            self.UnListenAllEvents()
        except Exception as error:
            print("[Chatelaine][Lifecycle] unlisten_failed: %s" % error)
        self._finalizeAfterTick = None
        self._visualSlotEnabled.clear()
        self._visualRevision.clear()
        self._eventDeliveryFailures.clear()
        self._chatelaineSessionActionPlayer = None
        self._quickEquipPressGate = None

        self._equipment.destroy()
        self._entityEquipment.destroy()

    def _broadcast_registry_ready(self, snapshot):
        return self.BroadcastChatelaineEvent(
            "ChatelaineRegistryReadyServerEvent",
            {
                "registryRevision": snapshot["registryRevision"],
                "providerCount": self._registry.get_status()[
                    "providerCount"
                ],
            },
        )

    @staticmethod
    def _set_command_failed(args, message):
        args["return_failed"] = True
        args["return_msg_key"] = message

    def _create_level_item_component(self):
        try:
            factory = serverApi.GetEngineCompFactory()
            return factory.CreateItem(serverApi.GetLevelId())
        except Exception:
            return None

    def _item_exists(self, item_id):
        component = self._itemComponent
        getter = getattr(component, "GetItemBasicInfo", None)
        if not callable(getter):
            return False
        try:
            info = getter(item_id, 0, False)
        except Exception:
            return False
        return isinstance(info, dict) and bool(info)

    def _native_max_stack(self, item_or_name):
        item_id = _item_name(item_or_name)
        if not item_id:
            return 1
        getter = getattr(self._itemComponent, "GetItemBasicInfo", None)
        if not callable(getter):
            return 1
        try:
            info = getter(item_id, 0, False)
        except Exception:
            return 1
        if not isinstance(info, dict):
            return 1
        value = info.get("maxStackSize", info.get("max_stack_size", 1))
        try:
            value = int(value)
        except (TypeError, ValueError, OverflowError):
            return 1
        return max(1, min(64, value))
