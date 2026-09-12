# -*- coding: utf-8 -*-
"""Pure-data Chatelaine provider registry shared by the server System and tests."""

import copy
import json
import re


try:
    STRING_TYPES = (basestring,)
    INTEGER_TYPES = (int, long)
except NameError:
    STRING_TYPES = (str,)
    INTEGER_TYPES = (int,)

NUMBER_TYPES = INTEGER_TYPES + (float,)


CONTRACT_NAME = "chatelaine:slot_provider"
CONTRACT_VERSION = 1
SCHEMA_VERSION = 1
MAX_DATA_NESTING = 16
MAX_PAGE_SLOTS = 16
MAX_STACK = 64
CORE_ORDER_BASE = -1000000
MAX_PROVIDERS = 32
MAX_PROVIDER_TYPES = 64
MAX_PROVIDER_PAGES = 16
MAX_PROVIDER_SLOTS = 128
MAX_PROVIDER_ITEMS = 256
MAX_TOTAL_TYPES = 256
MAX_TOTAL_PAGES = 64
MAX_TOTAL_SLOTS = 512
MAX_TOTAL_ITEMS = 2048
MAX_TOTAL_VISUALS = 256
MAX_VISUAL_SLOTS_PER_VISUAL = 32
MAX_TOTAL_VISUAL_INSTANCES = 512
MAX_ENTITY_MODELS_PER_VISUAL = 32
MAX_ENTITY_VISUAL_INSTANCES = 512
MAX_PROVIDER_ATTACHABLE_ENTITIES = 64
MAX_ATTACHABLE_ENTITIES = 256
# Explicit enable_attachables=True types from the NetEase 3.9 resource baseline.
# Source file hashes: docs/source_evidence/enable_attachables_vanilla_20260912.json.
# Player has a separate render chain and is intentionally absent here.
VANILLA_ATTACHABLE_ENTITIES = (
    "minecraft:allay", "minecraft:armor_stand", "minecraft:bogged",
    "minecraft:copper_golem", "minecraft:drowned", "minecraft:happy_ghast",
    "minecraft:husk", "minecraft:piglin", "minecraft:piglin_brute",
    "minecraft:pillager", "minecraft:skeleton", "minecraft:stray",
    "minecraft:vindicator", "minecraft:warden", "minecraft:wither_skeleton",
    "minecraft:wolf", "minecraft:zombie", "minecraft:zombie_pigman",
    "minecraft:zombie_villager", "minecraft:zombie_villager_v2",
)
MAX_PROVIDER_PAYLOAD_BYTES = 131072
MAX_REGISTRY_PAYLOAD_BYTES = 524288
MAX_INVENTORY_STATE_BYTES = 262144
MAX_INVENTORY_ACTION_BYTES = 32768
MAX_VISUAL_REGISTRY_BYTES = 393216
MAX_VISUAL_STATE_BYTES = 131072
MAX_LABEL_LENGTH = 64
MAX_RESOURCE_PATH_LENGTH = 160
MAX_QUERY_NAME_LENGTH = 96


PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
NAMESPACED_ID_RE = re.compile(
    r"^[a-z][a-z0-9_]{0,31}:[a-z0-9][a-z0-9_./-]{0,63}$"
)
RESOURCE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
RESOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_./-]{0,159}$")
SOUND_EVENT_RE = re.compile(r"^(?:[a-z0-9_.-]+:)?[a-z0-9][a-z0-9_./-]*\Z")
TEXTURE_PATH_RE = re.compile(r"^textures/[a-z0-9][a-z0-9_./-]{0,151}$")
SIMPLE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


def serialized_size(value):
    """Return deterministic UTF-8 JSON size, or None for invalid data."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if not isinstance(encoded, bytes):
            encoded = encoded.encode("utf-8")
        return len(encoded)
    except Exception:
        return None


def visual_slot_query_name(visual_id, slot_id):
    """Stable bounded Molang query; finalization rejects any hash collision."""
    identity = (visual_id + "\x00" + slot_id).encode("utf-8")
    # NetEase's embedded Python exposes a reduced hashlib module on some
    # engine builds (not even sha256 is guaranteed).  FNV-1a is implemented
    # here using only integer operations, while _attach_visual_slots still
    # rejects the extremely unlikely case where two live identities collide.
    value = 144066263297769815596495629667062367629
    prime = 309485009821345068724781371
    mask = (1 << 128) - 1
    for byte in identity:
        if not isinstance(byte, int):
            byte = ord(byte)
        value ^= byte
        value = (value * prime) & mask
    return "query.mod.chatelaine_slot_%032x" % value


def _valid_namespaced_id(value):
    if not _is_string(value) or not NAMESPACED_ID_RE.match(value):
        return False
    _namespace, local = value.split(":", 1)
    segments = local.split("/")
    return all(segment not in ("", ".", "..") for segment in segments)


def _valid_resource_identifier(value, prefix=None):
    if (
        not _is_string(value)
        or len(value) > MAX_RESOURCE_PATH_LENGTH
        or not RESOURCE_ID_RE.match(value)
        or ".." in value
        or "//" in value
    ):
        return False
    return prefix is None or value.startswith(prefix)


def _valid_texture_path(value):
    if (
        not _is_string(value)
        or len(value) > MAX_RESOURCE_PATH_LENGTH
        or not TEXTURE_PATH_RE.match(value)
        or value.endswith(".png")
        or "//" in value
    ):
        return False
    return all(
        segment not in ("", ".", "..")
        for segment in value.split("/")
    )


def _valid_label(value):
    return _is_string(value) and len(value) <= MAX_LABEL_LENGTH


def _only_fields(source, required, optional=()):
    if not isinstance(source, dict):
        return False
    keys = set(source.keys())
    return set(required).issubset(keys) and not (
        keys - set(required) - set(optional)
    )


CORE_TYPES = (
    ("chatelaine:head", u"头部"),
    ("chatelaine:necklace", u"项链"),
    ("chatelaine:back", u"背部"),
    ("chatelaine:body", u"身体"),
    ("chatelaine:hands", u"手部"),
    ("chatelaine:bracelet", u"手镯"),
    ("chatelaine:ring", u"戒指"),
    ("chatelaine:belt", u"腰带"),
    ("chatelaine:charm", u"护符"),
    ("chatelaine:curio", u"饰品"),
)


def _core_slot(slot_id, label, order_offset, type_id, texture_name):
    return {
        "slotId": slot_id,
        "label": label,
        "order": CORE_ORDER_BASE + order_offset,
        "maxStack": 1,
        "acceptedTypes": [type_id],
        "emptyTexture": "textures/ui/chatelaine/empty_%s_slot" % texture_name,
        "providerId": "chatelaine",
        "pageId": "chatelaine:standard",
        "builtIn": True,
    }


CORE_SLOTS = (
    _core_slot("chatelaine:head", u"头部", 0, "chatelaine:head", "head"),
    _core_slot(
        "chatelaine:necklace", u"项链", 1, "chatelaine:necklace", "necklace"
    ),
    _core_slot("chatelaine:back", u"背部", 2, "chatelaine:back", "back"),
    _core_slot("chatelaine:body", u"身体", 3, "chatelaine:body", "body"),
    _core_slot("chatelaine:hands_1", u"手部", 4, "chatelaine:hands", "hands"),
    _core_slot("chatelaine:hands_2", u"手部", 5, "chatelaine:hands", "hands"),
    _core_slot(
        "chatelaine:bracelet", u"手镯", 6, "chatelaine:bracelet", "bracelet"
    ),
    _core_slot("chatelaine:ring_1", u"戒指", 7, "chatelaine:ring", "ring"),
    _core_slot("chatelaine:ring_2", u"戒指", 8, "chatelaine:ring", "ring"),
    _core_slot("chatelaine:belt", u"腰带", 9, "chatelaine:belt", "belt"),
    _core_slot("chatelaine:charm", u"护符", 10, "chatelaine:charm", "charm"),
    _core_slot("chatelaine:curio", u"饰品", 11, "chatelaine:curio", "curio"),
)


CORE_PAGE = {
    "pageId": "chatelaine:standard",
    "label": u"垂佩",
    "order": CORE_ORDER_BASE,
    "providerId": "chatelaine",
    "builtIn": True,
}


NATIVE_VISUAL_SLOTS = frozenset((
    "mainhand",
    "offhand",
    "head",
    "chest",
    "legs",
    "feet",
))


def _copy(value):
    return copy.deepcopy(value)


def _is_string(value):
    return isinstance(value, STRING_TYPES) and bool(value)


def _is_int(value):
    return isinstance(value, INTEGER_TYPES) and not isinstance(value, bool)


def _owned(identifier, provider_id):
    return (
        _valid_namespaced_id(identifier)
        and PROVIDER_ID_RE.match(provider_id or "")
        and identifier.split(":", 1)[0] == provider_id
        and provider_id != "chatelaine"
    )


def _unique_string_list(value, allow_empty=False, validator=None):
    if not isinstance(value, list):
        return None
    validator = validator or _valid_namespaced_id
    result = []
    seen = set()
    for entry in value:
        if not validator(entry) or entry in seen:
            return None
        seen.add(entry)
        result.append(entry)
    if not result and not allow_empty:
        return None
    return result


class ChatelaineRegistry(object):
    """Validate provider snapshots and build one deterministic registry."""

    def __init__(self, item_exists=None):
        self._item_exists = item_exists or (lambda _item_id: True)
        self._providers = {}
        self._frozen = False
        self._dirty = False
        self._revision = 0
        self._snapshot = self._empty_snapshot()
        self._slot_ids = ()
        self._entity_visual_registry = {"registryRevision": 0, "visualsById": {}}
        self._attachable_entities = frozenset()
        self._player_visual_registry = {"registryRevision": 0, "visualsById": {}, "itemTypesByItemId": {}}
        self._errors = []
        self._budget_usage_cache = self._budget_usage()

    def register(self, contract_name, contract_version, provider_id, payload):
        if contract_name != CONTRACT_NAME:
            return self._rejected("unknown_contract")
        if contract_version != CONTRACT_VERSION:
            return self._rejected("unsupported_version")
        if not PROVIDER_ID_RE.match(provider_id or "") or provider_id == "chatelaine":
            return self._rejected("invalid_provider_id")
        if (
            provider_id not in self._providers
            and len(self._providers) >= MAX_PROVIDERS
        ):
            return self._rejected("provider_budget_exceeded")
        payload_size = serialized_size(payload)
        if (
            payload_size is None
            or payload_size > MAX_PROVIDER_PAYLOAD_BYTES
        ):
            return self._rejected("provider_payload_budget_exceeded")

        normalized, reason = self._normalize_provider(provider_id, payload)
        if normalized is None:
            return self._rejected(reason or "invalid_payload")

        previous = self._providers.get(provider_id)
        if self._frozen:
            if previous == normalized:
                return self._accepted(True)
            return self._rejected("registry_frozen")

        usage = self._budget_usage(provider_id, normalized)
        if not self._fits_total_budget(usage):
            return self._rejected("registry_budget_exceeded")
        self._providers[provider_id] = normalized
        self._dirty = True
        self._budget_usage_cache = usage
        return self._accepted(previous == normalized)

    def unregister(self, provider_id):
        if self._frozen or provider_id not in self._providers:
            return False
        del self._providers[provider_id]
        self._dirty = True
        self._budget_usage_cache = self._budget_usage()
        return True

    def finalize(self):
        if self._frozen and not self._dirty:
            return True
        snapshot, errors = self._build_snapshot()
        snapshot_size = serialized_size(snapshot)
        if (
            snapshot_size is None
            or snapshot_size > MAX_REGISTRY_PAYLOAD_BYTES
        ):
            errors.append("registry_payload_budget_exceeded")
        player_visuals = _copy(snapshot.get("visualsById", {}))
        for visual in player_visuals.values():
            visual.pop("entity", None)
        player_projection = {
            "registryRevision": self._revision + 1,
            "visualsById": player_visuals,
            "itemTypesByItemId": snapshot.get("itemTypesByItemId", {}),
        }
        client_registry_size = serialized_size(player_projection)
        if (
            client_registry_size is None
            or client_registry_size > MAX_VISUAL_REGISTRY_BYTES
        ):
            errors.append("client_registry_payload_budget_exceeded")
        entity_projection = self._build_entity_visual_registry(snapshot, errors)
        entity_projection["registryRevision"] = self._revision + 1
        entity_size = serialized_size(entity_projection)
        if entity_size is None or entity_size > MAX_VISUAL_REGISTRY_BYTES:
            errors.append("entity_visual_registry_payload_budget_exceeded")
        self._errors = errors
        if errors:
            return False
        self._revision += 1
        snapshot["registryRevision"] = self._revision
        self._snapshot = snapshot
        self._entity_visual_registry = entity_projection
        self._attachable_entities = frozenset(snapshot["attachableEntities"])
        self._player_visual_registry = player_projection
        self._slot_ids = tuple(snapshot["slotsById"])
        self._dirty = False
        self._frozen = True
        self._budget_usage_cache = self._budget_usage()
        return True

    def get_snapshot(self):
        return _copy(self._snapshot)

    def get_contributions(self):
        return _copy(self._providers)

    def is_ready(self):
        return bool(self._frozen and not self._errors)

    def get_revision(self):
        return self._revision

    def player_visual_registry(self):
        return _copy(self._player_visual_registry)

    def entity_visual_registry(self):
        return _copy(self._entity_visual_registry)

    def entity_visual_for_item(self, item_id):
        return self._snapshot["itemsById"].get(item_id, {}).get("equippedVisualId")

    def entity_visual_model(self, visual_id, identifier):
        """Internal frozen view; consumers must not modify it."""
        visual = self._entity_visual_registry["visualsById"].get(visual_id)
        if visual is None:
            return None
        if identifier in visual["modelsByEntity"]:
            return visual["modelsByEntity"][identifier]
        return visual["default"] if identifier in self._attachable_entities else None

    def get_slot(self, slot_id):
        """Return one detached slot definition without copying the registry."""
        return _copy(self._snapshot["slotsById"].get(slot_id))

    def get_slot_ids(self):
        """Immutable finalized slot index for internal reconciliation."""
        return self._slot_ids

    def get_status(self):
        return {
            "contractName": CONTRACT_NAME,
            "contractVersion": CONTRACT_VERSION,
            "providerCount": len(self._providers),
            "registryRevision": self._revision,
            "dirty": self._dirty,
            "frozen": self._frozen,
            "ready": self.is_ready(),
            "errors": _copy(self._errors),
            # Usage changes only with contributions or the finalized snapshot.
            # Its scalar values need only a shallow detached copy for callers.
            "budgetUsage": dict(self._budget_usage_cache),
            "budgetLimits": {
                "providers": MAX_PROVIDERS,
                "types": MAX_TOTAL_TYPES,
                "pages": MAX_TOTAL_PAGES,
                "slots": MAX_TOTAL_SLOTS,
                "items": MAX_TOTAL_ITEMS,
                "visuals": MAX_TOTAL_VISUALS,
                "visualInstances": MAX_TOTAL_VISUAL_INSTANCES,
                "entityModelsPerVisual": MAX_ENTITY_MODELS_PER_VISUAL,
                "entityVisualInstances": MAX_ENTITY_VISUAL_INSTANCES,
                "providerAttachableEntities": MAX_PROVIDER_ATTACHABLE_ENTITIES,
                "attachableEntities": MAX_ATTACHABLE_ENTITIES,
                "providerPayloadBytes": MAX_PROVIDER_PAYLOAD_BYTES,
                "registryPayloadBytes": MAX_REGISTRY_PAYLOAD_BYTES,
            },
        }

    def _accepted(self, idempotent=False):
        return {
            "accepted": True,
            "contractVersion": CONTRACT_VERSION,
            "idempotent": bool(idempotent),
        }

    def _rejected(self, reason):
        return {
            "accepted": False,
            "reason": reason,
            "contractVersion": CONTRACT_VERSION,
        }

    def _empty_snapshot(self):
        return {
            "schemaVersion": SCHEMA_VERSION,
            "registryRevision": 0,
            "typesById": dict(
                (
                    type_id,
                    {
                        "typeId": type_id,
                        "label": label,
                        "providerId": "chatelaine",
                        "builtIn": True,
                    },
                )
                for type_id, label in CORE_TYPES
            ),
            "pages": [],
            "slotsById": {},
            "itemTypesByItemId": {},
            "itemsById": {},
            "visualsById": {},
            "attachableEntities": list(VANILLA_ATTACHABLE_ENTITIES),
            "attachableEntitySources": dict((identifier, ["chatelaine"])
                for identifier in VANILLA_ATTACHABLE_ENTITIES),
        }

    def _normalize_provider(self, provider_id, payload):
        if not _only_fields(
            payload,
            ("schemaVersion", "types", "pages", "items"),
            ("attachableEntities",),
        ):
            return None, "invalid_payload"
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            return None, "unsupported_schema"
        for key in ("types", "pages", "items"):
            if not isinstance(payload.get(key), list):
                return None, "invalid_%s" % key
        if len(payload["types"]) > MAX_PROVIDER_TYPES:
            return None, "provider_type_budget_exceeded"
        if len(payload["pages"]) > MAX_PROVIDER_PAGES:
            return None, "provider_page_budget_exceeded"
        if len(payload["items"]) > MAX_PROVIDER_ITEMS:
            return None, "provider_item_budget_exceeded"
        if not self._is_contract_value(payload, 0):
            return None, "invalid_payload_value"
        attachable_entities = _unique_string_list(payload.get("attachableEntities", []),
            allow_empty=True, validator=_valid_namespaced_id)
        if attachable_entities is None or "minecraft:player" in attachable_entities:
            return None, "invalid_attachable_entities"
        if len(attachable_entities) > MAX_PROVIDER_ATTACHABLE_ENTITIES:
            return None, "provider_attachable_entity_budget_exceeded"

        types = []
        seen_types = set()
        for source in payload["types"]:
            normalized = self._normalize_type(provider_id, source)
            if normalized is None:
                return None, "invalid_type"
            type_id = normalized["typeId"]
            if type_id in seen_types:
                return None, "duplicate_type"
            seen_types.add(type_id)
            types.append(normalized)

        pages = []
        seen_pages = set()
        seen_slots = set()
        for source in payload["pages"]:
            normalized = self._normalize_page(provider_id, source)
            if normalized is None:
                return None, "invalid_page"
            page_id = normalized["pageId"]
            if page_id in seen_pages:
                return None, "duplicate_page"
            seen_pages.add(page_id)
            for slot in normalized["slots"]:
                slot_id = slot["slotId"]
                if slot_id in seen_slots:
                    return None, "duplicate_slot"
                seen_slots.add(slot_id)
            pages.append(normalized)
        if len(seen_slots) > MAX_PROVIDER_SLOTS:
            return None, "provider_slot_budget_exceeded"

        items = []
        seen_items = set()
        for source in payload["items"]:
            normalized = self._normalize_item(provider_id, source)
            if normalized is None:
                return None, "invalid_item"
            item_id = normalized["itemId"]
            if item_id in seen_items:
                return None, "duplicate_item"
            seen_items.add(item_id)
            if not self._safe_item_exists(item_id):
                return None, "unknown_item"
            items.append(normalized)

        return {
            "schemaVersion": SCHEMA_VERSION,
            "types": types,
            "pages": pages,
            "items": items,
            "attachableEntities": sorted(attachable_entities),
        }, None

    def _normalize_type(self, provider_id, source):
        if not _only_fields(source, ("typeId", "label")):
            return None
        type_id = source.get("typeId")
        label = source.get("label")
        if not _owned(type_id, provider_id) or not _valid_label(label):
            return None
        return {
            "typeId": type_id,
            "label": label,
            "providerId": provider_id,
            "builtIn": False,
        }

    def _normalize_page(self, provider_id, source):
        if not _only_fields(
            source,
            ("pageId", "label", "slots"),
            ("order",),
        ):
            return None
        page_id = source.get("pageId")
        label = source.get("label")
        order = source.get("order", 0)
        slots = source.get("slots")
        if (
            not _owned(page_id, provider_id)
            or not _valid_label(label)
            or not _is_int(order)
            or order < 0
            or not isinstance(slots, list)
            or not 1 <= len(slots) <= MAX_PAGE_SLOTS
        ):
            return None
        normalized_slots = []
        for source_slot in slots:
            slot = self._normalize_slot(provider_id, page_id, source_slot)
            if slot is None:
                return None
            normalized_slots.append(slot)
        normalized_slots.sort(
            key=lambda slot: (slot["order"], slot["slotId"])
        )
        return {
            "pageId": page_id,
            "label": label,
            "order": int(order),
            "providerId": provider_id,
            "builtIn": False,
            "slots": normalized_slots,
        }

    def _normalize_slot(self, provider_id, page_id, source):
        if not _only_fields(
            source,
            ("slotId", "label", "acceptedTypes"),
            ("order", "maxStack", "emptyTexture"),
        ):
            return None
        slot_id = source.get("slotId")
        label = source.get("label")
        order = source.get("order", 0)
        max_stack = source.get("maxStack", 1)
        accepted = _unique_string_list(source.get("acceptedTypes"))
        texture = source.get("emptyTexture", "")
        if (
            not _owned(slot_id, provider_id)
            or not _valid_label(label)
            or not _is_int(order)
            or order < 0
            or not _is_int(max_stack)
            or not 1 <= max_stack <= MAX_STACK
            or accepted is None
            or (texture and not _valid_texture_path(texture))
        ):
            return None
        return {
            "slotId": slot_id,
            "label": label,
            "order": int(order),
            "maxStack": int(max_stack),
            "acceptedTypes": accepted,
            "emptyTexture": texture,
            "providerId": provider_id,
            "pageId": page_id,
            "builtIn": False,
        }

    def _normalize_item(self, provider_id, source):
        if not _only_fields(
            source,
            ("itemId", "types"),
            (
                "equipOnUse",
                "quickEquipDecision",
                "equippedVisual",
                "equipSound",
                "quickEquipSound",
            ),
        ):
            return None
        item_id = source.get("itemId")
        types = _unique_string_list(source.get("types"))
        equip_on_use = source.get("equipOnUse", False)
        quick_equip_decision = source.get("quickEquipDecision", False)
        if (
            not _valid_namespaced_id(item_id)
            or types is None
            or not isinstance(equip_on_use, bool)
            or not isinstance(quick_equip_decision, bool)
            or (quick_equip_decision and not equip_on_use)
        ):
            return None
        visual = source.get("equippedVisual")
        if visual is not None:
            visual = self._normalize_visual(provider_id, visual)
            if visual is None:
                return None
        equip_sound = self._normalize_sound(source.get("equipSound"))
        quick_equip_sound = self._normalize_sound(
            source.get("quickEquipSound")
        )
        if (
            ("equipSound" in source and equip_sound is None)
            or (
                "quickEquipSound" in source
                and quick_equip_sound is None
            )
        ):
            return None
        return {
            "itemId": item_id,
            "types": types,
            "equipOnUse": equip_on_use,
            "quickEquipDecision": quick_equip_decision,
            "equippedVisual": visual,
            "equipSound": equip_sound,
            "quickEquipSound": quick_equip_sound,
            "providerId": provider_id,
        }

    def _normalize_visual(self, provider_id, source):
        if not _only_fields(
            source,
            (
                "visualId",
                "geometry",
                "textures",
                "materials",
                "renderController",
            ),
            (
                "animations",
                "animationControllers",
                "nativeSlotBlock",
                "firstPerson",
                "entity",
            ),
        ):
            return None
        visual_id = source.get("visualId")
        if not _owned(visual_id, provider_id):
            return None
        geometry = self._normalize_resource(
            source.get("geometry"),
            provider_id,
            "geometry.",
        )
        textures = self._normalize_resources(
            source.get("textures"),
            False,
            provider_id,
            "texture",
        )
        materials = self._normalize_resources(
            source.get("materials"),
            False,
            provider_id,
            "material",
        )
        animations = source.get("animations", [])
        animation_controllers = source.get("animationControllers", [])
        render_controller = source.get("renderController")
        first_person = source.get("firstPerson", False)
        if (
            geometry is None
            or textures is None
            or materials is None
            or not isinstance(animations, list)
            or not isinstance(animation_controllers, list)
            or not _valid_resource_identifier(
                render_controller,
                "controller.render.",
            )
        ):
            return None
        normalized_animations = []
        animation_keys = set()
        for animation in animations:
            if not _only_fields(
                animation,
                ("key", "resource", "state", "layer"),
            ):
                return None
            resource = self._normalize_resource(
                animation,
                provider_id,
                "animation.",
            )
            if (
                resource is None
                or resource["key"] in animation_keys
            ):
                return None
            animation_keys.add(resource["key"])
            state = animation.get("state")
            layer = animation.get("layer")
            if (
                not _is_string(state)
                or not SIMPLE_NAME_RE.match(state)
                or not _is_string(layer)
                or not SIMPLE_NAME_RE.match(layer)
            ):
                return None
            resource["state"] = state
            resource["layer"] = layer
            normalized_animations.append(resource)
        normalized_animation_controllers = []
        controller_keys = set()
        for controller in animation_controllers:
            if not _only_fields(
                controller,
                ("key", "resource", "attach"),
            ):
                return None
            resource = self._normalize_resource(
                controller,
                provider_id,
                "controller.animation.",
            )
            if (
                resource is None
                or resource["key"] in controller_keys
            ):
                return None
            controller_keys.add(resource["key"])
            attach = controller.get("attach")
            if not isinstance(attach, dict):
                return None
            mode = attach.get("mode")
            if mode == "state":
                target_controller = attach.get("controller")
                state = attach.get("state")
                if (
                    not _is_string(target_controller)
                    or not SIMPLE_NAME_RE.match(target_controller)
                    or not _is_string(state)
                    or not SIMPLE_NAME_RE.match(state)
                    or set(attach.keys()) != set((
                        "mode", "controller", "state",
                    ))
                ):
                    return None
                normalized_attach = {
                    "mode": "state",
                    "controller": target_controller,
                    "state": state,
                }
            elif mode == "script_animate":
                auto_replace = attach.get("autoReplace", False)
                if (
                    not isinstance(auto_replace, bool)
                    or set(attach.keys()) - set(("mode", "autoReplace"))
                ):
                    return None
                normalized_attach = {
                    "mode": "script_animate",
                    "autoReplace": bool(auto_replace),
                }
            else:
                return None
            resource["attach"] = normalized_attach
            normalized_animation_controllers.append(resource)
        block = source.get("nativeSlotBlock")
        normalized_block = None
        if block is not None:
            if not _only_fields(block, ("slots", "operator")):
                return None
            slots = _unique_string_list(
                block.get("slots"),
                True,
                lambda value: (
                    _is_string(value) and value in NATIVE_VISUAL_SLOTS
                ),
            )
            operator = block.get("operator")
            if (
                slots is None
                or operator not in ("and", "or")
                or any(slot not in NATIVE_VISUAL_SLOTS for slot in slots)
            ):
                return None
            normalized_block = {"slots": slots, "operator": operator}
        normalized_first_person = first_person
        if isinstance(first_person, dict):
            if not _only_fields(
                first_person,
                (
                    "geometry",
                    "textures",
                    "materials",
                    "renderController",
                ),
                ("animations", "animationControllers"),
            ):
                return None
            first_source = _copy(first_person)
            first_source["visualId"] = visual_id
            normalized_first = self._normalize_visual(
                provider_id,
                first_source,
            )
            if normalized_first is None:
                return None
            normalized_first_person = {
                "geometry": normalized_first["geometry"],
                "textures": normalized_first["textures"],
                "materials": normalized_first["materials"],
                "animations": normalized_first["animations"],
                "animationControllers": normalized_first[
                    "animationControllers"
                ],
                "renderController": normalized_first[
                    "renderController"
                ],
            }
            base_keys = {
                "geometry": set((geometry["key"],)),
                "texture": set(
                    value["key"] for value in textures
                ),
                "material": set(
                    value["key"] for value in materials
                ),
                "animation": set(
                    value["key"] for value in normalized_animations
                ),
                "animation_controller": set(
                    value["key"]
                    for value in normalized_animation_controllers
                ),
            }
            first_keys = {
                "geometry": set((
                    normalized_first_person["geometry"]["key"],
                )),
                "texture": set(
                    value["key"]
                    for value in normalized_first_person["textures"]
                ),
                "material": set(
                    value["key"]
                    for value in normalized_first_person["materials"]
                ),
                "animation": set(
                    value["key"]
                    for value in normalized_first_person["animations"]
                ),
                "animation_controller": set(
                    value["key"]
                    for value in normalized_first_person[
                        "animationControllers"
                    ]
                ),
            }
            if any(
                base_keys[kind].intersection(first_keys[kind])
                for kind in base_keys
            ):
                return None
        elif first_person is not False:
            return None
        entity = self._normalize_entity_visual(provider_id, source.get("entity", {}))
        if entity is None:
            return None
        return {
            "visualId": visual_id,
            "geometry": geometry,
            "textures": textures,
            "materials": materials,
            "animations": normalized_animations,
            "animationControllers": normalized_animation_controllers,
            "renderController": render_controller,
            "nativeSlotBlock": normalized_block,
            "firstPerson": normalized_first_person,
            "providerId": provider_id,
            "entity": entity,
        }

    def _normalize_entity_visual(self, provider_id, source):
        if not _only_fields(source, (), ("enabled", "modelsByEntity", "renderControllersBySlot")):
            return None
        enabled = source.get("enabled", True)
        models = source.get("modelsByEntity", {})
        if (not isinstance(enabled, bool) or not isinstance(models, dict)
                or len(models) > MAX_ENTITY_MODELS_PER_VISUAL):
            return None
        result = {"enabled": enabled, "modelsByEntity": {}}
        if "renderControllersBySlot" in source:
            controllers = self._normalize_entity_render_slots(source["renderControllersBySlot"])
            if controllers is None:
                return None
            result["renderControllersBySlot"] = controllers
        for identifier, model in models.items():
            if not _valid_namespaced_id(identifier) or not _only_fields(model, (), (
                    "geometry", "textures", "materials", "animations", "animationControllers",
                    "renderController", "renderControllersBySlot")):
                return None
            normalized = {}
            for field, value in model.items():
                if field == "geometry":
                    if not _only_fields(value, ("key", "resource")):
                        return None
                    value = self._normalize_resource(value, provider_id, "geometry.")
                elif field in ("textures", "materials"):
                    value = self._normalize_resources(value, False, provider_id,
                        "texture" if field == "textures" else "material")
                elif field in ("animations", "animationControllers"):
                    if not isinstance(value, list):
                        return None
                    entries, keys = [], set()
                    for entry in value:
                        if not _only_fields(entry, ("key", "resource"), ("condition",)):
                            return None
                        resource = self._normalize_resource(entry, provider_id,
                            "animation." if field == "animations" else "controller.animation.")
                        condition = entry.get("condition", "1.0")
                        if (resource is None or resource["key"] in keys
                                or not _is_string(condition) or len(condition) > 512):
                            return None
                        keys.add(resource["key"])
                        resource["condition"] = condition
                        entries.append(resource)
                    value = entries
                elif field == "renderControllersBySlot":
                    value = self._normalize_entity_render_slots(value)
                elif not _valid_resource_identifier(value, "controller.render."):
                    return None
                if value is None:
                    return None
                normalized[field] = value
            result["modelsByEntity"][identifier] = normalized
        return result

    @staticmethod
    def _normalize_entity_render_slots(source):
        if not isinstance(source, dict) or len(source) > MAX_VISUAL_SLOTS_PER_VISUAL:
            return None
        if any(not _valid_namespaced_id(key) or not _valid_resource_identifier(value, "controller.render.")
               for key, value in source.items()):
            return None
        return _copy(source)

    @staticmethod
    def _build_entity_visual_registry(snapshot, errors):
        result = {"registryRevision": 0, "visualsById": {},
                  "attachableEntities": list(snapshot["attachableEntities"])}
        attachable_entities = set(snapshot["attachableEntities"])
        identifiers = set()
        instances = 0
        for visual_id, source in snapshot["visualsById"].items():
            entity = source["entity"]
            if not entity["enabled"]:
                continue
            base = dict((key, _copy(source[key])) for key in (
                "geometry", "textures", "materials", "renderController"))
            base["slotIds"] = list(source["slotIds"])
            base["modelKey"] = "default"
            base["renderControllersBySlot"] = _copy(entity.get("renderControllersBySlot", {}))
            for field in ("animations", "animationControllers"):
                base[field] = [dict(key=entry["key"], resource=entry["resource"], condition="1.0")
                               for entry in source[field]]
            models = {}
            for identifier, override in entity["modelsByEntity"].items():
                model = _copy(base)
                model.update(_copy(override))
                model["modelKey"] = identifier
                models[identifier] = model
            for model in [base] + list(models.values()):
                if not set(model["renderControllersBySlot"]).issubset(set(model["slotIds"])):
                    errors.append("entity_visual_unknown_slot:%s" % visual_id)
                # Distinct resources are necessary for actual simultaneous instances.
                # The native API rejects a second attachment of the same RC name.
                mapping = model["renderControllersBySlot"]
                if mapping and (set(mapping) != set(model["slotIds"])
                                or len(set(mapping.values())) != len(mapping)):
                    errors.append("entity_visual_render_slots_incomplete:%s" % visual_id)
            instances += len(source["slotIds"]) * (1 + len(models))
            identifiers.update(models)
            result["visualsById"][visual_id] = {"default": base, "modelsByEntity": models}
        if instances > MAX_ENTITY_VISUAL_INSTANCES:
            errors.append("entity_visual_instance_budget_exceeded")
        for identifier in [None] + sorted(identifiers):
            aliases = {}
            for visual_id, visual in sorted(result["visualsById"].items()):
                model = visual["modelsByEntity"].get(identifier)
                if model is None:
                    if identifier is not None and identifier not in attachable_entities:
                        continue
                    model = visual["default"]
                resources = [("geometry", [model["geometry"]]), ("texture", model["textures"]),
                             ("material", model["materials"]),
                             ("animate", model["animations"] + [
                                 {"key": "controller__" + entry["key"]}
                                 for entry in model["animationControllers"]]),
                             ("render", [{"key": key} for key in
                              set(model["renderControllersBySlot"].values()) or [model["renderController"]]])]
                for category, entries in resources:
                    local = set()
                    for entry in entries:
                        key = (category, entry["key"])
                        if key in local or key in aliases:
                            errors.append("duplicate_entity_visual_alias:%s:%s:%s" % (
                                identifier or "default", category, entry["key"]))
                        local.add(key)
                        aliases[key] = visual_id
        return result

    @staticmethod
    def _normalize_sound(source):
        if source is None:
            return None
        if _is_string(source):
            source = {"sound": source}
        if not isinstance(source, dict) or not _only_fields(
            source,
            ("sound",),
            ("volume", "pitch"),
        ):
            return None
        sound = source.get("sound")
        volume = source.get("volume", 1.0)
        pitch = source.get("pitch", 1.0)
        if (
            not _is_string(sound)
            or len(sound) > MAX_RESOURCE_PATH_LENGTH
            or not SOUND_EVENT_RE.match(sound)
            or ".." in sound
            or "//" in sound
            or isinstance(volume, bool)
            or not isinstance(volume, NUMBER_TYPES)
            or isinstance(pitch, bool)
            or not isinstance(pitch, NUMBER_TYPES)
            or not 0.0 <= float(volume) <= 4.0
            or not 0.01 <= float(pitch) <= 4.0
        ):
            return None
        return {
            "sound": sound,
            "volume": float(volume),
            "pitch": float(pitch),
        }

    @staticmethod
    def _normalize_resource(source, provider_id, resource_prefix=None):
        if not isinstance(source, dict):
            return None
        key = source.get("key")
        resource = source.get("resource")
        key_prefix = provider_id + "_"
        if (
            not _is_string(key)
            or not RESOURCE_KEY_RE.match(key)
            or not key.startswith(key_prefix)
            or not _valid_resource_identifier(resource, resource_prefix)
        ):
            return None
        return {"key": key, "resource": resource}

    def _normalize_resources(
        self,
        source,
        allow_empty,
        provider_id,
        resource_kind,
    ):
        if not isinstance(source, list) or (not source and not allow_empty):
            return None
        result = []
        keys = set()
        for value in source:
            if not _only_fields(value, ("key", "resource")):
                return None
            if resource_kind == "texture":
                normalized = self._normalize_resource(
                    value,
                    provider_id,
                    "textures/",
                )
                if normalized is not None and not _valid_texture_path(
                    normalized["resource"]
                ):
                    return None
            else:
                normalized = self._normalize_resource(
                    value,
                    provider_id,
                    None,
                )
            if normalized is None or normalized["key"] in keys:
                return None
            keys.add(normalized["key"])
            result.append(normalized)
        return result

    def _budget_usage(self, replacement_id=None, replacement=None):
        providers = dict(self._providers)
        if replacement_id is not None and replacement is not None:
            providers[replacement_id] = replacement
        usage = {
            "providers": len(providers),
            "types": len(CORE_TYPES),
            "pages": 1,
            "slots": len(CORE_SLOTS),
            "items": 0,
            "visuals": 0,
            "visualInstances": sum(
                len(visual.get("slotIds", ()))
                for visual in self._snapshot.get(
                    "visualsById",
                    {},
                ).values()
            ),
            "providerPayloadBytesTotal": 0,
            "largestProviderPayloadBytes": 0,
            "registryPayloadBytes": serialized_size(self._snapshot) or 0,
            "attachableEntities": len(set(VANILLA_ATTACHABLE_ENTITIES).union(
                *(set(provider.get("attachableEntities", ())) for provider in providers.values()))),
            "entityVisualPayloadBytes": serialized_size(self._entity_visual_registry) or 0,
            "entityVisualInstances": sum(
                len(visual["default"]["slotIds"]) * (1 + len(visual["modelsByEntity"]))
                for visual in self._entity_visual_registry["visualsById"].values()),
        }
        for provider in providers.values():
            usage["types"] += len(provider.get("types", ()))
            usage["pages"] += len(provider.get("pages", ()))
            usage["slots"] += sum(
                len(page.get("slots", ()))
                for page in provider.get("pages", ())
            )
            usage["items"] += len(provider.get("items", ()))
            usage["visuals"] += sum(
                1
                for item in provider.get("items", ())
                if item.get("equippedVisual") is not None
            )
            provider_size = serialized_size(provider) or 0
            usage["providerPayloadBytesTotal"] += provider_size
            usage["largestProviderPayloadBytes"] = max(
                usage["largestProviderPayloadBytes"],
                provider_size,
            )
        return usage

    def _fits_total_budget(self, usage):
        return (
            usage["providers"] <= MAX_PROVIDERS
            and usage["types"] <= MAX_TOTAL_TYPES
            and usage["pages"] <= MAX_TOTAL_PAGES
            and usage["slots"] <= MAX_TOTAL_SLOTS
            and usage["items"] <= MAX_TOTAL_ITEMS
            and usage["visuals"] <= MAX_TOTAL_VISUALS
            and usage["attachableEntities"] <= MAX_ATTACHABLE_ENTITIES
        )

    def _build_snapshot(self):
        snapshot = self._empty_snapshot()
        errors = []
        custom_pages = []

        for provider_id in sorted(self._providers.keys()):
            provider = self._providers[provider_id]
            for identifier in provider["attachableEntities"]:
                snapshot["attachableEntitySources"].setdefault(identifier, []).append(provider_id)
            for type_data in provider["types"]:
                type_id = type_data["typeId"]
                if type_id in snapshot["typesById"]:
                    errors.append("duplicate_type:%s" % type_id)
                else:
                    snapshot["typesById"][type_id] = _copy(type_data)
            custom_pages.extend(_copy(provider["pages"]))

        item_accumulator = {}
        for provider_id in sorted(self._providers.keys()):
            for item in self._providers[provider_id]["items"]:
                item_id = item["itemId"]
                target = item_accumulator.setdefault(item_id, {
                    "itemId": item_id,
                    "types": set(),
                    "equipOnUse": False,
                    "sources": [],
                    "equipOnUseSources": [],
                    "quickEquipDecisionSources": [],
                    "equippedVisual": None,
                    "equipSound": None,
                    "quickEquipSound": None,
                })
                target["types"].update(item["types"])
                target["sources"].append(provider_id)
                if item["equipOnUse"]:
                    target["equipOnUse"] = True
                    target["equipOnUseSources"].append(provider_id)
                if item["quickEquipDecision"]:
                    target["quickEquipDecisionSources"].append(provider_id)
                visual = item.get("equippedVisual")
                if visual is not None:
                    if target["equippedVisual"] is None:
                        target["equippedVisual"] = _copy(visual)
                    elif target["equippedVisual"] != visual:
                        errors.append("visual_conflict:%s" % item_id)
                for field, error_prefix in (
                    ("equipSound", "equip_sound_conflict"),
                    ("quickEquipSound", "quick_equip_sound_conflict"),
                ):
                    sound = item.get(field)
                    if sound is None:
                        continue
                    if target[field] is None:
                        target[field] = _copy(sound)
                    elif target[field] != sound:
                        errors.append("%s:%s" % (error_prefix, item_id))

        snapshot["attachableEntities"] = sorted(snapshot["attachableEntitySources"])
        referenced_core_types = set()
        for item_id in sorted(item_accumulator.keys()):
            value = item_accumulator[item_id]
            type_ids = sorted(value["types"])
            unknown = [
                type_id for type_id in type_ids
                if type_id not in snapshot["typesById"]
            ]
            if unknown:
                errors.append("unknown_item_type:%s:%s" % (
                    item_id,
                    ",".join(unknown),
                ))
                continue
            referenced_core_types.update(
                type_id for type_id in type_ids
                if type_id.startswith("chatelaine:")
            )
            visual = value["equippedVisual"]
            visual_id = None
            if visual is not None:
                visual_id = visual["visualId"]
                existing = snapshot["visualsById"].get(visual_id)
                if existing is not None and existing != visual:
                    errors.append("duplicate_visual:%s" % visual_id)
                else:
                    snapshot["visualsById"][visual_id] = _copy(visual)
            snapshot["itemTypesByItemId"][item_id] = type_ids
            snapshot["itemsById"][item_id] = {
                "itemId": item_id,
                "types": type_ids,
                "equipOnUse": bool(value["equipOnUse"]),
                "equipOnUseSources": sorted(value["equipOnUseSources"]),
                "quickEquipDecisionSources": sorted(
                    value["quickEquipDecisionSources"]
                ),
                "equippedVisualId": visual_id,
                "equipSound": _copy(value["equipSound"]),
                "quickEquipSound": _copy(value["quickEquipSound"]),
                "sources": sorted(value["sources"]),
            }

        core_slots = []
        for slot in CORE_SLOTS:
            if any(
                type_id in referenced_core_types
                for type_id in slot["acceptedTypes"]
            ):
                core_slots.append(_copy(slot))

        active_pages = []
        if core_slots:
            page = _copy(CORE_PAGE)
            page["slotIds"] = [slot["slotId"] for slot in core_slots]
            active_pages.append(page)
            for slot in core_slots:
                snapshot["slotsById"][slot["slotId"]] = slot

        for page in custom_pages:
            slot_ids = []
            for slot in page["slots"]:
                unknown = [
                    type_id for type_id in slot["acceptedTypes"]
                    if type_id not in snapshot["typesById"]
                ]
                if unknown:
                    errors.append("unknown_slot_type:%s:%s" % (
                        slot["slotId"],
                        ",".join(unknown),
                    ))
                    continue
                if slot["slotId"] in snapshot["slotsById"]:
                    errors.append("duplicate_slot:%s" % slot["slotId"])
                    continue
                snapshot["slotsById"][slot["slotId"]] = _copy(slot)
                slot_ids.append(slot["slotId"])
            page_data = dict(
                (key, _copy(value))
                for key, value in page.items()
                if key != "slots"
            )
            page_data["slotIds"] = slot_ids
            active_pages.append(page_data)

        page_ids = set()
        for page in active_pages:
            if page["pageId"] in page_ids:
                errors.append("duplicate_page:%s" % page["pageId"])
            page_ids.add(page["pageId"])
        active_pages.sort(key=lambda page: (page["order"], page["pageId"]))
        snapshot["pages"] = active_pages
        self._attach_visual_slots(snapshot, errors)
        self._validate_visual_aliases(snapshot, errors)
        return snapshot, sorted(set(errors))

    @staticmethod
    def _attach_visual_slots(snapshot, errors):
        visual_types = dict(
            (visual_id, set())
            for visual_id in snapshot["visualsById"]
        )
        for item in snapshot["itemsById"].values():
            visual_id = item.get("equippedVisualId")
            if visual_id in visual_types:
                visual_types[visual_id].update(item.get("types", ()))

        query_owners = {}
        total_instances = 0
        for visual_id in sorted(snapshot["visualsById"]):
            type_ids = visual_types.get(visual_id, set())
            slot_ids = []
            for slot_id in sorted(snapshot["slotsById"]):
                accepted = set(
                    snapshot["slotsById"][slot_id].get(
                        "acceptedTypes",
                        (),
                    )
                )
                if not accepted.intersection(type_ids):
                    continue
                query_name = visual_slot_query_name(visual_id, slot_id)
                if len(query_name) > MAX_QUERY_NAME_LENGTH:
                    errors.append(
                        "visual_query_too_long:%s:%s" % (
                            visual_id,
                            slot_id,
                        )
                    )
                    continue
                owner = query_owners.get(query_name)
                current = (visual_id, slot_id)
                if owner is not None and owner != current:
                    errors.append(
                        "duplicate_visual_query:%s" % query_name
                    )
                    continue
                query_owners[query_name] = current
                slot_ids.append(slot_id)
            if len(slot_ids) > MAX_VISUAL_SLOTS_PER_VISUAL:
                errors.append(
                    "visual_slot_budget_exceeded:%s" % visual_id
                )
            total_instances += len(slot_ids)
            snapshot["visualsById"][visual_id]["slotIds"] = slot_ids
        if total_instances > MAX_TOTAL_VISUAL_INSTANCES:
            errors.append("visual_instance_budget_exceeded")

    @staticmethod
    def _validate_visual_aliases(snapshot, errors):
        """Reject aliases shared by distinct visuals before client injection.

        ActorRender additions mutate one global player client entity.  Even an
        identical duplicate would make injection order an engine-side concern,
        so every category/key pair has one owning visual in a frozen registry.
        """
        aliases = {}
        for visual_id in sorted(snapshot["visualsById"].keys()):
            visual = snapshot["visualsById"][visual_id]
            resources = (
                ("geometry", (visual.get("geometry"),)),
                ("texture", visual.get("textures", ())),
                ("material", visual.get("materials", ())),
                ("animation", visual.get("animations", ())),
                (
                    "animation_controller",
                    visual.get("animationControllers", ()),
                ),
            )
            first_person = visual.get("firstPerson")
            if isinstance(first_person, dict):
                resources += (
                    ("geometry", (first_person.get("geometry"),)),
                    ("texture", first_person.get("textures", ())),
                    ("material", first_person.get("materials", ())),
                    ("animation", first_person.get("animations", ())),
                    (
                        "animation_controller",
                        first_person.get("animationControllers", ()),
                    ),
                )
            for category, entries in resources:
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    key = entry.get("key")
                    owner_key = (category, key)
                    owner = aliases.get(owner_key)
                    if owner is not None and owner != visual_id:
                        errors.append(
                            "duplicate_visual_alias:%s:%s" % (
                                category,
                                key,
                            )
                        )
                    else:
                        aliases[owner_key] = visual_id

    def _safe_item_exists(self, item_id):
        try:
            return bool(self._item_exists(item_id))
        except Exception:
            return False

    def _is_contract_value(self, value, depth):
        if depth > MAX_DATA_NESTING:
            return False
        if value is None or isinstance(
            value,
            (bool,) + INTEGER_TYPES + (float,) + STRING_TYPES,
        ):
            return True
        if isinstance(value, list):
            return all(
                self._is_contract_value(element, depth + 1)
                for element in value
            )
        if isinstance(value, dict):
            return all(
                isinstance(key, STRING_TYPES)
                and self._is_contract_value(element, depth + 1)
                for key, element in value.items()
            )
        return False
