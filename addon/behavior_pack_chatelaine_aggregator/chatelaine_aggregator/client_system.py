# -*- coding: utf-8 -*-
"""Chatelaine client bridge; UI and visuals extend this System."""

import mod.client.extraClientApi as clientApi

from chatelaine_aggregator.registry import visual_slot_query_name
from chatelaine_aggregator.entity_visual_client import EntityVisualClient


ClientSystem = clientApi.GetClientSystemCls()
VISUAL_REGISTRY_CLIENT_EVENT = "ChatelaineVisualRegistryClientEvent"
VISUAL_STATE_CLIENT_EVENT = "ChatelaineVisualStateClientEvent"
VISUAL_SYNC_REQUEST_SERVER_EVENT = "ChatelaineVisualSyncRequestServerEvent"
OPEN_EVENT = "ChatelaineInventoryOpenServerEvent"
ACTION_EVENT = "ChatelaineInventoryActionServerEvent"
CLOSE_EVENT = "ChatelaineInventoryCloseServerEvent"
STATE_CLIENT_EVENT = "ChatelaineInventoryStateClientEvent"
PLAYER_RENDER_SETUP_DELAY_SECONDS = 0.05
PLAYER_RENDER_RETRY_DELAY_SECONDS = 0.25
PLAYER_RENDER_RETRY_LIMIT = 20


try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)


def _is_int(value):
    return isinstance(value, INTEGER_TYPES) and not isinstance(value, bool)


class ChatelaineClientSystem(ClientSystem):
    _destroyed = False

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self._destroyed = False
        self._visualTimers = {}
        self.compFactory = clientApi.GetEngineCompFactory()
        self.uiAudioComp = None
        self.visualRegistry = {
            "registryRevision": 0,
            "visualsById": {},
            "itemTypesByItemId": {},
        }
        self.visualStates = {}
        self.visualPreparedByPlayer = {}
        self.visualInjectionStagesByPlayer = {}
        self.visualSetupGenerations = {}
        self.visualPrepareTickets = {}
        self.visualInjectionReady = set()
        self.visualLastFailureByPlayer = {}
        self.visualQueryRegistered = set()
        self.entityVisuals = EntityVisualClient(self)
        self.chatelaineInventoryState = {
            "sessionId": None,
            "equipmentRevision": 0,
            "activePageId": None,
            "slots": [],
            "inventory": [],
            "cursorItem": {},
            "cursorOrigin": {},
        }
        self.chatelaineInventoryStateVersion = 0
        self._nextOpenRequestId = 1
        self._nextActionRequestId = 1
        self._lastInventoryResponseRequestId = 0
        self.chatelaineInventoryAwaitingOpen = False
        self.chatelaineInventoryOpenRequestId = None
        self.chatelaineInventoryAdvanceAfterOpen = False
        self.shiftDown = False
        self.activeChatelaineInventoryProxy = None
        proxy_class = (
            "chatelaine_aggregator.inventory_proxy."
            "InventoryChatelaineScreenProxy"
        )
        manager = clientApi.GetNativeScreenManagerCls().instance()
        manager.RegisterScreenProxy(
            "crafting.inventory_screen",
            proxy_class,
        )
        manager.RegisterScreenProxy(
            "crafting_pocket.inventory_screen_pocket",
            proxy_class,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineServerSystem",
            VISUAL_REGISTRY_CLIENT_EVENT,
            self,
            self.OnVisualRegistry,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineServerSystem",
            VISUAL_STATE_CLIENT_EVENT,
            self,
            self.OnVisualState,
        )
        self.ListenForEvent(
            "chatelaine_api",
            "ChatelaineServerSystem",
            STATE_CLIENT_EVENT,
            self,
            self.OnChatelaineInventoryState,
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            "UiInitFinished",
            self,
            self.OnUiInitFinished,
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            "OnKeyPressInGame",
            self,
            self.OnKeyPressInGame,
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            "InventoryItemChangedClientEvent",
            self,
            self.OnInventoryItemChanged,
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            "AddPlayerCreatedClientEvent",
            self,
            self.OnAddPlayerCreated,
        )
        self.ListenForEvent(
            clientApi.GetEngineNamespace(),
            clientApi.GetEngineSystemName(),
            "RemovePlayerAOIClientEvent",
            self,
            self.OnRemovePlayerAoi,
        )

        for event_name, callback in (
                ("ChatelaineEntityVisualRegistryClientEvent", self.OnEntityVisualRegistry),
                ("ChatelaineEntityVisualStateClientEvent", self.OnEntityVisualState)):
            self.ListenForEvent("chatelaine_api", "ChatelaineServerSystem", event_name, self, callback)
        for event_name, callback in (
                ("AddEntityClientEvent", self.OnEntityVisualAdded),
                ("RemoveEntityClientEvent", self.OnEntityVisualRemoved),
                ("OnLocalPlayerStopLoading", self.OnEntityVisualReady),
                ("DimensionChangeFinishClientEvent", self.OnEntityVisualDimension)):
            self.ListenForEvent(clientApi.GetEngineNamespace(), clientApi.GetEngineSystemName(),
                                event_name, self, callback)

    def OnEntityVisualRegistry(self, args):
        if self._destroyed:
            return False
        self.entityVisuals.on_registry(args)

    def OnEntityVisualState(self, args):
        if self._destroyed:
            return False
        self.entityVisuals.on_state(args)

    def OnEntityVisualAdded(self, args):
        if self._destroyed:
            return False
        self.entityVisuals.on_add(args)

    def OnEntityVisualRemoved(self, args):
        if self._destroyed:
            return False
        self.entityVisuals.on_remove(args)

    def OnEntityVisualReady(self, args=None):
        if self._destroyed:
            return False
        self.entityVisuals.ready()

    def OnEntityVisualDimension(self, args):
        if self._destroyed:
            return False
        if args.get("playerId") == clientApi.GetLocalPlayerId():
            self.entityVisuals.dimension_changed()

    def SwingLocalPlayer(self):
        if self._destroyed:
            return False
        """Play the local hand swing used by an authoritative UI drop."""
        player_id = clientApi.GetLocalPlayerId()
        if not player_id:
            return False
        player = self.compFactory.CreatePlayer(player_id)
        if player is None:
            return False
        player.Swing()
        return True

    def OnInventoryItemChanged(self, _args):
        if self._destroyed:
            return False
        proxy = self.activeChatelaineInventoryProxy
        if proxy is not None:
            proxy.MarkInventoryDirty()

    def OnKeyPressInGame(self, args):
        if self._destroyed:
            return False
        if not isinstance(args, dict):
            return
        try:
            key = int(args.get("key"))
        except (TypeError, ValueError):
            return
        value = args.get("isDown")
        is_down = value in (True, 1, "1", "true", "True")
        if key == 16:
            self.shiftDown = is_down

    def IsShiftDown(self):
        if self._destroyed:
            return False
        return bool(self.shiftDown)

    def OnUiInitFinished(self, _args=None):
        if self._destroyed:
            return False
        """Recover local render injection and request any missed snapshots."""
        self.entityVisuals.ready()
        player_id = clientApi.GetLocalPlayerId()
        if not player_id:
            return
        if player_id in self.visualInjectionReady:
            # Match the mature source lifecycle: only AddPlayerCreated resets
            # and injects ActorRender resources. UiInitFinished may repeat for
            # the same live actor, so it can only reapply queries and request
            # authoritative data.
            self._schedule_visual_prepare(player_id)
        self.NotifyToServer(VISUAL_SYNC_REQUEST_SERVER_EVENT, {})

    def OnVisualRegistry(self, args):
        if self._destroyed:
            return False
        if not isinstance(args, dict):
            return
        revision = args.get("registryRevision", 0)
        if revision < self.visualRegistry.get("registryRevision", 0):
            return
        self.visualRegistry = {
            "registryRevision": revision,
            "visualsById": args.get("visualsById", {}),
            "itemTypesByItemId": args.get("itemTypesByItemId", {}),
        }
        print("[Chatelaine][Visual] REGISTRY revision=%s visuals=%s" % (
            revision,
            len(self.visualRegistry["visualsById"]),
        ))
        for player_id in tuple(self.visualPreparedByPlayer.keys()):
            self._schedule_visual_prepare(player_id)

    def OnVisualState(self, args):
        if self._destroyed:
            return False
        if not isinstance(args, dict):
            return
        player_id = args.get("playerId")
        if not player_id:
            return
        previous = self.visualStates.get(player_id, {})
        if args.get("visualRevision", 0) < previous.get(
            "visualRevision",
            0,
        ):
            return
        if args == previous:
            return
        self.visualStates[player_id] = args
        self._schedule_visual_prepare(player_id)

    def OnAddPlayerCreated(self, args):
        if self._destroyed:
            return False
        player_id = args.get("playerId") if isinstance(args, dict) else None
        if not player_id:
            return
        generation = self.visualSetupGenerations.get(player_id, 0) + 1
        self.visualSetupGenerations[player_id] = generation
        self.visualPreparedByPlayer[player_id] = set()
        self.visualInjectionStagesByPlayer[player_id] = {}
        self.visualInjectionReady.discard(player_id)
        self.visualLastFailureByPlayer.pop(player_id, None)
        game = self.compFactory.CreateGame(clientApi.GetLevelId())
        if game is not None:
            self._add_visual_timer(game, player_id, "setup",
                PLAYER_RENDER_SETUP_DELAY_SECONDS,
                self._finish_player_render_setup,
                player_id,
                generation,
            )
        if player_id == clientApi.GetLocalPlayerId():
            self.NotifyToServer(VISUAL_SYNC_REQUEST_SERVER_EVENT, {})

    def OnRemovePlayerAoi(self, args):
        if self._destroyed:
            return False
        player_id = None
        if isinstance(args, dict):
            player_id = args.get("playerId") or args.get("entityId")
        if player_id:
            self.visualSetupGenerations[player_id] = (
                self.visualSetupGenerations.get(player_id, 0) + 1
            )
            self.visualPreparedByPlayer.pop(player_id, None)
            self.visualInjectionStagesByPlayer.pop(player_id, None)
            self.visualPrepareTickets.pop(player_id, None)
            self.visualInjectionReady.discard(player_id)
            self.visualLastFailureByPlayer.pop(player_id, None)
            self.visualStates.pop(player_id, None)

    def _finish_player_render_setup(self, player_id, generation):
        if self._destroyed:
            return False
        if self.visualSetupGenerations.get(player_id) != generation:
            return
        self._visualTimers.pop((player_id, "setup"), None)
        self.visualInjectionReady.add(player_id)
        self._schedule_visual_prepare(player_id)

    def _schedule_visual_prepare(self, player_id, delay=0.0):
        if self._destroyed:
            return False
        if not player_id or player_id not in self.visualInjectionReady:
            return False
        generation = self.visualSetupGenerations.get(player_id)
        if generation is None:
            return False
        ticket = self.visualPrepareTickets.get(player_id, 0) + 1
        self.visualPrepareTickets[player_id] = ticket
        if delay <= 0.0:
            self._run_visual_prepare(player_id, generation, ticket, 0)
            return True
        game = self.compFactory.CreateGame(clientApi.GetLevelId())
        if game is None:
            return False
        self._add_visual_timer(game, player_id, "prepare",
            delay,
            self._run_visual_prepare,
            player_id,
            generation,
            ticket,
            0,
        )
        return True

    def _run_visual_prepare(
        self,
        player_id,
        generation,
        ticket,
        attempt,
    ):
        if self._destroyed:
            return False
        if (
            self.visualSetupGenerations.get(player_id) != generation
            or self.visualPrepareTickets.get(player_id) != ticket
            or player_id not in self.visualInjectionReady
        ):
            return
        self._visualTimers.pop((player_id, "prepare"), None)
        if self._prepare_player_visuals(player_id):
            return
        if attempt >= PLAYER_RENDER_RETRY_LIMIT:
            print("[Chatelaine][Visual] PREPARE exhausted player=%s" % player_id)
            return
        game = self.compFactory.CreateGame(clientApi.GetLevelId())
        if game is not None:
            self._add_visual_timer(game, player_id, "prepare",
                PLAYER_RENDER_RETRY_DELAY_SECONDS,
                self._run_visual_prepare,
                player_id,
                generation,
                ticket,
                attempt + 1,
            )

    def _add_visual_timer(self, game, player_id, kind, delay, callback, *args):
        if self._destroyed:
            return
        key = (player_id, kind)
        previous = self._visualTimers.pop(key, None)
        if previous is not None:
            previous[0].CancelTimer(previous[1])
        self._visualTimers[key] = (game, game.AddTimer(delay, callback, *args))

    def Destroy(self):
        self.destroy()

    def destroy(self):
        self._destroyed = True
        self.entityVisuals.destroy()
        try:
            self.UnListenAllEvents()
        except Exception as error:
            print("[Chatelaine][Lifecycle] unlisten_failed: %s" % error)
        self.visualSetupGenerations.clear()
        self.visualPrepareTickets.clear()
        self.visualInjectionReady.clear()
        timers = list(self._visualTimers.values())
        self._visualTimers.clear()
        for game, timer in timers:
            try:
                game.CancelTimer(timer)
            except Exception as error:
                print("[Chatelaine][Lifecycle] cancel_visual_timer_failed: %s" % error)
        proxy = self.activeChatelaineInventoryProxy
        self.activeChatelaineInventoryProxy = None
        if proxy is not None and proxy.client_system is self:
            proxy._destroyed = True
            proxy.client_system = None
        self._clear_curio_inventory_cache()
        self.shiftDown = False
        self.visualStates.clear()
        self.visualPreparedByPlayer.clear()
        self.visualInjectionStagesByPlayer.clear()
        self.visualLastFailureByPlayer.clear()
        self.visualQueryRegistered.clear()
        self.uiAudioComp = None
        self.compFactory = None

    def _set_visual_failure(self, player_id, visual_id, stage):
        failure = (visual_id, stage)
        if self.visualLastFailureByPlayer.get(player_id) != failure:
            self.visualLastFailureByPlayer[player_id] = failure
            print("[Chatelaine][Visual] PREPARE failed player=%s visual=%s stage=%s" % (
                player_id,
                visual_id,
                stage,
            ))
        return False

    @staticmethod
    def _visual_query_name(visual_id, slot_id):
        return visual_slot_query_name(visual_id, slot_id)

    def _prepare_player_visuals(self, player_id):
        if self._destroyed:
            return False
        if not player_id or player_id not in self.visualInjectionReady:
            return False
        prepared = self.visualPreparedByPlayer.setdefault(player_id, set())
        stages_by_visual = self.visualInjectionStagesByPlayer.setdefault(
            player_id,
            {},
        )
        visuals = self.visualRegistry.get("visualsById", {})
        pending = [
            (visual_id, visual)
            for visual_id, visual in visuals.items()
            if visual_id not in prepared
        ]
        if not pending:
            self._apply_visual_state(player_id)
            return True
        registry = self.compFactory.CreateQueryVariable(
            clientApi.GetLevelId()
        )
        render = self.compFactory.CreateActorRender(player_id)
        if registry is None or render is None:
            return False
        ready_to_rebuild = []
        for visual_id, visual in pending:
            stages = stages_by_visual.setdefault(visual_id, set())
            slot_ids = list(visual.get("slotIds", ()))
            query_names = []
            for slot_id in slot_ids:
                query_name = self._visual_query_name(visual_id, slot_id)
                query_names.append(query_name)
                if query_name in self.visualQueryRegistered:
                    continue
                if not registry.Register(query_name, 0.0):
                    return self._set_visual_failure(
                        player_id,
                        visual_id,
                        "query:%s" % slot_id,
                    )
                self.visualQueryRegistered.add(query_name)
            condition = " || ".join(
                "%s > 0.5" % query_name
                for query_name in query_names
            ) or "0.0"
            if len(query_names) > 1:
                condition = "(%s)" % condition
            first_person_config = visual.get("firstPerson", False)
            animate_condition = (
                "%s && !variable.is_first_person" % condition
            )
            geometry = visual.get("geometry", {})
            if "geometry" not in stages:
                if not render.AddPlayerGeometry(
                    geometry.get("key"), geometry.get("resource")
                ):
                    return self._set_visual_failure(
                        player_id, visual_id, "geometry"
                    )
                stages.add("geometry")
            for texture in visual.get("textures", ()):
                stage = "texture:%s" % texture.get("key")
                if stage in stages:
                    continue
                if not render.AddPlayerTexture(
                    texture.get("key"), texture.get("resource")
                ):
                    return self._set_visual_failure(
                        player_id, visual_id, stage
                    )
                stages.add(stage)
            for material in visual.get("materials", ()):
                stage = "material:%s" % material.get("key")
                if stage in stages:
                    continue
                if not render.AddPlayerRenderMaterial(
                    material.get("key"), material.get("resource")
                ):
                    return self._set_visual_failure(
                        player_id, visual_id, stage
                    )
                stages.add(stage)
            for animation in visual.get("animations", ()):
                key = animation.get("key")
                add_stage = "animation:%s" % key
                state_stage = "animation_state:%s" % key
                if add_stage not in stages:
                    if not render.AddPlayerAnimation(
                        key, animation.get("resource")
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, add_stage
                        )
                    stages.add(add_stage)
                if state_stage not in stages:
                    if not render.AddPlayerAnimationIntoState(
                        animation.get("state"),
                        animation.get("layer"),
                        key,
                        animate_condition,
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, state_stage
                        )
                    stages.add(state_stage)
            for controller in visual.get("animationControllers", ()):
                key = controller.get("key")
                add_stage = "animation_controller:%s" % key
                if add_stage not in stages:
                    if not render.AddPlayerAnimationController(
                        key, controller.get("resource")
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, add_stage
                        )
                    stages.add(add_stage)
                attach = controller.get("attach", {})
                mode = attach.get("mode")
                attach_stage = "animation_controller_%s:%s" % (mode, key)
                if attach_stage in stages:
                    continue
                if mode == "state":
                    attached = render.AddPlayerAnimationIntoState(
                        attach.get("controller"),
                        attach.get("state"),
                        key,
                        animate_condition,
                    )
                else:
                    attached = render.AddPlayerScriptAnimate(
                        key,
                        animate_condition,
                        bool(attach.get("autoReplace", False)),
                    )
                if not attached:
                    return self._set_visual_failure(
                        player_id, visual_id, attach_stage
                    )
                stages.add(attach_stage)
            for slot_id, query_name in zip(slot_ids, query_names):
                render_stage = "render_controller:%s" % slot_id
                if render_stage in stages:
                    continue
                if not render.AddPlayerRenderController(
                    visual.get("renderController"),
                    "%s > 0.5 && !variable.is_first_person"
                    % query_name,
                ):
                    return self._set_visual_failure(
                        player_id,
                        visual_id,
                        render_stage,
                    )
                stages.add(render_stage)
            if isinstance(first_person_config, dict):
                first_condition = (
                    "%s && variable.is_first_person" % condition
                )
                first_geometry = first_person_config.get("geometry", {})
                first_stage = "first_person:geometry"
                if first_stage not in stages:
                    if not render.AddPlayerGeometry(
                        first_geometry.get("key"),
                        first_geometry.get("resource"),
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, first_stage
                        )
                    stages.add(first_stage)
                for texture in first_person_config.get("textures", ()):
                    first_stage = "first_person:texture:%s" % (
                        texture.get("key")
                    )
                    if first_stage in stages:
                        continue
                    if not render.AddPlayerTexture(
                        texture.get("key"), texture.get("resource")
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, first_stage
                        )
                    stages.add(first_stage)
                for material in first_person_config.get("materials", ()):
                    first_stage = "first_person:material:%s" % (
                        material.get("key")
                    )
                    if first_stage in stages:
                        continue
                    if not render.AddPlayerRenderMaterial(
                        material.get("key"), material.get("resource")
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, first_stage
                        )
                    stages.add(first_stage)
                for animation in first_person_config.get("animations", ()):
                    key = animation.get("key")
                    add_stage = "first_person:animation:%s" % key
                    state_stage = (
                        "first_person:animation_state:%s" % key
                    )
                    if add_stage not in stages:
                        if not render.AddPlayerAnimation(
                            key, animation.get("resource")
                        ):
                            return self._set_visual_failure(
                                player_id, visual_id, add_stage
                            )
                        stages.add(add_stage)
                    if state_stage not in stages:
                        if not render.AddPlayerAnimationIntoState(
                            animation.get("state"),
                            animation.get("layer"),
                            key,
                            first_condition,
                        ):
                            return self._set_visual_failure(
                                player_id, visual_id, state_stage
                            )
                        stages.add(state_stage)
                for controller in first_person_config.get(
                    "animationControllers",
                    (),
                ):
                    key = controller.get("key")
                    add_stage = (
                        "first_person:animation_controller:%s" % key
                    )
                    if add_stage not in stages:
                        if not render.AddPlayerAnimationController(
                            key, controller.get("resource")
                        ):
                            return self._set_visual_failure(
                                player_id, visual_id, add_stage
                            )
                        stages.add(add_stage)
                    attach = controller.get("attach", {})
                    mode = attach.get("mode")
                    attach_stage = (
                        "first_person:animation_controller_%s:%s"
                        % (mode, key)
                    )
                    if attach_stage in stages:
                        continue
                    if mode == "state":
                        attached = render.AddPlayerAnimationIntoState(
                            attach.get("controller"),
                            attach.get("state"),
                            key,
                            first_condition,
                        )
                    else:
                        attached = render.AddPlayerScriptAnimate(
                            key,
                            first_condition,
                            bool(attach.get("autoReplace", False)),
                        )
                    if not attached:
                        return self._set_visual_failure(
                            player_id, visual_id, attach_stage
                        )
                    stages.add(attach_stage)
                for slot_id, query_name in zip(slot_ids, query_names):
                    first_stage = (
                        "first_person:render_controller:%s" % slot_id
                    )
                    if first_stage in stages:
                        continue
                    if not render.AddPlayerRenderController(
                        first_person_config.get("renderController"),
                        "%s > 0.5 && variable.is_first_person"
                        % query_name,
                    ):
                        return self._set_visual_failure(
                            player_id, visual_id, first_stage
                        )
                    stages.add(first_stage)
            ready_to_rebuild.append(visual_id)
        if ready_to_rebuild:
            if not render.RebuildPlayerRender():
                return self._set_visual_failure(
                    player_id, ready_to_rebuild[0], "rebuild"
                )
            prepared.update(ready_to_rebuild)
            self.visualLastFailureByPlayer.pop(player_id, None)
            print("[Chatelaine][Visual] PREPARED player=%s visuals=%s" % (
                player_id,
                ",".join(ready_to_rebuild),
            ))
        self._apply_visual_state(player_id)
        return all(visual_id in prepared for visual_id, _visual in pending)

    def _apply_visual_state(self, player_id):
        if self._destroyed:
            return False
        prepared = self.visualPreparedByPlayer.get(player_id, set())
        if not prepared:
            return False
        query = self.compFactory.CreateQueryVariable(player_id)
        if query is None:
            return False
        slot_states = self.visualStates.get(player_id, {}).get("slots", {})
        visuals = self.visualRegistry.get("visualsById", {})
        result = True
        for visual_id in prepared:
            visual = visuals.get(visual_id, {})
            for slot_id in visual.get("slotIds", ()):
                state = slot_states.get(slot_id, {})
                visible = bool(
                    state.get("visible")
                    and state.get("visualId") == visual_id
                )
                result = bool(query.Set(
                    self._visual_query_name(visual_id, slot_id),
                    1.0 if visible else 0.0,
                )) and result
        return result

    def OnChatelaineInventoryState(self, args):
        if self._destroyed:
            return False
        if not isinstance(args, dict):
            return
        opened_response = False
        if self.chatelaineInventoryAwaitingOpen:
            if (
                args.get("result") != "opened"
                or args.get("openRequestId")
                != self.chatelaineInventoryOpenRequestId
            ):
                return
            self.chatelaineInventoryAwaitingOpen = False
            self.chatelaineInventoryOpenRequestId = None
            self._lastInventoryResponseRequestId = 0
            opened_response = True
        else:
            current = self.chatelaineInventoryState.get("sessionId")
            if current is None or args.get("sessionId") != current:
                return
        response_request_id = args.get("requestId")
        if _is_int(response_request_id):
            response_request_id = int(response_request_id)
            if response_request_id <= self._lastInventoryResponseRequestId:
                # A delayed streaming/page response must never roll the
                # replica back after a newer action result was already used.
                return
            self._lastInventoryResponseRequestId = response_request_id
        args = dict(args)
        args["page"] = (
            "chatelaine" if args.get("activePageId") is not None else "armor"
        )
        self.chatelaineInventoryState = args
        self.chatelaineInventoryStateVersion += 1
        proxy = self.activeChatelaineInventoryProxy
        if proxy is not None:
            proxy.RefreshCurioState()
        if self.chatelaineInventoryAdvanceAfterOpen:
            self.chatelaineInventoryAdvanceAfterOpen = False
            self._send_inventory_action({"action": "next_page"})

    def SetActiveChatelaineInventoryProxy(self, proxy, expected=None):
        if self._destroyed:
            return False
        if (
            expected is not None
            and self.activeChatelaineInventoryProxy is not expected
        ):
            return False
        self.activeChatelaineInventoryProxy = proxy
        return True

    def GetCurioInventoryState(self):
        if self._destroyed:
            return self.chatelaineInventoryState
        return self.chatelaineInventoryState

    def GetCurioInventoryStateVersion(self):
        if self._destroyed:
            return self.chatelaineInventoryStateVersion
        return self.chatelaineInventoryStateVersion

    def IsCurioInventoryAwaitingOpen(self):
        if self._destroyed:
            return False
        return self.chatelaineInventoryAwaitingOpen

    def OpenCurioInventory(self):
        if self._destroyed:
            return False
        request_id = self._nextOpenRequestId
        self._nextOpenRequestId += 1
        self.chatelaineInventoryAwaitingOpen = True
        self.chatelaineInventoryOpenRequestId = request_id
        self._lastInventoryResponseRequestId = 0
        self.chatelaineInventoryState["sessionId"] = None
        self.NotifyToServer(OPEN_EVENT, {"openRequestId": request_id})
        return request_id

    def EnsureCurioInventorySession(self):
        if self._destroyed:
            return False
        if self.chatelaineInventoryState.get("sessionId") is not None:
            return True
        if self.chatelaineInventoryAwaitingOpen:
            return True
        return bool(self.OpenCurioInventory())

    def NextChatelainePage(self):
        if self._destroyed:
            return False
        if self.chatelaineInventoryState.get("sessionId") is None:
            self.chatelaineInventoryAdvanceAfterOpen = True
            if not self.EnsureCurioInventorySession():
                self.chatelaineInventoryAdvanceAfterOpen = False
                return False
            return True
        return self._send_inventory_action({"action": "next_page"})

    def SetCurioInventoryPage(self, page):
        if self._destroyed:
            return False
        page_id = None if page == "armor" else page
        if page == "chatelaine":
            page_id = "__first__"
        return self._send_inventory_action({
            "action": "set_page",
            "pageId": page_id,
        })

    def RefreshCurioInventoryState(self):
        if self._destroyed:
            return False
        return self._send_inventory_action({"action": "refresh"})

    def _transfer_curio_inventory(self, payload):
        if not isinstance(payload, dict):
            return False
        action = dict(payload)
        action["action"] = "transfer"
        action["revision"] = self.chatelaineInventoryState.get(
            "equipmentRevision",
            0,
        )
        return self._send_inventory_action(action)

    def TransferCurioInventory(
        self,
        source_domain,
        source_slot,
        target_domain,
        target_slot,
        take_count,
        source_item=None,
        target_item=None,
    ):
        if self._destroyed:
            return False
        if source_domain not in ("inventory", "curio"):
            return False
        if target_domain not in ("inventory", "curio"):
            return False
        payload = {
            "sourceDomain": source_domain,
            "targetDomain": target_domain,
            "takeCount": int(take_count),
        }
        if source_domain == "inventory":
            payload["sourceInventorySlot"] = int(source_slot)
        else:
            source_id = self._curio_slot_id(source_slot)
            if source_id is None:
                return False
            payload["sourceSlotId"] = source_id
        if target_domain == "inventory":
            payload["targetInventorySlot"] = int(target_slot)
        else:
            target_id = self._curio_slot_id(target_slot)
            if target_id is None:
                return False
            payload["targetSlotId"] = target_id
        if isinstance(source_item, dict):
            payload["expectedSource"] = dict(source_item)
        if isinstance(target_item, dict):
            payload["expectedTarget"] = dict(target_item)
        return self._transfer_curio_inventory(payload)

    def DropCurioInventory(
        self,
        source_domain,
        source_slot,
        take_count,
        source_item=None,
    ):
        if self._destroyed:
            return False
        if source_domain not in ("inventory", "curio", "cursor"):
            return False
        if not isinstance(take_count, int) or int(take_count) < 1:
            return False
        payload = {
            "action": "drop",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "sourceDomain": source_domain,
            "takeCount": int(take_count),
        }
        if source_domain == "inventory":
            if not isinstance(source_slot, int):
                return False
            payload["sourceInventorySlot"] = int(source_slot)
        elif source_domain == "curio":
            slot_id = self._curio_slot_id(source_slot)
            if slot_id is None:
                return False
            payload["sourceSlotId"] = slot_id
        if isinstance(source_item, dict):
            payload["expectedSource"] = dict(source_item)
        return self._send_inventory_action(payload)

    def PickCurioInventoryCursor(
        self, source_domain, source_slot, take_count, source_item=None
    ):
        if self._destroyed:
            return False
        if source_domain not in ("inventory", "curio"):
            return False
        payload = {
            "action": "cursor_pick",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "sourceDomain": source_domain,
            "takeCount": int(take_count),
        }
        if source_domain == "inventory":
            payload["sourceInventorySlot"] = int(source_slot)
        else:
            slot_id = self._curio_slot_id(source_slot)
            if slot_id is None:
                return False
            payload["sourceSlotId"] = slot_id
        if isinstance(source_item, dict):
            payload["expectedSource"] = dict(source_item)
        return self._send_inventory_action(payload)

    def PlaceCurioInventoryCursor(
        self, target_domain, target_slot, take_count, cursor_item, target_item
    ):
        if self._destroyed:
            return False
        if target_domain not in ("inventory", "curio"):
            return False
        payload = {
            "action": "cursor_place",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "targetDomain": target_domain,
            "takeCount": int(take_count),
            "expectedCursor": dict(cursor_item or {}),
            "expectedTarget": dict(target_item or {}),
        }
        if target_domain == "inventory":
            payload["targetInventorySlot"] = int(target_slot)
        else:
            slot_id = self._curio_slot_id(target_slot)
            if slot_id is None:
                return False
            payload["targetSlotId"] = slot_id
        return self._send_inventory_action(payload)

    def CoalesceCurioInventoryCursor(self, item):
        if self._destroyed:
            return False
        return self._send_inventory_action({
            "action": "cursor_coalesce",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "expectedCursor": dict(item or {}),
        })

    def ReturnCurioInventoryCursor(self):
        if self._destroyed:
            return False
        return self._send_inventory_action({
            "action": "cursor_return",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
        })

    def CoalesceCurioInventory(self, slot, item):
        if self._destroyed:
            return False
        if not isinstance(slot, int) or slot < 0 or slot > 35:
            return False
        payload = {
            "action": "coalesce",
            "sourceInventorySlot": int(slot),
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision",
                0,
            ),
        }
        if isinstance(item, dict):
            payload["expectedSource"] = dict(item)
        return self._send_inventory_action(payload)

    def CanEquipCurio(self, slot_id, item):
        if self._destroyed:
            return False
        item_id = ""
        if isinstance(item, dict):
            item_id = item.get("newItemName") or item.get("itemName") or ""
        item_types = self.visualRegistry.get(
            "itemTypesByItemId",
            {},
        ).get(item_id, ())
        for slot in self.chatelaineInventoryState.get("slots", ()):
            if slot.get("slotId") != slot_id:
                continue
            accepted = slot.get("acceptedTypes", ())
            return any(type_id in accepted for type_id in item_types)
        return False

    def PlayInscriptionUiSound(self, sound_name, volume=1.0, pitch=1.0):
        if self._destroyed:
            return False
        if self.uiAudioComp is None:
            self.uiAudioComp = self.compFactory.CreateCustomAudio(
                clientApi.GetLevelId()
            )
        if self.uiAudioComp is not None:
            self.uiAudioComp.PlayCustomUIMusic(
                sound_name,
                volume,
                pitch,
                False,
            )
            return True
        return False

    def _curio_slot_id(self, index):
        if not isinstance(index, int):
            return None
        slots = self.chatelaineInventoryState.get("slots", ())
        if index < 0 or index >= len(slots):
            return None
        return slots[index].get("slotId")

    def CloseCurioInventory(self):
        if self._destroyed:
            return False
        session_id = self.chatelaineInventoryState.get("sessionId")
        self._clear_curio_inventory_cache()
        if session_id is None:
            return False
        return self.NotifyToServer(
            CLOSE_EVENT,
            {"sessionId": session_id},
        )

    def _clear_curio_inventory_cache(self):
        self.chatelaineInventoryAwaitingOpen = False
        self.chatelaineInventoryOpenRequestId = None
        self.chatelaineInventoryAdvanceAfterOpen = False
        self._lastInventoryResponseRequestId = 0
        self.chatelaineInventoryState = {
            "sessionId": None,
            "equipmentRevision": 0,
            "activePageId": None,
            "slots": [],
            "inventory": [],
            "cursorItem": {},
            "cursorOrigin": {},
        }
        self.chatelaineInventoryStateVersion += 1

    def DistributeCurioInventory(
        self,
        source_slot,
        expected_source,
        held_count,
        targets,
        mode,
    ):
        if self._destroyed:
            return False
        if (
            not isinstance(source_slot, int)
            or source_slot < 0
            or source_slot > 35
            or not isinstance(held_count, int)
            or held_count <= 0
            or not isinstance(targets, list)
            or not targets
            or mode not in ("even", "single")
        ):
            return False
        normalized = []
        for entry in targets:
            if not isinstance(entry, dict):
                return False
            slot = entry.get("slot")
            if not isinstance(slot, int) or slot < 0 or slot > 35:
                return False
            normalized.append({
                "slot": int(slot),
                "expected": dict(entry.get("expected") or {}),
            })
        return self._send_inventory_action({
            "action": "distribute",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision",
                0,
            ),
            "sourceInventorySlot": int(source_slot),
            "expectedSource": dict(expected_source or {}),
            "heldCount": int(held_count),
            "targets": normalized,
            "mode": mode,
        })

    def DistributeCurioInventoryCursor(self, item, targets, mode):
        if self._destroyed:
            return False
        if not isinstance(targets, list) or not targets:
            return False
        normalized = []
        for entry in targets:
            if not isinstance(entry, dict):
                return False
            slot = entry.get("slot")
            if not isinstance(slot, int) or slot < 0 or slot > 35:
                return False
            normalized.append({
                "slot": int(slot),
                "expected": dict(entry.get("expected") or {}),
            })
        return self._send_inventory_action({
            "action": "cursor_distribute",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "expectedCursor": dict(item or {}),
            "targets": normalized,
            "mode": mode,
        })

    def UpdateCurioInventoryDistribution(
        self,
        distribution_id,
        cursor_owned,
        source_slot,
        item,
        held_count,
        targets,
        mode,
    ):
        if self._destroyed:
            return False
        if (
            not isinstance(distribution_id, int)
            or distribution_id < 1
            or not isinstance(held_count, int)
            or held_count < 1
            or not isinstance(targets, list)
            or not targets
            or mode not in ("even", "single")
        ):
            return False
        normalized = []
        for entry in targets:
            if not isinstance(entry, dict):
                return False
            slot = entry.get("slot")
            weight = entry.get("weight")
            if (
                not isinstance(slot, int)
                or slot < 0
                or slot > 35
                or not isinstance(weight, int)
                or weight < 1
            ):
                return False
            normalized.append({
                "slot": int(slot),
                "weight": int(weight),
                "expected": dict(entry.get("expected") or {}),
            })
        payload = {
            "action": "distribute_update",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "distributionId": int(distribution_id),
            "cursorOwned": bool(cursor_owned),
            "expectedSource": dict(item or {}),
            "heldCount": int(held_count),
            "targets": normalized,
            "mode": mode,
        }
        if not cursor_owned:
            payload["sourceInventorySlot"] = int(source_slot)
        return self._send_inventory_action(payload)

    def FinishCurioInventoryDistribution(self, distribution_id):
        if self._destroyed:
            return False
        if not isinstance(distribution_id, int) or distribution_id < 1:
            return False
        return self._send_inventory_action({
            "action": "distribute_finish",
            "revision": self.chatelaineInventoryState.get(
                "equipmentRevision", 0
            ),
            "distributionId": int(distribution_id),
        })

    def _send_inventory_action(self, payload):
        if self._destroyed:
            return False
        session_id = self.chatelaineInventoryState.get("sessionId")
        if session_id is None:
            return False
        request_id = self._nextActionRequestId
        self._nextActionRequestId += 1
        action = dict(payload)
        action["sessionId"] = session_id
        action["requestId"] = request_id
        self.NotifyToServer(ACTION_EVENT, action)
        return request_id
