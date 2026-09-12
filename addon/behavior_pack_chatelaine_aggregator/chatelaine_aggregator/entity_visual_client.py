# -*- coding: utf-8 -*-
"""Independent single-actor visual injection; player render/UI code is untouched."""
import time
import mod.client.extraClientApi as clientApi
from chatelaine_aggregator.registry import visual_slot_query_name

REGISTRY_EVENT = "ChatelaineEntityVisualRegistryClientEvent"
STATE_EVENT = "ChatelaineEntityVisualStateClientEvent"
REQUEST_EVENT = "ChatelaineEntityVisualSyncRequestServerEvent"
MAX_ACTORS = 512
RETRY_LIMIT = 20


class EntityVisualClient(object):
    def __init__(self, system):
        self.system = system
        self.factory = system.compFactory
        self.game = self.factory.CreateGame(clientApi.GetLevelId())
        self.query_registry = self.factory.CreateQueryVariable(clientApi.GetLevelId())
        self.registered_queries = system.visualQueryRegistered
        self.session = "%d:%s" % (int(time.time() * 1000000), id(self))
        self.epoch = None
        self.registry = {"registryRevision": 0, "visualsById": {}}
        self.attachable_entities = frozenset()
        self.entries = {}
        self.pending_requests = set()
        self.timers = {}
        self.serial = 0
        self.destroyed = False
        self.started = False
        self.hello_token = 0

    def _timer(self, key, delay, callback, *args):
        if self.destroyed or self.game is None:
            return
        self._cancel(key)
        pending = {"handle": None}
        self.timers[key] = pending
        def invoke():
            if self.destroyed or self.timers.get(key) is not pending:
                return
            self.timers.pop(key, None)
            callback(*args)
        pending["handle"] = self.game.AddTimer(delay, invoke)
        if pending["handle"] is None or pending["handle"] is False:
            self.timers.pop(key, None)

    def _cancel(self, key):
        old = self.timers.pop(key, None)
        if old and old["handle"] is not None:
            self.game.CancelTimer(old["handle"])

    def _send(self, operation, targets=None):
        payload = {"operation": operation, "clientSession": self.session}
        if operation == "hello":
            self.hello_token += 1
            payload["helloToken"] = self.hello_token
        if targets is not None:
            payload["targets"] = targets
        return self.system.NotifyToServer(REQUEST_EVENT, payload)

    def ready(self, attempt=0):
        if self.destroyed:
            return
        self.started = True
        self._send("hello")
        if self.epoch is None and attempt < RETRY_LIMIT:
            self._timer("hello", 0.25, self.ready, attempt + 1)
        if "lease" not in self.timers:
            self._timer("lease", 30.0, self._renew)

    def on_registry(self, args):
        if self.destroyed or not isinstance(args, dict) or args.get("clientSession") != self.session:
            return
        if args.get("helloToken") != self.hello_token:
            return
        epoch = args.get("coreEpoch")
        if not epoch:
            return
        if epoch == self.epoch and args.get("registryRevision", 0) < self.registry["registryRevision"]:
            return
        if self.epoch is not None and epoch != self.epoch:
            for entity_id, entry in list(self.entries.items()):
                self._clear_render(entity_id, entry)
                entry["state"] = None
        self.epoch = epoch
        self.registry = {"registryRevision": args.get("registryRevision", 0),
                         "visualsById": args.get("visualsById", {})}
        self.attachable_entities = frozenset(args.get("attachableEntities", ()))
        self._cancel("hello")
        for entity_id, entry in list(self.entries.items()):
            self._queue(entity_id)
            self._prepare(entity_id, entry, 0)

    def _new_entry(self, entity_id):
        if entity_id in self.entries:
            return self.entries[entity_id]
        if len(self.entries) >= MAX_ACTORS:
            return None
        self.serial += 1
        entry = {"token": self.serial, "state": None, "installed": {},
                 "prepared": set(), "queries": set(), "lastFailure": None}
        self.entries[entity_id] = entry
        return entry

    def on_add(self, args):
        if self.destroyed or not isinstance(args, dict):
            return
        entity_id = args.get("id")
        if not entity_id or args.get("engineTypeStr") in ("minecraft:player", "minecraft:item"):
            return
        old = self.entries.get(entity_id)
        if old:
            self.on_remove({"id": entity_id})
        if self._new_entry(entity_id):
            self._queue(entity_id)

    def _queue(self, entity_id):
        self.pending_requests.add(entity_id)
        if "request" not in self.timers:
            self._timer("request", 0.05, self._flush)

    def _flush(self):
        ids = sorted(self.pending_requests)[:64]
        self.pending_requests.difference_update(ids)
        targets = [{"entityId": entity_id, "clientToken": self.entries[entity_id]["token"]}
                   for entity_id in ids if entity_id in self.entries]
        if targets:
            self._send("subscribe", targets)
        if self.pending_requests:
            self._timer("request", 0.15, self._flush)

    def on_state(self, args):
        if self.destroyed or not isinstance(args, dict) or args.get("clientSession") != self.session:
            return
        if args.get("kind") == "resync":
            self.ready()
            return
        if self.epoch is not None and args.get("coreEpoch") != self.epoch:
            return
        if args.get("kind") == "candidates":
            for entity_id in args.get("entityIds", ())[:64]:
                comp = self.factory.CreateEngineType(entity_id)
                if comp and comp.GetEngineTypeStr() and self._new_entry(entity_id):
                    self._queue(entity_id)
            return
        entity_id = args.get("entityId")
        entry = self.entries.get(entity_id)
        if entry is None or args.get("clientToken") != entry["token"]:
            return
        previous = entry["state"]
        order = (args.get("entityGeneration", 0), args.get("visualRevision", 0))
        if previous is not None:
            old_order = (previous.get("entityGeneration", 0), previous.get("visualRevision", 0))
            if order <= old_order:
                return
            if (order[0] != old_order[0]
                    or args.get("entityIdentifier") != previous.get("entityIdentifier")):
                self._clear_render(entity_id, entry)
        entry["state"] = args
        self._hide(entity_id, entry)
        if not args.get("active"):
            self._cancel(entity_id)
            if args.get("entityGeneration", 0) == 0:
                self.entries.pop(entity_id, None)
            return
        self._prepare(entity_id, entry, 0)

    def _model(self, visual_id, identifier):
        visual = self.registry["visualsById"].get(visual_id)
        if not visual:
            return None
        if identifier in visual["modelsByEntity"]:
            return visual["modelsByEntity"][identifier]
        return visual["default"] if identifier in self.attachable_entities else None

    def _prepare(self, entity_id, entry, attempt):
        if self.destroyed or self.entries.get(entity_id) is not entry:
            return
        self._cancel(entity_id)
        state = entry["state"]
        if not state or not state.get("active"):
            return
        if (self.epoch != state.get("coreEpoch")
                or self.registry["registryRevision"] != state.get("registryRevision")
                or self.game.GetCurrentDimension() != state.get("dimensionId")):
            return
        comp = self.factory.CreateEngineType(entity_id)
        identifier = comp.GetEngineTypeStr() if comp else None
        render = self.factory.CreateActorRender(entity_id)
        success = bool(identifier and identifier == state.get("entityIdentifier") and render)
        rebuild = False
        required = set(v["visualId"] for v in state["slots"].values() if v.get("visualId"))
        if success:
            for visual_id in sorted(required):
                model = self._model(visual_id, identifier)
                if model is None:
                    success = False
                    break
                if visual_id in entry["prepared"]:
                    continue
                if not self._inject(entity_id, entry, visual_id, model, render):
                    success = False
                    break
                rebuild = True
            if success and rebuild:
                success = bool(render.RebuildRenderForOneActor())
                if success:
                    entry["prepared"].update(required)
        if success:
            entry["lastFailure"] = None
            self._apply(entity_id, entry)
            return
        self._hide(entity_id, entry)
        if attempt >= RETRY_LIMIT:
            print("[Chatelaine][EntityVisual] PREPARE exhausted entity=%s stage=%s" % (
                entity_id, entry["lastFailure"]))
            return
        self._timer(entity_id, 0.25, self._prepare, entity_id, entry, attempt + 1)

    def _inject(self, entity_id, entry, visual_id, model, render):
        stages = entry["installed"].setdefault(visual_id, {})
        queries = []
        for slot_id in model["slotIds"]:
            query = visual_slot_query_name(visual_id, slot_id)
            if query not in self.registered_queries:
                if not self.query_registry.Register(query, 0.0):
                    entry["lastFailure"] = "query"
                    return False
                self.registered_queries.add(query)
            entry["queries"].add(query)
            queries.append(query)
        condition = "(" + (" || ".join(q + " > 0.5" for q in queries) or "0.0") + ")"
        geometry = model["geometry"]
        operations = [("geometry", geometry["key"], render.AddGeometryToOneActor,
                       (entity_id, geometry["key"], geometry["resource"]))]
        for field, kind, method in [
                ("textures", "texture", render.AddTextureToOneActor),
                ("materials", "material", render.AddRenderMaterialToOneActor),
                ("animations", "animation", render.AddAnimationToOneActor),
                ("animationControllers", "controller", render.AddAnimationControllerToOneActor)]:
            for resource in model[field]:
                key = resource["key"]
                if field == "animationControllers":
                    key = "controller__" + key
                operations.append((kind, key, method, (entity_id, key, resource["resource"])))
                if field in ("animations", "animationControllers"):
                    operations.append(("animate", key, render.AddScriptAnimateToOneActor,
                        (entity_id, key, condition + " && (" + resource["condition"] + ")", True)))
        mapping = model["renderControllersBySlot"]
        controllers = [(mapping[slot], query + " > 0.5") for slot, query in zip(model["slotIds"], queries)] if mapping else [
            (model["renderController"], condition)]
        for controller, expression in controllers:
            operations.append(("render", controller, render.AddRenderControllerToOneActor,
                               (entity_id, controller, expression)))
        for kind, key, method, arguments in operations:
            stage = (kind, key)
            if stage in stages:
                continue
            # Never claim or remove a pre-existing native/foreign RC.
            if kind == "render" and key in (render.GetActorRenderParams(entity_id, "render_controllers") or ()):
                entry["lastFailure"] = "render_controller_collision:" + key
                return False
            if not method(*arguments):
                entry["lastFailure"] = kind + ":" + key
                return False
            stages[stage] = True
        return True

    def _hide(self, entity_id, entry):
        comp = self.factory.CreateQueryVariable(entity_id)
        if comp:
            for query in entry["queries"]:
                comp.Set(query, 0.0)

    def _apply(self, entity_id, entry):
        self._hide(entity_id, entry)
        comp = self.factory.CreateQueryVariable(entity_id)
        if comp is None:
            return
        for slot_id, state in entry["state"]["slots"].items():
            visual_id = state.get("visualId")
            if visual_id in entry["prepared"]:
                comp.Set(visual_slot_query_name(visual_id, slot_id), 1.0 if state["visible"] else 0.0)

    def _clear_render(self, entity_id, entry):
        self._hide(entity_id, entry)
        render = self.factory.CreateActorRender(entity_id)
        if render and render.GetActorRenderParams(entity_id, "render_controllers") is not None:
            failures = []
            for stages in entry["installed"].values():
                for kind, key in stages:
                    result = True
                    if kind == "animate":
                        result = render.AddScriptAnimateToOneActor(entity_id, key, "0.0", True)
                    elif kind == "render":
                        result = render.RemoveRenderControllerForOneActor(entity_id, key)
                    elif kind == "controller":
                        result = render.RemoveAnimationControllerForOneActor(entity_id, key)
                    elif kind == "geometry":
                        result = render.RemoveGeometryForOneActor(entity_id, key)
                    elif kind == "texture":
                        result = render.RemoveTextureForOneActor(entity_id, key)
                    if not result:
                        failures.append(kind + ":" + key)
            if not render.RebuildRenderForOneActor():
                failures.append("rebuild")
            if failures:
                print("[Chatelaine][EntityVisual] CLEANUP failed entity=%s stages=%s" % (
                    entity_id, failures))
        entry["installed"].clear()
        entry["prepared"].clear()
        entry["queries"].clear()

    def on_remove(self, args):
        if self.destroyed:
            return
        entity_id = args.get("id") if isinstance(args, dict) else None
        entry = self.entries.pop(entity_id, None)
        self.pending_requests.discard(entity_id)
        self._cancel(entity_id)
        if entry:
            self._clear_render(entity_id, entry)
            self._send("unsubscribe", [{"entityId": entity_id, "clientToken": entry["token"]}])

    def dimension_changed(self):
        if self.destroyed:
            return
        for entity_id in list(self.entries):
            self.on_remove({"id": entity_id})
        self.session = "%d:%s" % (int(time.time() * 1000000), id(self))
        self.epoch = None
        self.ready()

    def _renew(self):
        if self.destroyed:
            return
        targets = [{"entityId": entity_id, "clientToken": entry["token"]}
                   for entity_id, entry in sorted(self.entries.items())]
        if targets:
            for offset in range(0, len(targets), 64):
                self._send("renew", targets[offset:offset + 64])
        else:
            self._send("renew", [])
        self._timer("lease", 30.0, self._renew)

    def destroy(self):
        if self.destroyed:
            return
        self.destroyed = True
        for key in list(self.timers):
            self._cancel(key)
        for entity_id, entry in list(self.entries.items()):
            self._clear_render(entity_id, entry)
        self.entries.clear()
        self.pending_requests.clear()
        self.registry = {"registryRevision": 0, "visualsById": {}}
        self.attachable_entities = frozenset()
