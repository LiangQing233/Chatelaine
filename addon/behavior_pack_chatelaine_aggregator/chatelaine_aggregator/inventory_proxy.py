# -*- coding: utf-8 -*-
"""Script-owned Chatelaine page embedded in the native inventory screen.

The native inventory and creative catalogue are never inspected or given
callbacks.  While the Chatelaine page is active their top-level controls are
hidden and disabled; script-bound replica grids render authoritative item
snapshots and submit all mutations to the server.
"""

import copy
import math

import mod.client.extraClientApi as clientApi

from chatelaine_aggregator.grid_layout import (
    EXPANDED_GRID_CAPACITY,
    cell_to_logical_slot,
    logical_slot_to_cell,
)
from chatelaine_aggregator.ui_lifecycle import advance_stable_signature


NAMESPACE = "chatelaine_api"
CLIENT_SYSTEM_NAME = "ChatelaineClientSystem"
CURIO_INVENTORY_POCKET_SCREEN = "crafting_pocket.inventory_screen_pocket"


CustomUIScreenProxy = clientApi.GetUIScreenProxyCls()
ViewBinder = clientApi.GetViewBinderCls()

NETWORK_RETRY_TICKS = 100
FLY_ANIMATION_TICKS = 5
CLASSIC_LEGACY_SPLIT_SIZE = (15.0, 3.0)
POCKET_TOUCH_LEGACY_SPLIT_SIZE = (24.0, 2.0)
MOUSE_SPLIT_FILL_TICKS = 32
TOUCH_SPLIT_PIXELS_PER_ITEM = 1.0
TOUCH_SPLIT_REVERSE_HYSTERESIS = 0.5
POCKET_NAVIGATION_STABLE_SAMPLES = 3
CLASSIC_HELD_ITEM_SIZE = (20.0, 20.0)
POCKET_HELD_ITEM_SIZE = (28.0, 28.0)
_SCREEN_ROOT = (
    "/variables_button_mappings_and_controls/safezone_screen_matrix/"
    "inner_matrix/safezone_screen_panel/root_screen_panel"
)
_CLASSIC_INVENTORY = _SCREEN_ROOT + "/content_stack_panel/player_inventory"
_CLASSIC_CRAFTING_PANEL = (
    _CLASSIC_INVENTORY + "/inventory_panel_top_half/crafting_panel"
)
_CLASSIC_CONTENT_STACK = _SCREEN_ROOT + "/content_stack_panel"
_CLASSIC_CATEGORY_CONTENT = (
    _CLASSIC_CONTENT_STACK
    + "/recipe_book/tab_navigation_panel/navigation_tabs/content"
)
_CLASSIC_TOOLBAR_STACK = (
    _CLASSIC_CONTENT_STACK
    + "/toolbar_anchor/toolbar_panel/toolbar_background/toolbar_stack_panel"
)
CLASSIC_PARENT_PATH = (
    _CLASSIC_INVENTORY
    + "/inventory_panel_top_half/player_armor_panel"
)
CLASSIC_ARMOR_PATH = CLASSIC_PARENT_PATH + "/armor_grid"
CLASSIC_OFFHAND_PATH = CLASSIC_PARENT_PATH + "/offhand_grid"
CLASSIC_ROOT_PATH = CLASSIC_PARENT_PATH + "/chatelaine_root"
CLASSIC_REPLICA_PATH = _CLASSIC_INVENTORY + "/chatelaine_replica"
CLASSIC_OVERLAY_PATH = _SCREEN_ROOT + "/chatelaine_overlay"
CLASSIC_INVENTORY_TOGGLE_PATH = (
    _CLASSIC_TOOLBAR_STACK
    + "/survival_layout_toggle_panel/survival_layout_toggle"
)
CLASSIC_CREATIVE_TOGGLE_PATH = (
    _CLASSIC_TOOLBAR_STACK
    + "/creative_layout_toggle_panel/creative_layout_toggle"
)
CLASSIC_LAYOUT_TOGGLE_PATHS = (
    _CLASSIC_TOOLBAR_STACK
    + "/mount_tab_layout_toggle_panel/mount_layout_toggle",
    _CLASSIC_TOOLBAR_STACK
    + "/parterner_tab_layout_toggle_panel/parterner_layout_toggle",
    CLASSIC_CREATIVE_TOGGLE_PATH,
    _CLASSIC_TOOLBAR_STACK
    + "/recipe_book_layout_toggle_panel_survival/recipe_book_layout_toggle",
    _CLASSIC_TOOLBAR_STACK
    + "/recipe_book_layout_toggle_panel_creative/recipe_book_layout_toggle",
    CLASSIC_INVENTORY_TOGGLE_PATH,
)

_POCKET_BASE = _SCREEN_ROOT + "/base_panel"
_POCKET_HELPER = _POCKET_BASE + "/hotbar_and_panels/gamepad_helper_border"
_POCKET_BOTH = _POCKET_HELPER + "/both_panels"
POCKET_PARENT_PATH = (
    _POCKET_BOTH
    + "/right_panel/armor_tab_content/content/"
    + "equipment_and_renderer/armor_panel"
)
POCKET_ARMOR_PATH = (
    _POCKET_BOTH
    + "/right_panel/armor_tab_content/content/"
    + "equipment_and_renderer/equipment/armor_grid"
)
POCKET_OFFHAND_PATH = (
    _POCKET_BOTH
    + "/right_panel/armor_tab_content/content/"
    + "equipment_and_renderer/equipment/offhand_grid"
)
POCKET_ROOT_PATH = POCKET_PARENT_PATH + "/chatelaine_root"
POCKET_REPLICA_PATH = (
    _POCKET_BASE
    + "/hotbar_and_panels/hotbar_section_panel/chatelaine_replica"
)
POCKET_OVERLAY_PATH = _SCREEN_ROOT + "/chatelaine_overlay"
POCKET_BAG_PATH = _POCKET_BOTH + "/left_panel/chatelaine_bag"
POCKET_ARMOR_TAB_PATH = _POCKET_BOTH + "/right_panel/armor_tab_content"
POCKET_ARMOR_NAV_TAB_PATH = (
    _POCKET_BOTH + "/right_tab_navigation_panel_pocket/content/armor_tab"
)
POCKET_ARMOR_NAV_TOGGLE_PATH = (
    POCKET_ARMOR_NAV_TAB_PATH + "/armor_tab_toggle"
)
POCKET_NATIVE_SELECTION_PROBE_PATH = (
    _SCREEN_ROOT + "/chatelaine_native_selection_probe"
)
POCKET_INVENTORY_TAB_PATH = (
    _POCKET_BOTH + "/left_panel/inventory_tab_content"
)
POCKET_RECIPE_CONTENT_PATH = (
    _POCKET_BOTH
    + "/left_panel/recipe_book_tab_content/tab_content_search_bar_panel"
)
POCKET_INVENTORY_CONTENT_PATH = (
    POCKET_INVENTORY_TAB_PATH + "/tab_content_search_bar_panel"
)
POCKET_INVENTORY_TOGGLE_PATH = (
    _POCKET_BOTH
    + "/left_tab_navigation_panel_pocket/content/inventory_tab"
)
_POCKET_LEFT_NAVIGATION = (
    _POCKET_BOTH + "/left_tab_navigation_panel_pocket"
)
_POCKET_LEFT_NAVIGATION_CONTENT = (
    _POCKET_LEFT_NAVIGATION + "/content"
)
POCKET_LEFT_NAVIGATION_KEEP_CHILDREN = frozenset(("inventory_tab", "fill"))
POCKET_CREATIVE_TOGGLE_ROOT_PATHS = (
    _POCKET_LEFT_NAVIGATION_CONTENT + "/search_tab_panel",
    _POCKET_LEFT_NAVIGATION_CONTENT + "/construction_tab_panel",
    _POCKET_LEFT_NAVIGATION_CONTENT + "/equipment_tab_panel",
    _POCKET_LEFT_NAVIGATION_CONTENT + "/items_tab_panel",
    _POCKET_LEFT_NAVIGATION_CONTENT + "/nature_tab_panel",
)
POCKET_NATIVE_HOTBAR_SECTION_PATH = (
    _POCKET_BASE + "/hotbar_and_panels/hotbar_section_panel"
)
POCKET_NATIVE_HOTBAR_PATH = POCKET_NATIVE_HOTBAR_SECTION_PATH + "/hotbar"
POCKET_NATIVE_SELECTED_GRID_PATHS = (
    (
        _POCKET_BOTH
        + "/left_panel/inventory_tab_content/"
        + "tab_content_search_bar_panel/scroll_pane/scroll_mouse/"
        + "scroll_view/stack_panel/background_and_viewport/"
        + "scrolling_view_port/scrolling_content/grid"
    ),
    POCKET_NATIVE_HOTBAR_PATH + "/hotbar_grid",
    (
        _POCKET_BOTH
        + "/right_panel/crafting_tab_content/content/"
        + "crafting_panel/crafting_grid_2x2"
    ),
    (
        _POCKET_BOTH
        + "/right_panel/crafting_tab_content/content/output/output_grid"
    ),
)
CLASSIC_PLAYER_DOLL_PATHS = (
    CLASSIC_PARENT_PATH + "/player_bg",
    CLASSIC_PARENT_PATH + "/player_preview_border",
)
POCKET_PLAYER_DOLL_PATHS = (
    POCKET_PARENT_PATH + "/armor_and_player",
)


def _is_int(value):
    return type(value).__name__ in ("int", "long")


def _item_name(item):
    if type(item).__name__ != "dict":
        return None
    return item.get("newItemName") or item.get("itemName")


def _item_count(item):
    if not _item_name(item):
        return 0
    value = item.get("count", 1)
    return max(0, int(value)) if _is_int(value) else 1


def _item_aux(item):
    if type(item).__name__ != "dict":
        return 0
    value = item.get("newAuxValue", item.get("auxValue", 0))
    return int(value) if _is_int(value) else 0


def _copy_client_stack(item, count):
    if type(item).__name__ != "dict" or int(count) <= 0:
        return {}
    result = copy.deepcopy(item)
    result["count"] = int(count)
    return result


def _normalized_item_value(value):
    """Canonicalize network containers before comparing item metadata."""
    value_type = type(value).__name__
    if value_type == "dict":
        return tuple(sorted(
            (key, _normalized_item_value(child))
            for key, child in value.items()
        ))
    if value_type in ("list", "tuple"):
        return tuple(_normalized_item_value(child) for child in value)
    return value


def _item_lock_mode(item):
    """Normalize only Bedrock's two real native item-lock values.

    Some NetEase builds expose the semantic field as ``itemLockMode`` while
    ``GetPlayerItem(..., True)`` exposes the same native component only as the
    typed-NBT ``userData['minecraft:item_lock']`` byte.  Reading that exact
    native key is not a generic "has userData" test: unrelated NBT must never
    create a lock overlay.
    """
    if type(item).__name__ != "dict":
        return None
    value = item.get("itemLockMode")
    if value is None:
        user_data = item.get("userData")
        if type(user_data).__name__ == "dict":
            native_value = user_data.get("minecraft:item_lock")
            if type(native_value).__name__ == "dict":
                value = native_value.get("__value__")
            else:
                value = native_value
    if (_is_int(value) and int(value) == 1) or value in (
        "slot", "lock_in_slot"
    ):
        return "lock_in_slot"
    if (_is_int(value) and int(value) == 2) or value in (
        "inventory", "lock_in_inventory"
    ):
        return "lock_in_inventory"
    return None


class InventoryChatelaineScreenProxy(CustomUIScreenProxy):
    _destroyed = False
    def __init__(self, screenName, screenNode):
        self._destroyed = False
        CustomUIScreenProxy.__init__(self, screenName, screenNode)
        self.screen_name = screenName
        self.screen_node = screenNode
        self.client_system = None
        self.root_path = None
        self.replica_path = None
        self.bag_path = None
        self.overlay_path = None
        self.root_control = None
        self.replica_control = None
        self.overlay_control = None
        self.armor_grid = None
        self.offhand_grid = None
        self.native_states = {}
        self.native_size_states = {}
        self.inventory_items = [{} for _index in range(36)]
        self.inventory_bag = []
        self.inventory_hotbar = []
        self.curio_items = []
        self.curio_slot_ids = []
        self.curio_empty_textures = []
        self.curio_layout = "compact"
        self.curio_slot_models = []
        self.curio_slots = []
        self.selection = None
        self.split_state = None
        self.press_state = None
        self.drag_state = None
        # A completed distribution keeps its last deterministic client image
        # until the matching authoritative snapshot arrives.  This is not an
        # active gesture: it only bridges the request/response render gap.
        self.committed_drag_preview = None
        self.pending = None
        self.pending_ticks = 0
        self.tick_count = 0
        self.last_click = None
        self.shift_quick_suppress_until = -1
        self.quick_move_pressed = None
        self.next_distribution_id = 1
        self.render_dirty = True
        self.bound_buttons = {}
        self.bound_button_slots = {}
        self.prepared_slot_paths = set()
        self.replica_buttons_complete = False
        self.applied_state_version = -1
        self.created = False
        self.curio_session_claimed = False
        self.curio_open_wait_ticks = 0
        self.fly_state = None
        self.fly_target_override = None
        self.inventory_dirty_ticks = 0
        self.touch_hover_text = ""
        self.held_lock_in_inventory = False
        self.held_lock_in_slot = False
        self.held_durability_visible = False
        self.held_durability_total = 1
        self.held_durability_current = 1
        # Hidden JSON UI panels report (0, 0) from GetSize even though their
        # configured size is nonzero. Keep the held renderer hidden until its
        # fixed profile size has been used in a completed position pass.
        self.held_item_active = False
        self.held_item_reveal_tick = None
        self.touch_details_token = None
        self.touch_gesture_position = None
        self.quick_move_pressed = None
        self.split_direction = "down"
        self.split_ratio = 0.0
        self.split_render_direction = None
        self.split_render_progress = None
        self.legacy_progress_total = 1
        self.legacy_progress_current = 0
        self.inventory_layout_forced = False
        self.pocket_inventory_switch_tick = None
        self.classic_toolbar_collapse_complete = False
        self.chatelaine_page_active = False
        self.chatelaine_controls_active = False
        self.applied_curio_layout = None
        self.applied_player_doll_visible = None
        self.native_inventory_exit_request_id = None
        self.native_inventory_exit_pending = False
        self.page_transition_request_id = None
        self.page_transition_target = None
        self.page_transition_ticks = 0
        self.pocket_exit_inventory_reselect = False
        self.pocket_exit_restore_states = {}
        self.pocket_left_child_states = {}
        self.pocket_grid_mouse_mode = None
        self.pocket_grid_position_applied = False
        self.pocket_bag_layout_signature = None
        self.pocket_overlay_cursor_return_pending = False
        self.pocket_navigation_signature = None
        self.pocket_navigation_stable_samples = 0
        self.pocket_navigation_ready = False
        self._max_stack_cache = {}
        self._item_basic_info_cache = {}
        self._hover_text_cache = {}
        self._switch_toggle_paths = {}
        self.chatelaine_toggle_available = None
        self.chatelaine_toggle_interactable = None
        self.pocket_armor_entry_interactable = None
        self.native_selected_marker_paths = []
        self.native_selected_marker_scan_tick = -100

    def OnCreate(self):
        if self._destroyed:
            return
        self._attach_client_system()
        self._create_controls()
        self._ensure_curio_session()

    def OnTick(self):
        if self._destroyed:
            return
        self.tick_count += 1
        if self.client_system is None:
            self._attach_client_system()
        if not self.created:
            self._create_controls()
        if (
            not self.curio_session_claimed
            or (
                self.client_system is not None
                and self._client_state().get("sessionId")
                is None
            )
        ):
            self._ensure_curio_session()
        if not self.created or self.client_system is None:
            return
        self._observe_pocket_navigation_tree()
        if self.pocket_exit_inventory_reselect:
            # Pocket's global left-tab binding settles after the page edge.
            # Reassert exactly once on the following tick instead of polling
            # or rewriting the native Toggle on every stable frame. Keeping
            # this before Refresh also guarantees a Refresh discovered by
            # this tick cannot consume its own deferred reassertion.
            self.pocket_exit_inventory_reselect = False
            self._select_inventory_layout()
            self._restore_pocket_exit_controls()
        if self.applied_state_version != self._client_state_version():
            self.RefreshCurioState()
        self._apply_toggle_availability()
        self._apply_pocket_armor_entry_availability()
        self._maintain_page_controls()
        self._continue_pocket_overlay_cursor_return()
        self._tick_inventory_dirty()
        if self.chatelaine_controls_active:
            if not self.replica_buttons_complete:
                self._bind_replica_buttons()
            if self.render_dirty:
                self._render_all_items()
            self._refresh_pocket_static_hover_text()
        self._tick_pending()
        self._tick_page_transition()
        self._tick_press_state()
        self._tick_fly()
        held_positioned = self._update_held_item_position()
        self._tick_held_item_reveal(held_positioned)

    def OnDestroy(self):
        self._destroyed = True
        if self.client_system is not None and self.curio_session_claimed:
            # Release ownership before closing. A replacement native proxy may
            # already have claimed the same live session; an old proxy must not
            # clear that replacement's awaiting-open/current-session state.
            if self.client_system.SetActiveChatelaineInventoryProxy(None, self):
                self.client_system.CloseCurioInventory()
        self.client_system = None
        self.screen_node = None
        self.root_control = None
        self.replica_control = None
        self.overlay_control = None
        self.armor_grid = None
        self.offhand_grid = None
        self.bound_buttons = {}
        self.bound_button_slots = {}
        self.prepared_slot_paths = set()
        self.replica_buttons_complete = False
        self.selection = None
        self.split_state = None
        self.press_state = None
        self.drag_state = None
        self.committed_drag_preview = None
        self.pending = None
        self.fly_state = None
        self.fly_target_override = None
        self.touch_details_token = None
        self.touch_gesture_position = None
        self.held_item_active = False
        self.held_item_reveal_tick = None
        self.inventory_layout_forced = False
        self.pocket_inventory_switch_tick = None
        self.classic_toolbar_collapse_complete = False
        self.chatelaine_page_active = False
        self.chatelaine_controls_active = False
        self.applied_curio_layout = None
        self.applied_player_doll_visible = None
        self.native_size_states = {}
        self.native_states = {}
        self.native_inventory_exit_request_id = None
        self.native_inventory_exit_pending = False
        self.page_transition_request_id = None
        self.page_transition_target = None
        self.page_transition_ticks = 0
        self.pocket_exit_inventory_reselect = False
        self.pocket_exit_restore_states = {}
        self.pocket_left_child_states = {}
        self.pocket_grid_mouse_mode = None
        self.pocket_grid_position_applied = False
        self.pocket_bag_layout_signature = None
        self.pocket_overlay_cursor_return_pending = False
        self.pocket_navigation_signature = None
        self.pocket_navigation_stable_samples = 0
        self.pocket_navigation_ready = False
        self.curio_session_claimed = False
        self.curio_open_wait_ticks = 0
        self._switch_toggle_paths = {}
        self.chatelaine_toggle_available = None
        self.chatelaine_toggle_interactable = None
        self.pocket_armor_entry_interactable = None
        self.native_selected_marker_paths = []
        self.native_selected_marker_scan_tick = -100

    def _attach_client_system(self):
        if self.client_system is None:
            current = clientApi.GetSystem(NAMESPACE, CLIENT_SYSTEM_NAME)
            if current is not None and not getattr(current, "_destroyed", False):
                self.client_system = current

    def _client_state(self):
        if self.client_system is None:
            return {}
        state = self.client_system.GetCurioInventoryState()
        return state if type(state).__name__ == "dict" else {}

    def _client_state_version(self):
        if self.client_system is None:
            return -1
        value = self.client_system.GetCurioInventoryStateVersion()
        return int(value) if _is_int(value) else -1

    def _client_awaiting_open(self):
        if self.client_system is None:
            return False
        return bool(self.client_system.IsCurioInventoryAwaitingOpen())

    def _ensure_curio_session(self):
        """Claim the client session once after both system and controls exist."""
        if not self.created or self.client_system is None:
            return
        if not self.curio_session_claimed:
            if not self.client_system.SetActiveChatelaineInventoryProxy(self):
                return
            self.curio_session_claimed = True
        self.client_system.EnsureCurioInventorySession()

    def _create_controls(self):
        if self.created or self.screen_node is None:
            return
        pocket = self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
        self.root_path = POCKET_ROOT_PATH if pocket else CLASSIC_ROOT_PATH
        self.replica_path = (
            POCKET_REPLICA_PATH if pocket else CLASSIC_REPLICA_PATH
        )
        self.bag_path = POCKET_BAG_PATH if pocket else self.replica_path
        self.overlay_path = POCKET_OVERLAY_PATH if pocket else CLASSIC_OVERLAY_PATH
        armor_path = POCKET_ARMOR_PATH if pocket else CLASSIC_ARMOR_PATH
        offhand_path = POCKET_OFFHAND_PATH if pocket else CLASSIC_OFFHAND_PATH
        self.root_control = self.screen_node.GetBaseUIControl(self.root_path)
        self.replica_control = self.screen_node.GetBaseUIControl(
            self.replica_path
        )
        self.overlay_control = self.screen_node.GetBaseUIControl(
            self.overlay_path
        )
        self.armor_grid = self.screen_node.GetBaseUIControl(armor_path)
        self.offhand_grid = self.screen_node.GetBaseUIControl(offhand_path)
        if (
            self.root_control is None
            or self.replica_control is None
            or self.overlay_control is None
            or self.armor_grid is None
        ):
            return
        self.created = True
        self._apply_toggle_availability()

    def _apply_toggle_availability(self):
        if not self.created or self.screen_node is None:
            return
        available = bool(self._client_state().get("pageCount", 0) > 0)
        interactable = bool(
            available and not self._native_selection_active()
        )
        if (
            available == self.chatelaine_toggle_available
            and interactable == self.chatelaine_toggle_interactable
        ):
            return
        toggle = self.screen_node.GetBaseUIControl(self.root_path + "/toggle")
        if toggle is None:
            return
        toggle.SetVisible(available)
        toggle.SetTouchEnable(interactable)
        self.chatelaine_toggle_available = available
        self.chatelaine_toggle_interactable = interactable

    def _native_selection_active(self):
        """Read native mouse-held and touch-selected state without mutation."""
        screen = getattr(self, "screen_node", None)
        root_path = getattr(self, "root_path", None)
        if screen is None or not root_path:
            return False
        probe_paths = [root_path + "/native_selection_probe"]
        if getattr(self, "screen_name", None) == CURIO_INVENTORY_POCKET_SCREEN:
            # The embedded probe is below armor_tab_content and therefore has
            # a hidden ancestor while crafting/other right tabs are active.
            # This zero-sized sibling of base_panel remains readable on every
            # right tab and does not alter the native navigation tree.
            probe_paths.insert(0, POCKET_NATIVE_SELECTION_PROBE_PATH)
        for probe_path in probe_paths:
            probe = screen.GetBaseUIControl(probe_path)
            if probe is not None and probe.GetVisible():
                return True
        return self._native_touch_selection_active()

    def _apply_pocket_armor_entry_availability(self):
        """Block only entry into an already-open Chatelaine armor page.

        Never change Toggle state or navigation membership.  In particular,
        armor stays interactive while it is the active right tab so leaving
        it can run the existing Chatelaine cursor/selection handoff.
        """
        if (
            not self.created
            or self.screen_node is None
            or self.screen_name != CURIO_INVENTORY_POCKET_SCREEN
        ):
            return
        entering_open_chatelaine = bool(
            self._chatelaine_page_selected()
            and not self._pocket_armor_tab_visible()
        )
        interactable = bool(
            not entering_open_chatelaine or not self._native_selection_active()
        )
        if interactable == self.pocket_armor_entry_interactable:
            return
        armor_toggle = self.screen_node.GetBaseUIControl(
            POCKET_ARMOR_NAV_TOGGLE_PATH
        )
        if armor_toggle is None:
            return
        # MCDK runtime inspection confirms armor_tab is only a Panel; the
        # actual navigation input receiver is its direct armor_tab_toggle.
        # Disable that Toggle exactly like the real Chatelaine Button, without
        # changing its selected state, group, index, visibility or tree.
        armor_toggle.SetTouchEnable(interactable)
        self.pocket_armor_entry_interactable = interactable

    def _native_touch_selection_active(self):
        """Inspect native slot highlight controls, excluding Chatelaine replicas."""
        screen = getattr(self, "screen_node", None)
        get_children = getattr(screen, "GetChildrenName", None)
        if screen is None or not callable(get_children):
            return False
        tick = int(getattr(self, "tick_count", 0))
        paths = getattr(self, "native_selected_marker_paths", [])
        last_scan = int(getattr(
            self,
            "native_selected_marker_scan_tick",
            -100,
        ))
        if not paths or tick - last_scan >= 20:
            paths = self._discover_native_selected_markers()
            self.native_selected_marker_paths = paths
            self.native_selected_marker_scan_tick = tick
        for path in paths:
            control = screen.GetBaseUIControl(path)
            if control is not None and control.GetVisible():
                return True
        return False

    def _discover_native_selected_markers(self):
        screen = getattr(self, "screen_node", None)
        get_children = getattr(screen, "GetChildrenName", None)
        if screen is None or not callable(get_children):
            return []
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            # MCDK runtime inspection confirms GetChildrenName returns the
            # direct short slot names here, and item_selected_image is a
            # direct child of each native container slot.  Enumerating these
            # four real item grids avoids the old 2,048-node whole-screen BFS,
            # which stopped before reaching Pocket's left inventory grid.
            markers = []
            for grid_path in POCKET_NATIVE_SELECTED_GRID_PATHS:
                for slot_name in get_children(grid_path) or ():
                    marker_path = (
                        grid_path + "/" + slot_name + "/item_selected_image"
                    )
                    if screen.GetBaseUIControl(marker_path) is not None:
                        markers.append(marker_path)
            return markers
        root = _POCKET_BASE if (
            self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
        ) else _CLASSIC_INVENTORY
        pending = [(root, 0)]
        markers = []
        visited = 0
        while pending and visited < 2048:
            path, depth = pending.pop(0)
            visited += 1
            for child_name in get_children(path) or ():
                child_path = path + "/" + child_name
                if child_name == "item_selected_image":
                    markers.append(child_path)
                    continue
                if depth < 16 and "/chatelaine_" not in child_path:
                    pending.append((child_path, depth + 1))
        return markers

    def RefreshCurioState(self):
        if not self.created or self.client_system is None:
            return
        state = self._client_state()
        pending_operation = self.pending
        state_request_id = state.get("requestId", 0)
        pending_request_id = (
            pending_operation.get("requestId")
            if pending_operation is not None else None
        )
        pending_response = bool(
            pending_operation is not None
            and _is_int(state_request_id)
            and _is_int(pending_request_id)
            and int(state_request_id) == int(pending_request_id)
        )
        pending_superseded = bool(
            pending_operation is not None
            and _is_int(state_request_id)
            and _is_int(pending_request_id)
            and int(state_request_id) > int(pending_request_id)
        )
        old_pending = pending_operation if pending_response else None
        self._play_authoritative_drop_swing(old_pending, state)
        queued_cursor_collect = bool(
            old_pending is not None
            and old_pending.get("action") == "cursor_pick"
            and old_pending.get("queuedDoubleClick")
            and state.get("result") == "ok"
        )
        if old_pending is not None or pending_superseded:
            # The inventory copied below is now the image that replaces a
            # committed drag preview.  Clear the bridge in the same refresh,
            # immediately before rebuilding DTOs, so no stale frame is drawn.
            self.committed_drag_preview = None
        self.applied_state_version = self._client_state_version()
        inventory = state.get("inventory")
        if type(inventory).__name__ == "list" and len(inventory) == 36:
            self.inventory_items = [
                copy.deepcopy(item) if type(item).__name__ == "dict" else {}
                for item in inventory
            ]
        elif state.get("sessionId") is not None:
            # Server snapshots are all-or-nothing. Retaining the preceding
            # 36-slot image here would make stale items appear actionable.
            self.inventory_items = [{} for _index in range(36)]
        slots = [
            entry for entry in (state.get("slots") or ())
            if type(entry).__name__ == "dict" and entry.get("slotId")
        ]
        next_slot_ids = [entry.get("slotId") for entry in slots]
        next_layout = state.get("layout", "compact")
        if self.selection is not None and self.selection.get("domain") == "curio":
            selected_index = int(self.selection.get("slot", -1))
            old_slot_id = (
                self.curio_slot_ids[selected_index]
                if 0 <= selected_index < len(self.curio_slot_ids)
                else None
            )
            new_slot_id = (
                next_slot_ids[selected_index]
                if 0 <= selected_index < len(next_slot_ids)
                else None
            )
            if old_slot_id is None or old_slot_id != new_slot_id:
                # Curio UI coordinates are page-local. Never let a virtual
                # cursor selected on page A silently become the same numeric
                # index on page B; the real item remains in A's stable slot.
                self._cancel_transient_state(
                    clear_selection=True,
                    cancel_fly=True,
                )
        slot_mapping_changed = bool(
            next_slot_ids != self.curio_slot_ids
            or next_layout != self.curio_layout
        )
        if slot_mapping_changed:
            self.bound_buttons = {}
            self.bound_button_slots = {}
            self.prepared_slot_paths = set()
            self.replica_buttons_complete = False
        self.curio_slot_ids = next_slot_ids
        self.curio_empty_textures = [
            entry.get("emptyTexture", "") for entry in slots
        ]
        self.curio_layout = next_layout
        self.curio_items = [
            copy.deepcopy(entry.get("item") or {}) for entry in slots
        ]
        continue_distribution = bool(
            old_pending is not None
            and old_pending.get("continueDistribution")
            and not old_pending.get("cursorOwned")
            and self._chatelaine_visible()
        )
        continue_mouse_hold = bool(
            old_pending is not None
            and old_pending.get("continueMouseHold")
            and self._chatelaine_visible()
        )
        should_fly = bool(
            old_pending is not None
            and state.get("result") == "ok"
            and old_pending.get("animateFly")
            and self._chatelaine_visible()
        )
        if should_fly:
            # Install the pre-transaction target before rebuilding collection
            # DTOs.  Otherwise the authoritative result flashes in the target
            # for one frame before the fly animation starts.
            self.fly_target_override = {
                "domain": old_pending.get("targetDomain"),
                "slot": old_pending.get("targetSlot"),
                "item": copy.deepcopy(old_pending.get("targetItem") or {}),
            }
        if old_pending is not None:
            if continue_distribution:
                self.selection = self._distribution_selection(old_pending)
            elif continue_mouse_hold:
                self.selection = self._post_transfer_mouse_selection(
                    old_pending
                )
            else:
                self.selection = None
            self.split_state = None
            self.press_state = None
            self.drag_state = None
            if (
                old_pending.get("action") == "cursor_pick"
                and old_pending.get("sourceDomain") == "inventory"
                and state.get("result") == "ok"
            ):
                # The server round trip sits between the two mouse clicks.
                # Begin the collection window once pickup is authoritative.
                self.last_click = (
                    "inventory",
                    old_pending.get("sourceSlot"),
                )
                self.last_click_tick = self.tick_count
        cursor_item = state.get("cursorItem") or {}
        if _item_name(cursor_item):
            self.selection = {
                "domain": "cursor",
                "slot": -1,
                "count": _item_count(cursor_item),
                "item": copy.deepcopy(cursor_item),
                "mouseMode": True,
                "cursorOwned": True,
                "cursorOrigin": copy.deepcopy(
                    state.get("cursorOrigin") or {}
                ),
            }
        elif self.selection is not None and self.selection.get("cursorOwned"):
            self.selection = None
        live_drag = self.drag_state or getattr(
            self, "committed_drag_preview", None
        )
        if live_drag is not None and live_drag.get("cursorOwned"):
            remaining = max(
                0,
                int(live_drag.get("heldCount", 0))
                - int(live_drag.get("plannedMoved", 0)),
            )
            if remaining > 0:
                self.selection = {
                    "domain": "cursor",
                    "slot": -1,
                    "count": remaining,
                    "item": _copy_client_stack(
                        live_drag.get("sourceItem") or {}, remaining
                    ),
                    "mouseMode": True,
                    "cursorOwned": True,
                    "cursorOrigin": copy.deepcopy(
                        state.get("cursorOrigin") or {}
                    ),
                }
            else:
                self.selection = None
        chatelaine_visible = self._chatelaine_visible()
        entering_chatelaine = bool(
            chatelaine_visible and not self.chatelaine_controls_active
        )
        if entering_chatelaine:
            # A page-only request reuses the last server inventory snapshot,
            # which may predate native inventory moves made while Chatelaine was
            # closed. Sample the local engine inventory before rebuilding the
            # still-hidden replica so its first visible frame is current.
            self._read_player_inventory()
        self._rebuild_view_models()
        if old_pending is not None:
            if should_fly and not self._start_fly(old_pending):
                self.fly_target_override = None
                self._rebuild_view_models()
            self.pending = None
            self.pending_ticks = 0
        elif pending_superseded:
            # A newer authoritative snapshot supersedes an unobserved result.
            # Never animate it as the older operation, but do release input.
            self.pending = None
            self.pending_ticks = 0
            if not _item_name(state.get("cursorItem") or {}):
                self.selection = None
            self.split_state = None
            self.press_state = None
            self.drag_state = None
        authority_resolved = bool(
            old_pending is not None or pending_superseded
        )
        resolved_pending = (
            old_pending
            if old_pending is not None
            else (pending_operation if pending_superseded else None)
        )
        self.render_dirty = True
        if (
            authority_resolved
            and self.chatelaine_controls_active
            and self.replica_control is not None
        ):
            # Commit the complete authoritative slot image, including hidden
            # source renderer payloads, before another click can return a
            # swapped cursor item to that source.
            self._render_all_items()
            # Transfer methods disable this root once when sending. Re-enable
            # it once when the matching/newer authority response resolves;
            # stable frames must not rewrite the same touch state.
            if not (
                resolved_pending is not None
                and resolved_pending.get("preserveReplicaTouch")
            ):
                self.replica_control.SetTouchEnable(True)
        if entering_chatelaine:
            # First populate the still-hidden grids from the current engine
            # inventory. Visibility is applied below, then a second pass fills
            # children which the engine may instantiate lazily.
            self._render_all_items()
        self._apply_page_visibility(chatelaine_visible)
        if entering_chatelaine:
            self._render_all_items()
            # Keep one delayed reconciliation for an inventory-change event
            # delivered in the same frame as its native slot commit.
            self.inventory_dirty_ticks = max(self.inventory_dirty_ticks, 1)
        self._refresh_transient_controls()
        if (
            self.native_inventory_exit_request_id is not None
            and _is_int(state_request_id)
            and int(state_request_id) >= int(
                self.native_inventory_exit_request_id
            )
            and state.get("page") == "armor"
        ):
            # The server has committed the page change. The inventory Toggle
            # was already selected on entry; restore the complete visibility,
            # size and touch snapshot once on this same native tree.
            self.native_inventory_exit_request_id = None
            self.native_inventory_exit_pending = False
            self._apply_page_visibility(False)
        elif (
            self.native_inventory_exit_request_id is not None
            and _is_int(state_request_id)
            and int(state_request_id) >= int(
                self.native_inventory_exit_request_id
            )
            and state.get("page") != "armor"
        ):
            # The authoritative page write failed or was superseded. Release
            # the local exit guard and continue from the returned page.
            self.native_inventory_exit_request_id = None
            self.native_inventory_exit_pending = False
        if (
            self.page_transition_request_id is not None
            and _is_int(state_request_id)
            and int(state_request_id) >= int(self.page_transition_request_id)
        ):
            self.page_transition_request_id = None
            self.page_transition_target = None
            self.page_transition_ticks = 0
            if (
                self.chatelaine_controls_active
                and self.replica_control is not None
                and self.pending is None
            ):
                self.replica_control.SetTouchEnable(True)
        if (
            queued_cursor_collect
            and self.pending is None
            and self.selection is not None
            and self.selection.get("cursorOwned")
        ):
            # A real double-click normally lands its second press while the
            # first server-authoritative pickup is in flight.  Run the queued
            # collection now that the hidden cursor slot is authoritative.
            self.last_click = None
            self.last_click_tick = -100
            self._send_cursor_double_click(self.selection)
        if old_pending is not None and old_pending.get("pocketOverlayReturn"):
            # One authoritative return attempt has resolved. A full inventory
            # may legitimately retain the hidden cursor; do not create a
            # response loop, and never discard that retained item locally.
            self.pocket_overlay_cursor_return_pending = False
        else:
            self._continue_pocket_overlay_cursor_return()
        self._continue_toggle_after_cursor_return(old_pending, state)

    def _continue_toggle_after_cursor_return(self, old_pending, state):
        if not (
            old_pending is not None
            and old_pending.get("action") == "cursor_return"
            and old_pending.get("toggleAfterReturn")
            and state.get("result") == "ok"
            and not _item_name(state.get("cursorItem") or {})
            and self.pending is None
        ):
            return False
        self._request_next_page()
        return True

    def _play_authoritative_drop_swing(self, pending_operation, state):
        """Swing once only after the matching drop transaction committed."""
        if (
            pending_operation is None
            or pending_operation.get("action") != "drop"
            or state.get("result") != "ok"
            or self.client_system is None
        ):
            return False
        self.client_system.SwingLocalPlayer()
        return True

    def MarkInventoryDirty(self):
        """Re-read after the event tick; its payload may precede slot commit."""
        # Keep the replica cache warm even on the armor/creative page. Opening
        # Chatelaine can then reveal the current inventory without an empty frame.
        self.inventory_dirty_ticks = 1

    def _tick_inventory_dirty(self):
        if self.inventory_dirty_ticks <= 0:
            return
        self.inventory_dirty_ticks -= 1
        if self.inventory_dirty_ticks > 0 or self.pending is not None:
            return
        if not self._read_player_inventory():
            return
        self._rebuild_view_models()
        self.render_dirty = True

    def _read_player_inventory(self):
        """Replace the replica cache with the current native inventory."""
        player_id = clientApi.GetLocalPlayerId()
        item_comp = (
            clientApi.GetEngineCompFactory().CreateItem(player_id)
            if player_id else None
        )
        if item_comp is None:
            return False
        item_pos = clientApi.GetMinecraftEnum().ItemPosType.INVENTORY
        inventory_items = []
        for slot in range(36):
            item = item_comp.GetPlayerItem(item_pos, slot, True)
            inventory_items.append(
                copy.deepcopy(item) if type(item).__name__ == "dict" else {}
            )
        self.inventory_items = inventory_items
        return True

    def _empty_dto(self):
        return {
            "itemVisible": False,
            "stackText": "",
            "stackVisible": False,
            "selected": False,
            "lockInInventory": False,
            "lockInSlot": False,
            "locked": False,
            "durabilityVisible": False,
            "durabilityTotal": 1,
            "durabilityCurrent": 1,
            "hoverText": "",
            "emptyVisible": False,
            "emptyTexture": "",
        }

    def _build_dto(self, item, domain, slot, empty_texture=""):
        dto = self._empty_dto()
        name = _item_name(item)
        count = _item_count(item)
        selected_source = bool(
            self.selection
            and self.selection.get("domain") == domain
            and self.selection.get("slot") == slot
        )
        selection_is_mouse = bool(
            selected_source and self.selection.get("mouseMode")
        )
        dto["itemVisible"] = bool(name and count > 0)
        dto["stackText"] = str(count) if count > 1 else ""
        dto["stackVisible"] = bool(dto["stackText"])
        # Distribution targets are bookkeeping only. Native inventory does
        # not draw the touch selection texture over every traversed cell.
        dto["selected"] = bool(
            selected_source
            and not selection_is_mouse
            and int(self.selection.get("count", 0)) > 0
        )
        lock_mode = _item_lock_mode(item)
        dto["lockInInventory"] = bool(
            dto["itemVisible"] and lock_mode == "lock_in_inventory"
        )
        dto["lockInSlot"] = bool(
            dto["itemVisible"] and lock_mode == "lock_in_slot"
        )
        dto["locked"] = bool(
            dto["lockInInventory"] or dto["lockInSlot"]
        )
        durability_visible, total, current = self._client_durability_state(item)
        if dto["itemVisible"]:
            dto["durabilityVisible"] = durability_visible
            dto["durabilityTotal"] = total
            dto["durabilityCurrent"] = current
        dto["hoverText"] = (
            self._formatted_hover_text(item) if dto["itemVisible"] else ""
        )
        dto["emptyVisible"] = bool(empty_texture and not dto["itemVisible"])
        dto["emptyTexture"] = empty_texture
        return dto

    def _formatted_hover_text(self, item):
        name = _item_name(item)
        if not name:
            return ""
        cache_key = (
            name,
            _item_aux(item),
            repr(item.get("userData")),
        )
        cached = self._hover_text_cache.get(cache_key)
        if cached is not None:
            return cached
        player_id = clientApi.GetLocalPlayerId()
        item_comp = (
            clientApi.GetEngineCompFactory().CreateItem(player_id)
            if player_id else None
        )
        getter = getattr(item_comp, "GetItemFormattedHoverText", None)
        if callable(getter):
            value = getter(
                name,
                _item_aux(item),
                False,
                item.get("userData"),
            )
            if type(value).__name__ in ("str", "unicode") and value:
                result = value
            else:
                result = name
        else:
            result = name
        if len(self._hover_text_cache) >= 128:
            self._hover_text_cache.clear()
        self._hover_text_cache[cache_key] = result
        return result

    def _rebuild_view_models(self):
        self.inventory_hotbar = [
            self._build_dto(
                self._visual_item(self.inventory_items[index], "inventory", index),
                "inventory",
                index,
            )
            for index in range(9)
        ]
        self.inventory_bag = [
            self._build_dto(
                self._visual_item(self.inventory_items[index], "inventory", index),
                "inventory",
                index,
            )
            for index in range(9, 36)
        ]
        self.curio_slot_models = [
            self._build_dto(
                self._visual_item(self.curio_items[index], "curio", index),
                "curio",
                index,
                self.curio_empty_textures[index],
            )
            for index in range(len(self.curio_items))
        ]
        if self.curio_layout == "expanded":
            # Collection bindings address row-major UI cells. Keep a full
            # physical 4x4 collection so the engine creates every cell, then
            # place the logical top-to-bottom slot order into those cells.
            self.curio_slots = [
                self._empty_dto()
                for _index in range(EXPANDED_GRID_CAPACITY)
            ]
            for logical_index, dto in enumerate(self.curio_slot_models):
                cell_index = logical_slot_to_cell(logical_index, True)
                if cell_index is not None:
                    self.curio_slots[cell_index] = dto
        else:
            self.curio_slots = list(self.curio_slot_models)

    def _curio_grid_path(self):
        name = (
            "expanded_slots_grid"
            if self.curio_layout == "expanded" else "slots_grid"
        )
        return self.root_path + "/" + name

    def _visual_item(self, item, domain, slot):
        override = self.fly_target_override
        if (
            override is not None
            and override.get("domain") == domain
            and override.get("slot") == slot
        ):
            return override.get("item") or {}
        drag = self.drag_state or getattr(
            self, "committed_drag_preview", None
        )
        if drag is not None and domain == "inventory":
            allocation = int((drag.get("allocations") or {}).get(int(slot), 0))
            if allocation > 0:
                entry = (drag.get("targetBySlot") or {}).get(int(slot), {})
                baseline = entry.get("expected") or {}
                base = baseline or drag.get("sourceItem") or {}
                return _copy_client_stack(
                    base, _item_count(baseline) + allocation
                )
        if (
            drag is not None
            and not drag.get("mouseMode")
            and drag.get("sourceDomain") == domain
            and drag.get("sourceSlot") == slot
        ):
            # Streaming distribution snapshots already contain the server-side
            # source decrement. Always project from the immutable gesture
            # baseline so an arriving update cannot subtract plannedMoved a
            # second time and make the remainder jump out of its origin cell.
            baseline = drag.get("sourceItem") or item
            return _copy_client_stack(
                baseline,
                max(
                    0,
                    _item_count(baseline) - drag.get("plannedMoved", 0),
                ),
            )
        return item

    def _distribution_selection(self, operation):
        domain = operation.get("sourceDomain")
        slot = operation.get("sourceSlot")
        item = copy.deepcopy(self._item_at(domain, slot) or {})
        expected = operation.get("sourceItem") or operation.get("item") or {}
        if expected and not self._same_stack(item, expected):
            return None
        held_remaining = max(
            0,
            _item_count(item) - int(operation.get("baseUnheld", 0)),
        )
        if held_remaining <= 0:
            return None
        return {
            "domain": domain,
            "slot": slot,
            "count": held_remaining,
            "sourceHiddenCount": held_remaining,
            "item": item,
            "mouseMode": bool(operation.get("mouseMode")),
        }

    def _post_transfer_mouse_selection(self, operation):
        """Rebuild the logical cursor from the authoritative source slot."""
        if operation is None or not operation.get("mouseMode"):
            return None
        domain = operation.get("sourceDomain")
        slot = operation.get("sourceSlot")
        source_after = self._item_at(domain, slot)
        source_before = operation.get("item") or {}
        base_unheld = max(0, int(operation.get("baseUnheld", 0)))
        if self._same_stack(source_after, source_before):
            remaining = max(0, _item_count(source_after) - base_unheld)
            if remaining > 0:
                return {
                    "domain": domain,
                    "slot": slot,
                    "count": remaining,
                    "sourceHiddenCount": remaining,
                    "item": copy.deepcopy(source_after),
                    "mouseMode": True,
                }
        target_before = operation.get("targetItem") or {}
        if (
            _item_name(target_before)
            and self._same_stack(source_after, target_before)
            and _item_count(source_after) == _item_count(target_before)
        ):
            item = copy.deepcopy(source_after or {})
            return {
                "domain": domain,
                "slot": slot,
                "count": _item_count(item),
                "sourceHiddenCount": _item_count(item),
                "item": item,
                "mouseMode": True,
            }
        return None

    def _collection_value(self, collection_name, index, key, default):
        collection = getattr(self, collection_name, ())
        if not _is_int(index) or int(index) < 0 or int(index) >= len(collection):
            return default
        return collection[int(index)].get(key, default)

    def _chatelaine_page_selected(self):
        if self.native_inventory_exit_pending:
            # Do not expose a half-restored native tree between the optimistic
            # local page change and the confirmed close/reopen transaction.
            return True
        return bool(
            self.client_system is not None
            and self._client_state().get("page") == "chatelaine"
        )

    def _chatelaine_visible(self):
        if not self._chatelaine_page_selected():
            return False
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return True
        return self._pocket_armor_tab_visible()

    def _pocket_armor_tab_visible(self):
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return True
        armor_tab = self.screen_node.GetBaseUIControl(POCKET_ARMOR_TAB_PATH)
        return bool(armor_tab is not None and armor_tab.GetVisible())

    def _pocket_inventory_tab_selected(self):
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return True
        inventory_tab = self.screen_node.GetBaseUIControl(
            POCKET_INVENTORY_TAB_PATH
        )
        return bool(
            inventory_tab is not None and inventory_tab.GetVisible()
        )

    def _native_control_paths(self):
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            # Left categories have their own one-shot exit restore after the
            # native inventory-toggle binding settles. Capturing them here
            # would make the generic restore write the stack once immediately
            # and the deferred restore write it again on the next tick.
            return self._pocket_native_restore_paths()
        return (
            _CLASSIC_CRAFTING_PANEL,
            _CLASSIC_INVENTORY + "/inventory_panel_bottom_half",
            _CLASSIC_INVENTORY + "/hotbar_grid",
            _CLASSIC_CONTENT_STACK + "/recipe_book",
            _CLASSIC_CONTENT_STACK + "/center_fold",
        )

    def _hide_pocket_left_navigation_children(self):
        """Snapshot and hide every direct Pocket left tab except inventory."""
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return
        children = self.screen_node.GetChildrenName(
            _POCKET_LEFT_NAVIGATION_CONTENT
        ) or ()
        for child_name in children:
            if type(child_name).__name__ not in ("str", "unicode"):
                continue
            child_tail = child_name.rsplit("/", 1)[-1]
            if child_tail in POCKET_LEFT_NAVIGATION_KEEP_CHILDREN:
                continue
            child_path = (
                child_name
                if child_name.startswith(
                    _POCKET_LEFT_NAVIGATION_CONTENT + "/"
                )
                else _POCKET_LEFT_NAVIGATION_CONTENT + "/" + child_name
            )
            control = self.screen_node.GetBaseUIControl(child_path)
            if control is None:
                continue
            if child_path not in self.pocket_left_child_states:
                self.pocket_left_child_states[child_path] = bool(
                    control.GetVisible()
                )
            control.SetVisible(False)
            control.SetTouchEnable(False)

    def _pocket_left_restore_paths(self):
        return tuple(self.pocket_left_child_states.keys())

    @staticmethod
    def _pocket_required_left_tab_paths():
        # Search and the four creative categories must be returned when Chatelaine
        # releases the left side. Arrow visibility remains snapshot-owned
        # because it depends on the current category scroll position.
        return POCKET_CREATIVE_TOGGLE_ROOT_PATHS

    @staticmethod
    def _pocket_overlay_native_paths():
        return (
            POCKET_RECIPE_CONTENT_PATH,
            POCKET_INVENTORY_CONTENT_PATH,
        )

    @staticmethod
    def _pocket_native_restore_paths():
        return (
            POCKET_RECIPE_CONTENT_PATH,
            POCKET_INVENTORY_CONTENT_PATH,
            POCKET_NATIVE_HOTBAR_PATH,
            POCKET_NATIVE_HOTBAR_PATH + "/bg",
            POCKET_NATIVE_HOTBAR_PATH + "/hotbar_grid",
        )

    @staticmethod
    def _classic_category_paths():
        return tuple(
            _CLASSIC_CATEGORY_CONTENT + "/" + name
            for name in (
                "construction_tab_panel",
                "equipment_tab_panel",
                "items_tab_panel",
                "nature_tab_panel",
            )
        )

    def _restore_classic_tab_touch(self, states):
        """Restore hit testing after the toolbar has re-entered layout.

        NetEase's toolbar bindings may make a panel visible one frame after
        SetVisible. Visibility does not reset a previous SetTouchEnable(False),
        so re-enable both the visible wrapper and its actual toggle while the
        native-state snapshot is being reasserted.
        """
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            return
        if not states and not self.native_size_states:
            return
        entries = (
            (
                "mount_tab_layout_toggle_panel",
                "mount_layout_toggle",
                True,
            ),
            (
                "parterner_tab_layout_toggle_panel",
                "parterner_layout_toggle",
                True,
            ),
            (
                "creative_layout_toggle_panel",
                "creative_layout_toggle",
                False,
            ),
            (
                "recipe_book_layout_toggle_panel_survival",
                "recipe_book_layout_toggle",
                False,
            ),
            (
                "recipe_book_layout_toggle_panel_creative",
                "recipe_book_layout_toggle",
                False,
            ),
        )
        for panel_name, toggle_name, optional in entries:
            panel_path = _CLASSIC_TOOLBAR_STACK + "/" + panel_name
            if optional:
                restored_size = self.native_size_states.get(
                    panel_path, (0, 0)
                )
                if restored_size[0] <= 0:
                    panel = self.screen_node.GetBaseUIControl(panel_path)
                    if panel is not None:
                        panel.SetVisible(False)
                        panel.SetTouchEnable(False)
                    toggle = self.screen_node.GetBaseUIControl(
                        panel_path + "/" + toggle_name
                    )
                    if toggle is not None:
                        toggle.SetVisible(False)
                        toggle.SetTouchEnable(False)
                    continue
            panel = self.screen_node.GetBaseUIControl(panel_path)
            if panel is not None:
                if optional:
                    panel.SetVisible(True)
                panel.SetTouchEnable(True)
            toggle = self.screen_node.GetBaseUIControl(
                panel_path + "/" + toggle_name
            )
            if toggle is not None:
                toggle.SetVisible(True)
                toggle.SetTouchEnable(True)

    def _sync_classic_toolbar_padding(self):
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            return
        creative = self.screen_node.GetBaseUIControl(
            _CLASSIC_TOOLBAR_STACK + "/creative_layout_toggle_panel"
        )
        padding = self.screen_node.GetBaseUIControl(
            _CLASSIC_TOOLBAR_STACK + "/padding_1"
        )
        if creative is not None and padding is not None:
            padding.SetVisible(bool(creative.GetVisible()))

    def _apply_classic_toolbar_collapse(self, chatelaine_visible):
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            return True
        entries = (
            ("mount_tab_layout_toggle_panel", "mount_layout_toggle", None),
            ("parterner_tab_layout_toggle_panel", "parterner_layout_toggle", None),
            ("creative_layout_toggle_panel", "creative_layout_toggle", (25, 20)),
            ("padding_1", None, (2, 0)),
            (
                "recipe_book_layout_toggle_panel_survival",
                "recipe_book_layout_toggle",
                (25, 20),
            ),
            (
                "recipe_book_layout_toggle_panel_creative",
                "recipe_book_layout_toggle",
                (25, 20),
            ),
            ("padding_2", None, (1, 0)),
        )
        required_panels = set(entry[0] for entry in entries[2:])
        complete = True
        sizes = self.native_size_states
        for panel_name, toggle_name, restore_size in entries:
            panel_path = _CLASSIC_TOOLBAR_STACK + "/" + panel_name
            panel = self.screen_node.GetBaseUIControl(panel_path)
            if panel is None:
                if chatelaine_visible and panel_name in required_panels:
                    complete = False
                continue
            if chatelaine_visible:
                if panel_path not in sizes:
                    current_size = tuple(panel.GetSize())
                    sizes[panel_path] = (
                        current_size
                        if current_size[0] > 0 or restore_size is None
                        else restore_size
                    )
                panel.SetSize((0, 0))
                panel.SetTouchEnable(False)
                if toggle_name:
                    toggle_path = panel_path + "/" + toggle_name
                    toggle = self.screen_node.GetBaseUIControl(toggle_path)
                    if toggle is not None:
                        if toggle_path not in sizes:
                            current_size = tuple(toggle.GetSize())
                            sizes[toggle_path] = (
                                current_size
                                if current_size[0] > 0 or restore_size is None
                                else (25, 20)
                            )
                        toggle.SetSize((0, 0))
                        toggle.SetVisible(False)
                        toggle.SetTouchEnable(False)
                    elif panel_name in required_panels:
                        complete = False
            elif panel_path in sizes:
                panel.SetSize(tuple(sizes[panel_path]))
                if toggle_name:
                    toggle_path = panel_path + "/" + toggle_name
                    toggle = self.screen_node.GetBaseUIControl(toggle_path)
                    if toggle is not None and toggle_path in sizes:
                        toggle.SetSize(tuple(sizes[toggle_path]))
        return complete

    def _apply_classic_chatelaine_layout(self, chatelaine_visible):
        if (
            self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            or not chatelaine_visible
        ):
            return
        forced = (
            (_CLASSIC_CONTENT_STACK + "/survival_padding", True),
            (_CLASSIC_INVENTORY, True),
        )
        for path, visible in forced:
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetVisible(visible)
                control.SetTouchEnable(visible)

    def _capture_native_controls(self):
        paths = list(self._native_control_paths())
        for path in paths:
            if path in self.native_states:
                continue
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                self.native_states[path] = bool(control.GetVisible())

    def _force_inventory_layout(self, chatelaine_visible):
        if not chatelaine_visible:
            self.inventory_layout_forced = False
            self.pocket_inventory_switch_tick = None
            return True
        if self.inventory_layout_forced:
            return True
        if (
            self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            and not self.pocket_navigation_ready
        ):
            # A Chatelaine session can survive a Classic -> Pocket screen
            # reconstruction. Never issue a group selection while Pocket's
            # factory-backed navigation_tab members are still registering:
            # ScreenView asserts if its queued selected index has no member.
            return False
        selected = self._select_inventory_layout()
        if (
            selected
            and self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
        ):
            # Pocket category tabs are factory-backed members of the native
            # ``navigation_tab`` group. The C++ selected-index binding settles
            # one tick after SetToggleState. Hiding the old category in that
            # same tick can destroy its factory child while ScreenView still
            # has (for example) index 2 queued, causing a hard assertion.
            if self.pocket_inventory_switch_tick is None:
                self.pocket_inventory_switch_tick = self.tick_count
                return False
            if self.tick_count <= self.pocket_inventory_switch_tick:
                return False
        self.inventory_layout_forced = selected
        return self.inventory_layout_forced

    def _observe_pocket_navigation_tree(self):
        """Warm a read-only, stable Pocket navigation readiness barrier."""
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return True
        # Creative members are factory-backed and may legitimately have no
        # Toggle child in survival mode. Their static host panels, the direct
        # navigation content list and the survival Toggle itself are the
        # reliable construction boundary.
        required_controls = (
            (_POCKET_LEFT_NAVIGATION_CONTENT,)
            + POCKET_CREATIVE_TOGGLE_ROOT_PATHS
            + (POCKET_INVENTORY_TOGGLE_PATH,)
        )
        for path in required_controls:
            if self.screen_node.GetBaseUIControl(path) is None:
                self.pocket_navigation_signature = None
                self.pocket_navigation_stable_samples = 0
                self.pocket_navigation_ready = False
                return False
        if self._switch_toggle_at(POCKET_INVENTORY_TOGGLE_PATH) is None:
            self.pocket_navigation_signature = None
            self.pocket_navigation_stable_samples = 0
            self.pocket_navigation_ready = False
            return False
        child_names = tuple(sorted(
            child.rsplit("/", 1)[-1]
            for child in (
                self.screen_node.GetChildrenName(
                    _POCKET_LEFT_NAVIGATION_CONTENT
                ) or ()
            )
            if type(child).__name__ in ("str", "unicode")
        ))
        current_signature = (
            self._switch_toggle_paths.get(
                POCKET_INVENTORY_TOGGLE_PATH,
                POCKET_INVENTORY_TOGGLE_PATH,
            ),
            child_names,
        )
        (
            self.pocket_navigation_signature,
            self.pocket_navigation_stable_samples,
            self.pocket_navigation_ready,
        ) = advance_stable_signature(
            self.pocket_navigation_signature,
            self.pocket_navigation_stable_samples,
            current_signature,
            POCKET_NAVIGATION_STABLE_SAMPLES,
        )
        return self.pocket_navigation_ready

    def _select_inventory_layout(self):
        """Select the real native inventory Toggle exactly once.

        SwitchToggleUIControl defaults its relative toggle path to
        ``/this_toggle``. Native inventory tabs are already the actual toggle,
        so Get/SetToggleState must explicitly target ``""``. Using the default
        path is a silent no-op on Pocket and on some Classic variants.
        """
        path = (
            POCKET_INVENTORY_TOGGLE_PATH
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            else CLASSIC_INVENTORY_TOGGLE_PATH
        )
        toggle = self._switch_toggle_at(path)
        if toggle is None:
            return False
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            # The native radio group owns mutual exclusion. Do not manually
            # clear its five category toggles: four are factory-backed, and a
            # direct clear can leave C++ with a selected index whose control
            # was just destroyed. Only request the static inventory member,
            # and never resend the command once it is already selected.
            complete = True
            if not self._toggle_state(toggle):
                self._set_toggle_state(toggle, True)
            toggle_path_actual = self._switch_toggle_paths.get(path)
            toggle_control = self.screen_node.GetBaseUIControl(
                toggle_path_actual
            ) if toggle_path_actual else None
            if toggle_control is not None:
                # SetToggleState changes the Toggle object, while the native
                # global binding may still repaint its old category in the
                # same frame. Override the rendered property as the last step.
                toggle_control.SetPropertyBag({"#toggle_state": True})
        else:
            # Classic layout toggles are not reliably made mutually exclusive
            # by SetToggleState. Clear every competing layout first; otherwise
            # creative/recipe and survival can both remain selected and the
            # horizontal content stack lays out two full panels.
            complete = True
            optional_paths = CLASSIC_LAYOUT_TOGGLE_PATHS[:2]
            for other_path in CLASSIC_LAYOUT_TOGGLE_PATHS:
                if other_path == CLASSIC_INVENTORY_TOGGLE_PATH:
                    continue
                other = self._switch_toggle_at(other_path)
                if other is None:
                    if other_path not in optional_paths:
                        complete = False
                    continue
                if other is not None and self._toggle_state(other):
                    self._set_toggle_state(other, False)
            if not self._toggle_state(toggle):
                self._set_toggle_state(toggle, True)
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            inventory_content = self.screen_node.GetBaseUIControl(
                POCKET_INVENTORY_TAB_PATH
            )
            if (
                inventory_content is not None
                and not inventory_content.GetVisible()
            ):
                # The global selected-tab binding can settle one frame after
                # the nested SwitchToggle changes. Keep the requested content
                # active until #is_left_tab_inventory catches up.
                inventory_content.SetVisible(True)
                inventory_content.SetTouchEnable(True)
        return complete

    def _switch_toggle_at(self, root_path, max_depth=5):
        cached_path = self._switch_toggle_paths.get(root_path)
        if cached_path:
            cached_control = self.screen_node.GetBaseUIControl(cached_path)
            cached_toggle = (
                cached_control.asSwitchToggle()
                if self._is_actual_toggle(cached_control) else None
            )
            if cached_toggle is not None:
                return cached_toggle
            self._switch_toggle_paths.pop(root_path, None)
        pending = [(root_path, 0)]
        while pending:
            path, depth = pending.pop(0)
            control = self.screen_node.GetBaseUIControl(path)
            if self._is_actual_toggle(control):
                toggle = control.asSwitchToggle()
                if toggle is not None:
                    self._switch_toggle_paths[root_path] = path
                    return toggle
            if depth >= max_depth:
                continue
            for child_name in self.screen_node.GetChildrenName(path) or ():
                pending.append((path + "/" + child_name, depth + 1))
        return None

    @staticmethod
    def _is_actual_toggle(control):
        if control is None:
            return False
        properties = control.GetPropertyBag()
        return bool(
            type(properties).__name__ == "dict"
            and "#toggle_state" in properties
        )

    @staticmethod
    def _toggle_state(toggle):
        return bool(toggle.GetToggleState(""))

    @staticmethod
    def _set_toggle_state(toggle, selected):
        toggle.SetToggleState(bool(selected), "")

    def _restore_classic_creative_touch(self, states):
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN or not states:
            return
        paths = (
            _CLASSIC_CONTENT_STACK + "/recipe_book",
            _CLASSIC_CONTENT_STACK + "/recipe_book/tab_navigation_panel",
            _CLASSIC_CONTENT_STACK + "/recipe_book/tab_content_panel",
            _CLASSIC_CONTENT_STACK + "/recipe_book/creative_hotbar_panel",
        )
        for path in paths:
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetTouchEnable(True)
        for path in self._classic_category_paths():
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetVisible(True)
                control.SetTouchEnable(True)

    def _hide_native_controls(self, paths):
        for path in paths:
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetVisible(False)
                control.SetTouchEnable(False)

    def _restore_pocket_overlay_native_controls(self):
        """Restore native inventory content while Chatelaine stays selected."""
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return
        for path in self._pocket_native_restore_paths():
            control = self.screen_node.GetBaseUIControl(path)
            if control is None:
                continue
            # The native outer/right-tab bindings own the final page choice;
            # every inner content and complete hotbar ancestor must be ready.
            # Restoring only bg/grid leaves a hidden parent and no hotbar.
            control.SetVisible(True)
            control.SetTouchEnable(True)

    def _settle_pocket_overlay_exit(self):
        """Finish Chatelaine gestures and return its hidden cursor on Tab exit."""
        self.pocket_overlay_cursor_return_pending = True
        if self.pending is not None:
            # Do not run a queued mouse double-click after the right Tab has
            # already left the Chatelaine overlay. The pickup response is used
            # only to discover and return the authoritative hidden cursor.
            self.pending.pop("queuedDoubleClick", None)
        if self.drag_state is not None:
            # Streaming distribution owns server state. Finish it instead of
            # erasing only the preview and leaving the session interlocked.
            self._submit_drag_distribution()
        self._cancel_transient_state(
            clear_selection=True,
            cancel_fly=True,
        )
        self._continue_pocket_overlay_cursor_return()

    def _continue_pocket_overlay_cursor_return(self):
        if (
            self.screen_name != CURIO_INVENTORY_POCKET_SCREEN
            or not getattr(
                self, "pocket_overlay_cursor_return_pending", False
            )
            or self.client_system is None
            or self.pending is not None
        ):
            return False
        cursor_item = self._client_state().get("cursorItem") or {}
        if not _item_name(cursor_item):
            self.pocket_overlay_cursor_return_pending = False
            return True
        request_id = self.client_system.ReturnCurioInventoryCursor()
        if not request_id:
            return False
        self.pending = {
            "action": "cursor_return",
            "requestId": request_id,
            "mouseMode": True,
            "cursorOwned": True,
            "pocketOverlayReturn": True,
            "animateFly": False,
        }
        self.pending_ticks = 0
        if self.replica_control is not None:
            self.replica_control.SetTouchEnable(False)
        return True

    def _restore_pocket_exit_controls(self):
        """Reassert Pocket controls once after native tab bindings settle."""
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return
        states = self.pocket_exit_restore_states
        for path, visible in states.items():
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetVisible(bool(visible))
                control.SetTouchEnable(bool(visible))
        # These controls were hidden by Chatelaine itself, so a false value left by
        # the delayed native binding is not a valid exit target. Reassert only
        # the five tab panels once after that binding settles. The navigation
        # and content stack parents were never hidden and must not be toggled:
        # doing so can re-anchor the vertical stack at the screen top.
        for path in self._pocket_required_left_tab_paths():
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetVisible(True)
                control.SetTouchEnable(True)
        self.pocket_exit_restore_states = {}

    def _apply_page_visibility(self, chatelaine_visible):
        chatelaine_visible = bool(chatelaine_visible)
        page_selected = self._chatelaine_page_selected()
        player_doll_visible = bool(
            self._client_state().get("playerDollVisible", True)
        )
        if (
            page_selected == self.chatelaine_page_active
            and chatelaine_visible == self.chatelaine_controls_active
            and self.curio_layout == self.applied_curio_layout
            and player_doll_visible == self.applied_player_doll_visible
        ):
            # Page ownership and the Pocket armor overlay change only at their
            # respective edges. Stable frames must not rewrite the UI tree.
            return
        entering_page = bool(page_selected and not self.chatelaine_page_active)
        leaving_page = bool(not page_selected and self.chatelaine_page_active)
        entering_overlay = bool(
            chatelaine_visible and not self.chatelaine_controls_active
        )
        leaving_overlay = bool(
            not chatelaine_visible and self.chatelaine_controls_active
        )
        if entering_page:
            # Capture before forcing the survival layout. Native/NetEase
            # bindings can transiently change tab visibility during that
            # switch, and those transient values must never become the
            # restoration snapshot.
            self.native_states = {}
            self.native_size_states = {}
            self.pocket_left_child_states = {}
            self._capture_native_controls()
            self._cancel_transient_state(clear_selection=True, cancel_fly=True)
        elif leaving_page:
            self._cancel_transient_state(clear_selection=True, cancel_fly=True)
        if entering_overlay:
            # The input profile is cached for this screen-proxy lifetime.
            # Reapply that cached position if Pocket lazily rebuilt the grids,
            # but never reread a runtime mouse/touch mode switch here.
            self.pocket_grid_position_applied = False
            self.render_dirty = True
        elif leaving_overlay and not leaving_page:
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
                self._settle_pocket_overlay_exit()
            else:
                self._cancel_transient_state(
                    clear_selection=True,
                    cancel_fly=True,
                )
        self._force_inventory_layout(page_selected)
        self._apply_classic_chatelaine_layout(page_selected)
        self.classic_toolbar_collapse_complete = bool(
            self._apply_classic_toolbar_collapse(page_selected)
            if page_selected else False
        )
        replica_visible = bool(chatelaine_visible)
        if self.armor_grid is not None:
            self.armor_grid.SetVisible(not chatelaine_visible)
            self.armor_grid.SetTouchEnable(not chatelaine_visible)
        if self.offhand_grid is not None:
            self.offhand_grid.SetVisible(not chatelaine_visible)
            self.offhand_grid.SetTouchEnable(not chatelaine_visible)
        for grid_name in ("slots_grid", "expanded_slots_grid"):
            slots_grid = self.screen_node.GetBaseUIControl(
                self.root_path + "/" + grid_name
            )
            if slots_grid is not None:
                active = bool(
                    replica_visible
                    and grid_name == self._curio_grid_path().rsplit("/", 1)[1]
                )
                slots_grid.SetVisible(active)
                slots_grid.SetTouchEnable(active)
        doll_visible = bool(
            not replica_visible
            or player_doll_visible
        )
        doll_paths = (
            POCKET_PLAYER_DOLL_PATHS
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            else CLASSIC_PLAYER_DOLL_PATHS
        )
        for doll_path in doll_paths:
            doll = self.screen_node.GetBaseUIControl(doll_path)
            if doll is not None:
                doll.SetVisible(doll_visible)
                doll.SetTouchEnable(doll_visible)
        self.replica_control.SetVisible(replica_visible)
        self.replica_control.SetTouchEnable(
            bool(
                replica_visible
                and self.pending is None
                and self.page_transition_target is None
            )
        )
        if self.overlay_control is not self.replica_control:
            self.overlay_control.SetVisible(chatelaine_visible)
        bag_scroll_panel = self.screen_node.GetBaseUIControl(
            self.bag_path + "/bag_scroll_panel"
        )
        hotbar_grid = self.screen_node.GetBaseUIControl(
            self.replica_path + "/hotbar_grid"
        )
        bag_visible = bool(
            replica_visible and self._pocket_inventory_tab_selected()
        )
        if bag_scroll_panel is not None:
            bag_scroll_panel.SetVisible(bag_visible)
            bag_scroll_panel.SetTouchEnable(bag_visible)
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            bag_root = self.screen_node.GetBaseUIControl(self.bag_path)
            if bag_root is not None:
                bag_root.SetVisible(bag_visible)
                bag_root.SetTouchEnable(bag_visible)
        if hotbar_grid is not None:
            hotbar_grid.SetVisible(replica_visible)
            hotbar_grid.SetTouchEnable(replica_visible)
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            native_hotbar = self.screen_node.GetBaseUIControl(
                POCKET_NATIVE_HOTBAR_PATH
            )
            if native_hotbar is not None:
                # The fixed-height replica is a sibling inside this same
                # hotbar_section_panel. Swap the two roots on one page edge;
                # never hide or disable their shared layout parent.
                native_hotbar.SetVisible(not chatelaine_visible)
                native_hotbar.SetTouchEnable(not chatelaine_visible)
        if (
            self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            and page_selected
            and self.inventory_layout_forced
        ):
            # Chatelaine page ownership keeps every left category except inventory
            # hidden regardless of which right-side tab is selected.
            self._hide_pocket_left_navigation_children()
            if chatelaine_visible:
                self._hide_native_controls(self._pocket_overlay_native_paths())
            else:
                self._restore_pocket_overlay_native_controls()
        elif chatelaine_visible:
            self._hide_native_controls(self._native_control_paths())
        if leaving_page:
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
                restore_paths = (
                    self._pocket_left_restore_paths()
                    + self._pocket_native_restore_paths()
                )
                required_left_paths = self._pocket_required_left_tab_paths()
                self.pocket_exit_restore_states = {
                    path: (
                        True
                        if (
                            path in self._pocket_native_restore_paths()
                            or path in required_left_paths
                        )
                        else bool(self.native_states.get(path, True))
                    )
                    for path in restore_paths
                }
                self.pocket_left_child_states = {}
            self._restore_native_controls()
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
                # Pocket Chatelaine owns the left side while it is open, so its
                # exit target is always the inventory tab rather than the
                # category that happened to be selected before entry. Apply
                # this after restoring the native tree: restoring visibility
                # can make the global #is_left_tab_* binding repaint the old
                # category and leave the inventory body below an unchecked
                # and therefore non-interactive tab.
                self._select_inventory_layout()
                self.pocket_exit_inventory_reselect = True
        self.chatelaine_page_active = bool(page_selected)
        self.chatelaine_controls_active = bool(chatelaine_visible)
        self.applied_curio_layout = self.curio_layout
        self.applied_player_doll_visible = player_doll_visible

    def _restore_native_controls(self):
        if self.screen_node is None:
            return
        states = self.native_states
        for path, visible in states.items():
            control = self.screen_node.GetBaseUIControl(path)
            if control is not None:
                control.SetVisible(bool(visible))
                control.SetTouchEnable(bool(visible))
        self._restore_pocket_overlay_native_controls()
        self._restore_classic_tab_touch(states)
        self._sync_classic_toolbar_padding()
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            # Chatelaine always exits to the Classic inventory layout. Restoring a
            # pre-Chatelaine recipe/creative snapshot leaves its transparent input
            # roots above the visible inventory and swallows every mouse hit.
            # The crafting panel is owned by the same deterministic exit
            # layout: Chatelaine hid it itself, so a missing or transiently-false
            # entry snapshot must never be treated as its final state.
            for path in (
                _CLASSIC_CONTENT_STACK + "/survival_padding",
                _CLASSIC_INVENTORY,
                _CLASSIC_CRAFTING_PANEL,
                _CLASSIC_INVENTORY + "/inventory_panel_bottom_half",
                _CLASSIC_INVENTORY + "/hotbar_grid",
            ):
                control = self.screen_node.GetBaseUIControl(path)
                if control is not None:
                    control.SetVisible(True)
                    control.SetTouchEnable(True)
            for path in (
                _CLASSIC_CONTENT_STACK + "/recipe_book",
                _CLASSIC_CONTENT_STACK + "/center_fold",
            ):
                control = self.screen_node.GetBaseUIControl(path)
                if control is not None:
                    control.SetVisible(False)
                    control.SetTouchEnable(False)
            # Native layout bindings only change visibility.  Restore input on
            # the complete creative/recipe root after forcing the initial
            # inventory layout, otherwise selecting a creative toolbar toggle
            # makes the catalogue visible again but leaves its search, four
            # category tabs and item content below a touch-disabled ancestor.
            self._restore_classic_creative_touch(states)
        self.native_states = {}
        self.native_size_states = {}
        self.classic_toolbar_collapse_complete = False
        if self.armor_grid is not None:
            self.armor_grid.SetVisible(True)
            self.armor_grid.SetTouchEnable(True)
        if self.offhand_grid is not None:
            self.offhand_grid.SetVisible(True)
            self.offhand_grid.SetTouchEnable(True)

    def _maintain_page_controls(self):
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            # Classic page edges are delivered by RefreshCurioState. Its
            # stable frames only need to finish a lazy native takeover.
            if not self.chatelaine_page_active:
                return
            page_selected = True
            chatelaine_visible = True
        else:
            page_selected = self._chatelaine_page_selected()
            chatelaine_visible = self._chatelaine_visible()
        if (
            bool(page_selected) != self.chatelaine_page_active
            or bool(chatelaine_visible) != self.chatelaine_controls_active
        ):
            # Pocket right-tab changes are native and have no dedicated proxy
            # callback, so poll only these two edge conditions. The page keeps
            # left-category ownership while the armor overlay independently
            # follows right-tab visibility.
            self._apply_page_visibility(chatelaine_visible)
        if page_selected and not self.inventory_layout_forced:
            # Native toggles may be one lazy-construction step behind the
            # custom roots. Retry only the unfinished takeover; once every
            # required Toggle exists this path becomes permanently idle.
            if self._force_inventory_layout(True):
                self._apply_classic_chatelaine_layout(True)
                self.classic_toolbar_collapse_complete = bool(
                    self._apply_classic_toolbar_collapse(True)
                )
                if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
                    self._hide_pocket_left_navigation_children()
                    if chatelaine_visible:
                        self._hide_native_controls(
                            self._pocket_overlay_native_paths()
                        )
        elif (
            page_selected
            and self.screen_name != CURIO_INVENTORY_POCKET_SCREEN
            and not self.classic_toolbar_collapse_complete
        ):
            # Required toolbar children can also settle after the layout
            # Toggle. Collapse only until every mandatory child was reached.
            self.classic_toolbar_collapse_complete = bool(
                self._apply_classic_toolbar_collapse(True)
            )
        if not chatelaine_visible:
            return
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            self._apply_pocket_grid_position()
            self._layout_pocket_bag_slots()

    def _apply_pocket_grid_position(self):
        """Apply one screen-session input profile to the Pocket bag viewport."""
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return False
        if self.pocket_grid_mouse_mode is None:
            # InventoryChatelaineScreenProxy is recreated with the native screen,
            # so this value naturally expires when the player closes and
            # reopens inventory. Do not follow input-profile changes while the
            # current screen remains alive.
            self.pocket_grid_mouse_mode = bool(self._is_mouse_mode())
        if getattr(self, "pocket_grid_position_applied", False):
            return True
        grid_x = 11.5 if self.pocket_grid_mouse_mode else 7.5
        bag_scroll_panel = self.screen_node.GetBaseUIControl(
            self.bag_path + "/bag_scroll_panel"
        )
        if bag_scroll_panel is not None:
            bag_scroll_panel.SetPosition((grid_x, 7))
        self.pocket_grid_position_applied = bool(bag_scroll_panel is not None)
        return self.pocket_grid_position_applied

    def _pocket_bag_slots_path(self):
        if self.pocket_grid_mouse_mode is None:
            self.pocket_grid_mouse_mode = bool(self._is_mouse_mode())
        mode_root = "scroll_mouse" if self.pocket_grid_mouse_mode else "scroll_touch"
        return (
            self.bag_path
            + "/bag_scroll_panel/"
            + mode_root
            + "/scroll_view/panel/background_and_viewport/"
            "scrolling_view_port/scrolling_content/bag_slots_panel"
        )

    def _layout_pocket_bag_slots(self):
        """Place 27 persistent Pocket cells without a Grid layout cycle."""
        if self.screen_name != CURIO_INVENTORY_POCKET_SCREEN:
            return False
        slots_path = self._pocket_bag_slots_path()
        slots_panel = self.screen_node.GetBaseUIControl(slots_path)
        if slots_panel is None:
            return False
        viewport_path = slots_path.rsplit(
            "/scrolling_content/bag_slots_panel", 1
        )[0]
        viewport = self.screen_node.GetBaseUIControl(viewport_path)
        if viewport is None:
            return False
        viewport_size = viewport.GetSize()
        if (
            type(viewport_size).__name__ not in ("tuple", "list")
            or len(viewport_size) < 2
            or float(viewport_size[0]) <= 0.0
        ):
            return False
        children = sorted(
            self.screen_node.GetChildrenName(slots_path) or (),
            key=self._grid_child_sort_key,
        )
        if len(children) < 27:
            return False
        columns = max(1, min(27, int(float(viewport_size[0]) // 28.0)))
        rows = (27 + columns - 1) // columns
        signature = (columns, rows)
        if signature == self.pocket_bag_layout_signature:
            return True
        for index, child_name in enumerate(children[:27]):
            control = self.screen_node.GetBaseUIControl(
                slots_path + "/" + child_name
            )
            if control is None:
                return False
            control.SetPosition((
                float((index % columns) * 28),
                float((index // columns) * 28),
            ))
        slots_panel.SetSize((float(columns * 28), float(rows * 28)))
        slots_panel.SetPosition((0.0, 0.0))
        self.pocket_bag_layout_signature = signature
        return True

    @staticmethod
    def _grid_child_sort_key(name):
        cursor = len(name)
        while cursor > 0 and name[cursor - 1].isdigit():
            cursor -= 1
        suffix = name[cursor:]
        return (int(suffix) if suffix else 0, name)

    def _grid_specs(self):
        if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN:
            bag_specs = (
                (self._pocket_bag_slots_path(), "inventory", 9, self.inventory_items[9:36]),
            )
        else:
            bag_specs = (
                (self.bag_path + "/bag_grid", "inventory", 9, self.inventory_items[9:36]),
            )
        return bag_specs + (
            (self.replica_path + "/hotbar_grid", "inventory", 0, self.inventory_items[0:9]),
            (self._curio_grid_path(), "curio", 0, self.curio_items),
        )

    def _refresh_pocket_static_hover_text(self):
        """Fill the active hover branch of a non-collection Pocket cell.

        A button creates its hover-control branch only after HoverIn.  The
        ordinary render pass can therefore run before ``hover_text`` exists.
        Grid cells solve that with a collection binding; the persistent
        Pocket cells intentionally have no collection context, so update the
        newly-created branch on the following UI tick instead.
        """
        if (
            self.screen_name != CURIO_INVENTORY_POCKET_SCREEN
            or not self._is_mouse_mode()
        ):
            return
        slots_path = self._pocket_bag_slots_path()
        children = sorted(
            self.screen_node.GetChildrenName(slots_path) or (),
            key=self._grid_child_sort_key,
        )
        for index, child_name in enumerate(children[:27]):
            hover_text = self.screen_node.GetBaseUIControl(
                slots_path
                + "/"
                + child_name
                + "/slot_button/hover/hover_text"
            )
            if hover_text is None:
                continue
            dto = (
                self.inventory_bag[index]
                if index < len(self.inventory_bag)
                else None
            )
            hover_text.SetPropertyBag({
                "#hover_text": (
                    dto.get("hoverText", "") if dto is not None else ""
                ),
            })

    def _grid_logical_index(self, domain, cell_index, slot_count):
        return cell_to_logical_slot(
            cell_index,
            slot_count,
            domain == "curio" and self.curio_layout == "expanded",
        )

    def _grid_cell_index(self, domain, logical_index):
        return logical_slot_to_cell(
            logical_index,
            domain == "curio" and self.curio_layout == "expanded",
        )

    def _bind_replica_buttons(self):
        if self.replica_buttons_complete:
            return
        expected_count = 0
        for grid_path, domain, first_slot, items in self._grid_specs():
            expected_count += len(items)
            for cell_index, child_name in enumerate(
                sorted(
                    self.screen_node.GetChildrenName(grid_path) or (),
                    key=self._grid_child_sort_key,
                )
            ):
                logical_index = self._grid_logical_index(
                    domain, cell_index, len(items)
                )
                if logical_index is None:
                    continue
                slot = first_slot + logical_index
                button_path = grid_path + "/" + child_name + "/slot_button"
                if button_path in self.bound_buttons:
                    continue
                control = self.screen_node.GetBaseUIControl(button_path)
                button = control.asButton() if control is not None else None
                if button is None:
                    continue
                button.AddTouchEventParams({"isSwallow": True})
                down = self._make_touch_callback(domain, slot, False)
                move = self._make_touch_callback(domain, slot, True)
                move_in = self._make_touch_move_in_callback(domain, slot)
                up = self._make_touch_up_callback(domain, slot)
                button.SetButtonTouchDownCallback(down)
                button.SetButtonTouchMoveCallback(move)
                button.SetButtonTouchMoveInCallback(move_in)
                button.SetButtonTouchUpCallback(up)
                cancel_setter = getattr(
                    button, "SetButtonTouchCancelCallback", None
                )
                if callable(cancel_setter):
                    cancel_setter(up)
                self.bound_buttons[button_path] = (down, move, move_in, up)
                self.bound_button_slots[button_path] = (domain, slot)
        self.replica_buttons_complete = bool(
            expected_count > 0
            and len(self.bound_button_slots) >= expected_count
        )

    def _make_touch_callback(self, domain, slot, moving):
        def callback(args):
            # Low-level callbacks do not identify the mouse button. Mouse
            # input must use the primary/secondary ViewBinder routes below;
            # otherwise right click is incorrectly consumed as primary.
            if self._is_mouse_mode():
                return
            if moving:
                self._on_touch_move(domain, slot, args)
            else:
                self._on_press_down(domain, slot, args, False)
        return callback

    def _make_touch_move_in_callback(self, domain, slot):
        def callback(args):
            self._on_press_move_in(domain, slot, args)
        return callback

    def _make_touch_up_callback(self, domain, slot):
        def callback(_args):
            if self._is_mouse_mode():
                return
            self._on_press_up(domain, slot, False)
        return callback

    @staticmethod
    def _touch_position(args):
        if type(args).__name__ != "dict":
            return None
        x = args.get("TouchPosX", args.get("touchPosX"))
        y = args.get("TouchPosY", args.get("touchPosY"))
        if type(x).__name__ not in ("int", "long", "float"):
            return None
        if type(y).__name__ not in ("int", "long", "float"):
            return None
        return (float(x), float(y))

    def _current_touch_position(self, args=None):
        """Return the current UI-space touch coordinate for an active gesture."""
        # F11 mouse-as-touch keeps GetTouchPos/callback coordinates at the
        # press sample on affected PC builds. ActorMotion is the live pointer
        # source while a native PushScreen is open, so use it before either
        # touch source for the whole simulated-touch gesture.
        touch_with_mouse = getattr(clientApi, "IsTouchWithMouse", None)
        if callable(touch_with_mouse) and touch_with_mouse():
            position = self._mouse_position()
            if position is not None:
                return position
        # Real vertical UI drags elsewhere in this project use TouchPosY from
        # the button callback. On affected profiles GetTouchPos updates X but
        # reports a stale/differently transformed Y, making left/right splits
        # work while up/down splits jump or stall. Keep callback coordinates as
        # the gesture's single source and reuse the last sample on UI ticks
        # that have no event args.
        callback_position = self._touch_position(args)
        if callback_position is not None:
            self.touch_gesture_position = callback_position
            return callback_position
        cached_position = getattr(self, "touch_gesture_position", None)
        if cached_position is not None:
            return cached_position
        # GetTouchPos remains a startup fallback for builds/callbacks that do
        # not provide TouchPosX/Y at all; it is never alternated into a gesture
        # after callback coordinates have been observed.
        getter = getattr(clientApi, "GetTouchPos", None)
        if callable(getter):
            position = getter()
            if (
                type(position).__name__ in ("tuple", "list")
                and len(position) >= 2
                and type(position[0]).__name__ in ("int", "long", "float")
                and type(position[1]).__name__ in ("int", "long", "float")
            ):
                return (float(position[0]), float(position[1]))
        return self._touch_position(args)

    def _on_press_down(self, domain, slot, args, secondary=False):
        if self.tick_count <= getattr(
            self, "shift_quick_suppress_until", -1
        ):
            return
        if self.pending is not None:
            if (
                self.pending.get("action") == "cursor_pick"
                and self.pending.get("mouseMode")
                and self.pending.get("sourceDomain") == domain
                and int(self.pending.get("sourceSlot", -1)) == int(slot)
            ):
                # Do not discard the physical second click just because the
                # first pickup has not completed its server round trip yet.
                self.pending["queuedDoubleClick"] = True
            return
        if self.page_transition_target is not None:
            return
        if self._touch_split_in_progress():
            # A touch split owns the complete gesture until release. Entering
            # another cell must adjust/finish that split, never start item
            # distribution from the provisional selected marker.
            return
        self.touch_gesture_position = None
        item = self._item_at(domain, slot)
        mouse_mode = self._is_mouse_mode()
        if (
            self.selection is None
            and item
            and not self._is_locked(item)
            and self._shift_down()
        ):
            # Replica slots do not reliably receive the native container's
            # menu_auto_place action. Execute the cloned Shift behavior at
            # the replica press boundary for either mouse button instead.
            self.shift_quick_suppress_until = self.tick_count + 2
            self.last_click = None
            self.last_click_tick = -100
            self._send_quick_move_from(
                domain, slot, item, animate_fly=True
            )
            return
        pos = None if mouse_mode else self._current_touch_position(args)
        self.press_state = {
            "domain": domain,
            "slot": slot,
            "secondary": bool(secondary),
            "mouseMode": mouse_mode,
            "ticks": 0,
            "position": pos,
            "reselectSplit": False,
        }
        if self.selection is not None:
            same_touch_source = bool(
                not mouse_mode
                and not secondary
                and not self.selection.get("mouseMode")
                and not self.selection.get("splitComplete")
                and self.selection.get("domain") == domain
                and int(self.selection.get("slot", -1)) == int(slot)
                and _item_count(item) > 1
                and pos is not None
            )
            if same_touch_source:
                # A normal touch selection may be long-pressed again to enter
                # split mode. A rapid second tap on an inventory source is the
                # native double-tap collection gesture; mark it here because
                # this reselect branch otherwise makes _activate_slot's
                # double-click path unreachable.
                self.press_state["reselectSplit"] = True
                self.press_state["touchDoubleCollect"] = bool(
                    domain == "inventory"
                    and self.last_click == (domain, slot)
                    and self.tick_count
                    - getattr(self, "last_click_tick", -100) <= 8
                )
                self._prepare_touch_split(domain, slot, pos, True)
                return
            drag = self.drag_state
            if (
                drag is not None
                and domain == "inventory"
                and drag.get("pressedTarget") == (domain, int(slot))
            ):
                # Classic mouse receives the direct button callback and the
                # secondary ViewBinder callback for a right press. Keep the
                # first target and only upgrade its distribution mode.
                if secondary and drag.get("mode") != "single":
                    drag["mode"] = "single"
                    if drag.get("moved"):
                        self._update_drag_preview()
                return
            self._begin_drag(domain, slot, secondary)
            return
        if not item:
            self.split_state = None
            return
        if mouse_mode:
            self.split_state = {
                "domain": domain,
                "slot": slot,
                "count": 0,
                "active": False,
                "legacy": True,
            }
            return
        if pos is None:
            self.split_state = None
            return
        self._prepare_touch_split(domain, slot, pos, False)

    def _prepare_touch_split(self, domain, slot, pos, reselect=False):
        source_center = self._slot_center(domain, slot, pos)
        source_control = self._slot_control(domain, slot)
        source_size = source_control.GetSize() if source_control is not None else None
        if (
            not source_size
            or float(source_size[0]) <= 0
            or float(source_size[1]) <= 0
        ):
            source_size = (
                (28.0, 28.0)
                if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
                else (18.0, 18.0)
            )
        # Direction is resolved and locked at activation from this source
        # geometry and the then-current pointer position.
        self.split_direction = "down"
        self.split_render_direction = None
        self.split_render_progress = None
        self.split_state = {
            "domain": domain,
            "slot": slot,
            "start": pos,
            "overlayPosition": source_center,
            "sourceCenter": source_center,
            "sourceSize": tuple(source_size),
            "directionLocked": False,
            "axisOrigin": None,
            "count": 0,
            "active": False,
            "legacy": False,
            "reselectSplit": bool(reselect),
        }

    def _on_touch_move(self, domain, slot, args):
        state = self.split_state
        if (
            type(state).__name__ != "dict"
            or state.get("domain") != domain
            or state.get("slot") != slot
        ):
            return
        pos = self._current_touch_position(args)
        if pos is None:
            return
        self._update_touch_split(pos)

    def _update_touch_split(self, pos):
        state = self.split_state
        if (
            type(state).__name__ != "dict"
            or state.get("legacy")
            or not state.get("active")
        ):
            return
        if not state.get("directionLocked"):
            return
        total = _item_count(
            self._item_at(state.get("domain"), state.get("slot"))
        )
        if total <= 1:
            return
        direction = self.split_direction
        axis_position = self._split_axis_position(pos, direction)
        origin = state.get("axisOrigin")
        if origin is None:
            state["axisOrigin"] = axis_position
            return
        distance = max(0.0, axis_position - float(origin))
        raw_target = max(
            1,
            min(
                total,
                1 + int(distance / TOUCH_SPLIT_PIXELS_PER_ITEM),
            ),
        )
        target = max(1, min(total, int(state.get("count", 1))))
        if raw_target > target:
            target = raw_target
        elif raw_target < target:
            reverse_boundary = (
                float(target - 1) * TOUCH_SPLIT_PIXELS_PER_ITEM
                - TOUCH_SPLIT_REVERSE_HYSTERESIS
            )
            if distance <= reverse_boundary:
                target = raw_target
        # This is direct manipulation: the visible value must represent the
        # current absolute finger projection in this callback/tick. The old
        # one-item-per-tick convergence made fast drags visibly lag behind.
        # Boundary stability is still provided by the reverse hysteresis.
        state["count"] = target
        if self.selection is not None:
            self.selection["count"] = state["count"]
            self.selection["sourceHiddenCount"] = state["count"]
        self._set_split_progress(state["count"], total)

    def _lock_touch_split_direction(self, position):
        state = self.split_state
        if type(state).__name__ != "dict" or state.get("directionLocked"):
            return
        center = state.get("sourceCenter") or state.get("overlayPosition")
        if center is None:
            center = state.get("start") or position
        delta_x = float(position[0]) - float(center[0])
        delta_y = float(position[1]) - float(center[1])
        if abs(delta_x) >= abs(delta_y):
            self.split_direction = "right" if delta_x >= 0 else "left"
        else:
            self.split_direction = "down" if delta_y >= 0 else "up"
        state["directionLocked"] = True
        state["axisOrigin"] = self._split_axis_position(
            position, self.split_direction
        )

    @staticmethod
    def _split_axis_position(position, direction):
        """Project onto the horizontal amount axis of every split-bar layout.

        Up/down/left/right name where the horizontal 64px bar is placed around
        the source cell; they are not four drag axes. Every layout uses the
        same left-to-right amount axis: moving right increases the count.
        """
        return float(position[0])

    def _on_press_move_in(self, domain, slot, args=None):
        state = self.split_state
        if (
            type(state).__name__ == "dict"
            and state.get("active")
            and not state.get("legacy")
        ):
            position = self._current_touch_position(args)
            if position is not None:
                self._update_touch_split(position)
            return
        drag = self.drag_state
        if drag is None:
            return
        if self._add_drag_target(domain, slot):
            drag["moved"] = True
            self._update_drag_preview()

    def _on_press_up(self, domain, slot, secondary=False):
        self.touch_gesture_position = None
        if getattr(self, "quick_move_pressed", None) is not None:
            # Some profiles emit the ordinary primary/secondary Up before the
            # quick mapping Up, while others emit only quick Down. Either way
            # this is the release of the already-executed physical gesture.
            self.quick_move_pressed = None
            self.shift_quick_suppress_until = self.tick_count + 2
            self.press_state = None
            self.drag_state = None
            return
        if self.tick_count <= getattr(
            self, "shift_quick_suppress_until", -1
        ):
            self.press_state = None
            self.drag_state = None
            return
        drag = self.drag_state
        if drag is not None and drag.get("moved"):
            if not drag.get("mouseMode"):
                # Touch release terminates selection unconditionally. Server
                # success/failure only decides the authoritative item image;
                # it must never keep the completed gesture selected.
                self.selection = None
                self._selection_changed()
            self._submit_drag_distribution()
            return
        if drag is not None and self.selection is not None:
            self.selection["count"] = int(drag.get("heldCount", 1))
        self.drag_state = None
        press = self.press_state
        state = self.split_state
        if (
            press is not None
            and press.get("touchDoubleCollect")
            and not (state and state.get("active"))
        ):
            source_domain = press.get("domain")
            source_slot = press.get("slot")
            source_item = self._item_at(source_domain, source_slot)
            self.press_state = None
            self.split_state = None
            self._hide_split_overlay()
            self.last_click = None
            self.last_click_tick = -100
            self._send_double_click(source_slot, source_item)
            return
        split_release = bool(
            state
            and state.get("active")
            and (
                not state.get("legacy")
                or (
                    state.get("domain") == domain
                    and state.get("slot") == slot
                )
            )
        )
        if split_release:
            source_domain = state.get("domain")
            source_slot = state.get("slot")
            item = self._item_at(source_domain, source_slot)
            if state.get("legacy"):
                sent = self.client_system.PickCurioInventoryCursor(
                    source_domain,
                    source_slot,
                    state.get("count", 1),
                    item,
                )
                self.press_state = None
                self.split_state = None
                self._hide_split_overlay()
                if sent:
                    self.pending = {
                        "action": "cursor_pick",
                        "requestId": sent,
                        "sourceDomain": source_domain,
                        "sourceSlot": source_slot,
                        "sourceItem": copy.deepcopy(item),
                        "mouseMode": True,
                        "animateFly": False,
                        # Keep the already-resolved slot hit route alive under
                        # a stationary pointer. self.pending still guards the
                        # whole transaction while authority is in flight.
                        "preserveReplicaTouch": True,
                    }
                    self.pending_ticks = 0
                return
            # The directional bar belongs only to the active press. Hide it
            # before installing the completed selection so the legacy bar can
            # take over in this same release callback without both renderers
            # remaining visible for a frame.
            self._hide_directional_split_overlay()
            if self.selection is None:
                self.selection = {
                    "domain": source_domain,
                    "slot": source_slot,
                    "count": state.get("count", 1),
                    "sourceHiddenCount": state.get("count", 1),
                    "item": copy.deepcopy(item),
                    "mouseMode": False,
                    "splitComplete": True,
                    "splitTotal": _item_count(item),
                    "splitSourceCenter": state.get("sourceCenter"),
                    "splitSourceSize": state.get("sourceSize"),
                }
            else:
                self.selection["count"] = state.get("count", 1)
                self.selection["sourceHiddenCount"] = state.get("count", 1)
                self.selection["splitComplete"] = True
                self.selection["splitTotal"] = _item_count(item)
            self.press_state = None
            self.split_state = None
            self._selection_changed()
            return
        if state and state.get("reselectSplit"):
            # The second touch owns two mutually exclusive outcomes: holding
            # reaches the split threshold, while releasing before it is the
            # native same-cell cancel gesture on both Classic and Pocket.
            self.press_state = None
            self.split_state = None
            self._hide_split_overlay()
            self.selection = None
            self.last_click = None
            self.last_click_tick = -100
            self._selection_changed()
            return
        self.press_state = None
        self.split_state = None
        self._hide_split_overlay()
        self._activate_slot(domain, slot, secondary)

    def _tick_press_state(self):
        press = self.press_state
        if (
            press is None
            or (
                self.selection is not None
                and not self._touch_split_in_progress()
                and not press.get("reselectSplit")
            )
            or self.drag_state is not None
        ):
            return
        press["ticks"] += 1
        if press.get("secondary"):
            return
        item = self._item_at(press.get("domain"), press.get("slot"))
        total = _item_count(item)
        if total <= 1 or press["ticks"] < 10 or self.split_state is None:
            return
        if not press.get("mouseMode"):
            if not self.split_state.get("active"):
                # Resolve the source geometry once at activation. Pocket grid
                # children can be unavailable on the original touch-down but
                # are stable by the long-press threshold; the bar is never
                # repositioned after this capture.
                source = self._slot_control(
                    press.get("domain"), press.get("slot")
                )
                if source is not None:
                    source_position = source.GetGlobalPosition()
                    source_size = source.GetSize()
                    if (
                        source_position is not None
                        and source_size is not None
                        and float(source_size[0]) > 0
                        and float(source_size[1]) > 0
                    ):
                        source_center = (
                            float(source_position[0])
                            + float(source_size[0]) * 0.5,
                            float(source_position[1])
                            + float(source_size[1]) * 0.5,
                        )
                        self.split_state["overlayPosition"] = source_center
                        self.split_state["sourceCenter"] = source_center
                        self.split_state["sourceSize"] = tuple(source_size)
                self.split_state["active"] = True
                self.split_state["count"] = 1
                position = self._current_touch_position()
                if position is None:
                    position = self.split_state.get("start")
                if position is not None:
                    self._lock_touch_split_direction(position)
                self.selection = {
                    "domain": press.get("domain"),
                    "slot": press.get("slot"),
                    "count": 1,
                    "sourceHiddenCount": 1,
                    "item": copy.deepcopy(item),
                    "mouseMode": False,
                    "splitComplete": False,
                    "splitTotal": total,
                    "splitSourceCenter": self.split_state.get("sourceCenter"),
                    "splitSourceSize": self.split_state.get("sourceSize"),
                }
                self._selection_changed()
                self._show_split_overlay(
                    self.split_state.get(
                        "overlayPosition", self.split_state.get("start")
                    ),
                    1,
                    total,
                )
            position = self._current_touch_position()
            if position is not None:
                self._update_touch_split(position)
                return
            self._set_split_progress(self.split_state.get("count", 1), total)
            return
        count = min(
            total,
            max(
                1,
                int(
                    (press["ticks"] - 10)
                    * total
                    / MOUSE_SPLIT_FILL_TICKS
                ),
            ),
        )
        self.split_state["active"] = True
        self.split_state["count"] = count
        self._show_mouse_split_overlay(count, total)

    def _touch_split_in_progress(self):
        state = self.split_state
        return bool(
            type(state).__name__ == "dict"
            and state.get("active")
            and not state.get("legacy")
        )

    def _begin_drag(self, domain, slot, secondary):
        source = self.selection
        if self._is_locked(source.get("item") or {}):
            # Touch may inspect and split lock_in_slot stacks, but the lock
            # still forbids distribution, placement and swapping.
            return
        cursor_owned = bool(source.get("cursorOwned"))
        if (
            source.get("domain") != "inventory"
            and not cursor_owned
        ) or domain != "inventory":
            return
        origin = source.get("cursorOrigin") or {}
        source_slot = (
            origin.get("inventorySlot", -1)
            if cursor_owned else source.get("slot")
        )
        self.drag_state = {
            "sourceDomain": "cursor" if cursor_owned else "inventory",
            "sourceSlot": int(source_slot),
            "sourceItem": copy.deepcopy(
                source.get("item")
                if cursor_owned
                else self._item_at("inventory", source.get("slot"))
            ),
            "heldCount": int(source.get("count", 1)),
            "mouseMode": bool(source.get("mouseMode")),
            "cursorOwned": cursor_owned,
            "cursorOrigin": copy.deepcopy(origin),
            "mode": "single" if secondary else "even",
            "targets": [],
            "targetBySlot": {},
            "moved": False,
            "plannedMoved": 0,
            "allocations": {},
            "pressedTarget": (domain, int(slot)),
            "distributionId": int(self.next_distribution_id),
            "streamStarted": False,
        }
        self.next_distribution_id += 1
        if not self._add_drag_target(domain, slot):
            self.drag_state = None
        elif self.selection is not None:
            # Merely pressing a destination is still a normal one-slot place.
            # Distribution preview begins only after entering another slot.
            # Do not rebuild the collection while this first button still
            # owns the touch. Pocket destroys/recreates the pressed cell on a
            # rebuild, losing its TouchUp and forcing a second target click;
            # it also breaks the following MoveIn distribution trajectory.
            self.selection["count"] = int(self.drag_state.get("heldCount", 1))

    def _add_drag_target(self, domain, slot):
        drag = self.drag_state
        if drag is None or domain != "inventory":
            return False
        key = (domain, int(slot))
        if not drag.get("cursorOwned") and int(slot) == drag.get("sourceSlot"):
            return False
        existing = (drag.get("targetBySlot") or {}).get(int(slot))
        if existing is not None:
            if (
                drag.get("mode") == "single"
                and sum(
                    int(entry.get("weight", 1))
                    for entry in drag.get("targets", [])
                ) >= int(drag.get("heldCount", 0))
            ):
                return False
            existing["weight"] = int(existing.get("weight", 1)) + 1
            return True
        # Every accepted distribution target must receive at least one item.
        # Once the target count reaches the held count, accepting another cell
        # would make its quota zero (for example 10 items over 11 cells).
        if len(drag.get("targets", [])) >= int(drag.get("heldCount", 0)):
            return False
        target = self._item_at(domain, slot)
        source = drag.get("sourceItem") or {}
        if self._is_locked(target) or (target and not self._same_stack(source, target)):
            return False
        if _item_count(target) >= self._client_max_stack_size(source):
            return False
        entry = {
            "slot": int(slot),
            "weight": 1,
            "expected": copy.deepcopy(target or {}),
        }
        drag["targets"].append(entry)
        drag["targetBySlot"][int(slot)] = entry
        # The caller recomputes the complete preview after the target set has
        # changed. Keeping that update in one place avoids two collection
        # rebuilds for every cell after the first.
        return True

    def _client_item_basic_info(self, item):
        cache = self._item_basic_info_cache
        cache_key = (
            _item_name(item),
            _item_aux(item),
            bool(item.get("isEnchanted") or item.get("enchantData")),
        )
        if not cache_key[0]:
            return {}
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        player_id = clientApi.GetLocalPlayerId()
        item_comp = (
            clientApi.GetEngineCompFactory().CreateItem(player_id)
            if player_id else None
        )
        getter = getattr(item_comp, "GetItemBasicInfo", None)
        info = (
            getter(cache_key[0], cache_key[1], cache_key[2])
            if callable(getter) else None
        )
        result = info if type(info).__name__ == "dict" else {}
        cache[cache_key] = result
        return result

    def _client_max_durability(self, item):
        if type(item).__name__ != "dict":
            return 0
        maximum = item.get("maxDurability")
        if _is_int(maximum) and int(maximum) > 0:
            return int(maximum)
        info = self._client_item_basic_info(item)
        maximum = info.get("maxDurability", info.get("max_durability"))
        return int(maximum) if _is_int(maximum) and int(maximum) > 0 else 0

    def _client_durability_state(self, item):
        """Return (visible, total, remaining) using NetEase item semantics."""
        total = self._client_max_durability(item)
        if not _is_int(total) or int(total) <= 0:
            return (False, 1, 1)
        total = int(total)
        # GetPlayerItem and Get/SetItemDurability expose remaining durability,
        # not damage taken. Missing durability means an undamaged item.
        current = (
            item.get("durability")
            if type(item).__name__ == "dict" else None
        )
        if not _is_int(current):
            current = total
        current = max(0, min(total, int(current)))
        return (current < total, total, current)

    def _client_max_stack_size(self, item):
        cache_key = (
            _item_name(item),
            _item_aux(item),
            bool(item.get("isEnchanted") or item.get("enchantData")),
            bool(item.get("maxDurability")),
        )
        cached = self._max_stack_cache.get(cache_key)
        if cached is not None:
            return cached
        info = self._client_item_basic_info(item)
        if type(info).__name__ == "dict":
            maximum = info.get("maxStackSize", info.get("max_stack_size"))
            if _is_int(maximum) and int(maximum) > 0:
                result = int(maximum)
                self._max_stack_cache[cache_key] = result
                return result
        result = 1 if item.get("maxDurability") else 64
        self._max_stack_cache[cache_key] = result
        return result

    def _update_drag_preview(self):
        drag = self.drag_state
        if drag is None or not drag.get("targets"):
            return
        held = int(drag.get("heldCount", 0))
        total_weight = sum(
            int(entry.get("weight", 1)) for entry in drag["targets"]
        )
        if drag.get("mode") == "single":
            quotas = [
                int(entry.get("weight", 1))
                for entry in drag["targets"]
            ]
        else:
            # Preserve floor quotas (the indivisible remainder stays held),
            # but never give an accepted target a zero quota.
            quotas = [
                max(
                    1,
                    held * int(entry.get("weight", 1)) // total_weight,
                )
                for entry in drag["targets"]
            ]
            overflow = max(0, sum(quotas) - held)
            while overflow > 0:
                largest = max(
                    range(len(quotas)), key=lambda index: quotas[index]
                )
                if quotas[largest] <= 1:
                    break
                quotas[largest] -= 1
                overflow -= 1
        maximum = self._client_max_stack_size(drag.get("sourceItem") or {})
        held_remaining = held
        allocations = {}
        for index, entry in enumerate(drag["targets"]):
            target = entry.get("expected") or {}
            moved = min(
                max(0, maximum - _item_count(target)),
                quotas[index],
                held_remaining,
            )
            if moved > 0:
                allocations[int(entry.get("slot"))] = moved
                held_remaining -= moved
        drag["allocations"] = allocations
        drag["plannedMoved"] = held - held_remaining
        if self.selection is not None:
            # Zero remainder only hides the held/selected image. It does not
            # end the active touch gesture; TouchUp below owns the real finish
            # request and the logical selection cancellation.
            self.selection["count"] = held_remaining
        self._selection_changed()
        sent = self.client_system.UpdateCurioInventoryDistribution(
            drag.get("distributionId"),
            bool(drag.get("cursorOwned")),
            drag.get("sourceSlot"),
            drag.get("sourceItem"),
            drag.get("heldCount"),
            drag.get("targets"),
            drag.get("mode"),
        )
        if sent:
            drag["streamStarted"] = True
            drag["lastUpdateRequestId"] = sent

    def _submit_drag_distribution(self):
        drag = self.drag_state
        if drag is None:
            return
        self.drag_state = None
        self.press_state = None
        self.split_state = None
        self._hide_split_overlay()
        if not drag.get("streamStarted"):
            self.committed_drag_preview = None
            self.selection = (
                self._selection_from_drag(drag)
                if drag.get("mouseMode") else None
            )
            self._selection_changed()
            return
        sent = self.client_system.FinishCurioInventoryDistribution(
            drag.get("distributionId")
        )
        if sent:
            self.committed_drag_preview = copy.deepcopy(drag)
            self.pending = {
                "action": "distribute_finish",
                "distributionId": int(drag.get("distributionId", 0)),
                # A server-owned cursor is not the inventory slot it was
                # originally picked from. That origin is a legal distribution
                # target and must never be read back as the held remainder.
                "sourceDomain": drag.get("sourceDomain"),
                "sourceSlot": drag.get("sourceSlot"),
                "sourceItem": copy.deepcopy(drag.get("sourceItem") or {}),
                "baseUnheld": max(
                    0,
                    _item_count(drag.get("sourceItem")) - drag.get("heldCount", 0),
                ),
                "mouseMode": bool(drag.get("mouseMode")),
                "cursorOwned": bool(drag.get("cursorOwned")),
                # Legacy virtual selection reconstructs its remainder from a
                # real source inventory slot, matching the embedded project.
                # The hidden cursor is reconstructed exclusively from the
                # authoritative cursorItem in RefreshCurioState.
                "continueDistribution": False,
                "animateFly": False,
                "requestId": sent,
            }
            self.pending_ticks = 0
            self.replica_control.SetTouchEnable(False)
            if (
                not drag.get("mouseMode")
                or int(drag.get("plannedMoved", 0)) >= int(
                    drag.get("heldCount", 0)
                )
            ):
                # Releasing a touch distribution always ends the selected-cell
                # gesture, even when the real source slot keeps a remainder.
                # Mouse mode may keep only a genuine cursor remainder; once
                # fully consumed it must also disappear immediately.
                self.selection = None
        else:
            self.committed_drag_preview = None
            self.selection = (
                self._selection_from_drag(drag)
                if drag.get("mouseMode") else None
            )
        self._selection_changed()

    @staticmethod
    def _selection_from_drag(drag):
        """Rebuild the pre-drag selection after an unsubmitted preview."""
        held = max(0, int(drag.get("heldCount", 0)))
        if held <= 0:
            return None
        item = copy.deepcopy(drag.get("sourceItem") or {})
        if drag.get("cursorOwned"):
            return {
                "domain": "cursor",
                "slot": -1,
                "count": held,
                "item": _copy_client_stack(item, held),
                "mouseMode": True,
                "cursorOwned": True,
                "cursorOrigin": copy.deepcopy(
                    drag.get("cursorOrigin") or {}
                ),
            }
        return {
            "domain": "inventory",
            "slot": int(drag.get("sourceSlot", -1)),
            "count": held,
            "sourceHiddenCount": held,
            "item": item,
            "mouseMode": bool(drag.get("mouseMode")),
        }

    def _show_split_overlay(self, position, count, total):
        if position is None:
            return
        control = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/split_overlay"
        )
        if control is not None:
            # This panel is script-owned. Keep the root closed while its
            # direction, clip ratio and label are updated synchronously.
            control.SetVisible(False)
            self._set_global_position(control, position)
        progress_ready = self._set_split_progress(count, total)
        if control is not None and progress_ready:
            control.SetVisible(True)

    def _set_split_progress(self, count, total):
        total = max(1, int(total))
        count = max(0, min(total, int(count)))
        self.split_text = "{}/{}".format(count, total)
        self.split_ratio = min(1.0, float(count) / float(total))
        progress = (getattr(self, "split_direction", "down"), count, total)
        if progress == getattr(self, "split_render_progress", None):
            return True
        if self._refresh_directional_split_progress():
            self.split_render_progress = progress
            return True
        return False

    def _refresh_directional_split_progress(self):
        """Update the fixed touch bar without waiting for binder polling."""
        screen = getattr(self, "screen_node", None)
        overlay_path = getattr(self, "overlay_path", None)
        if screen is None or not overlay_path:
            return False
        active_direction = getattr(self, "split_direction", "down")
        direction_controls_ready = True
        if getattr(self, "split_render_direction", None) != active_direction:
            for direction in ("down", "up", "left", "right"):
                direction_control = screen.GetBaseUIControl(
                    overlay_path + "/split_overlay/" + direction
                )
                if direction_control is None:
                    direction_controls_ready = False
                    continue
                direction_control.SetVisible(direction == active_direction)
            if direction_controls_ready:
                self.split_render_direction = active_direction
        base_path = (
            overlay_path + "/split_overlay/" + active_direction + "/arrow"
        )
        fill = screen.GetBaseUIControl(base_path + "/fill")
        image = fill.asImage() if fill is not None else None
        clip_setter = getattr(image, "SetSpriteClipRatio", None)
        if callable(clip_setter):
            clip_setter(1.0 - float(getattr(self, "split_ratio", 0.0)))
        text_control = screen.GetBaseUIControl(base_path + "/text")
        label = text_control.asLabel() if text_control is not None else None
        text_setter = getattr(label, "SetText", None)
        if callable(text_setter):
            text_setter(getattr(self, "split_text", ""))
        return bool(
            direction_controls_ready
            and callable(clip_setter)
            and callable(text_setter)
        )

    def _show_legacy_split_overlay(self, position, count, total):
        if position is None:
            return
        host = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/legacy_split_overlay"
        )
        progress = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/legacy_split_overlay/progress"
        )
        if host is not None and progress is not None:
            # Keep the ordinary panel host hidden while both the script DTO
            # and the renderer's live property bag are updated. The inner
            # progress_bar_renderer retains its required ViewBinder wiring.
            host.SetVisible(False)
            touch_release = bool(
                self.selection
                and not self.selection.get("mouseMode")
                and self.selection.get("splitComplete")
            )
            host.SetSize(self._legacy_split_size(touch_release))
            self.legacy_progress_total = max(1, int(total))
            self.legacy_progress_current = max(
                0, min(self.legacy_progress_total, int(count))
            )
            self._set_global_position(host, position)
            properties_set = progress.SetPropertyBag({
                "#progress_bar_total_amount": self.legacy_progress_total,
                "#progress_bar_current_amount": self.legacy_progress_current,
                "#progress_bar_visible": True,
                "#touch_progress_bar_visible": True,
            })
            if properties_set is not False:
                host.SetVisible(True)

    def _legacy_split_size(self, touch_release=False):
        if (
            touch_release
            and self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
        ):
            return POCKET_TOUCH_LEGACY_SPLIT_SIZE
        return CLASSIC_LEGACY_SPLIT_SIZE

    def _show_mouse_split_overlay(self, count, total):
        position = self._mouse_position()
        control = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/legacy_split_overlay"
        )
        if position is None or control is None:
            return
        bar_size = CLASSIC_LEGACY_SPLIT_SIZE
        native_offset_y = (
            -18.0
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            else -12.0
        )
        self._show_legacy_split_overlay(
            (
                float(position[0]) - float(bar_size[0]) * 0.5,
                float(position[1]) + native_offset_y
                - float(bar_size[1]) * 0.5 + 0.5,
            ),
            count,
            total,
        )

    def _sync_completed_touch_split_overlay(self):
        selection = self.selection
        legacy = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/legacy_split_overlay"
        )
        completed = bool(
            selection
            and not selection.get("mouseMode")
            and selection.get("splitComplete")
        )
        if not completed:
            if legacy is not None and not (
                self.split_state and self.split_state.get("legacy")
            ):
                legacy.SetVisible(False)
            return
        if legacy is None:
            return
        center = selection.get("splitSourceCenter")
        size = selection.get("splitSourceSize")
        position = None
        if center is not None and size is not None:
            position = (
                float(center[0]) - float(size[0]) * 0.5,
                float(center[1]) - float(size[1]) * 0.5,
            )
        else:
            control = self._slot_control(
                selection.get("domain"), selection.get("slot")
            )
            if control is not None:
                position = control.GetGlobalPosition()
                size = control.GetSize()
        bar_size = self._legacy_split_size(True)
        native_top_inset = 1.0
        if position is None or size is None:
            return
        self._show_legacy_split_overlay(
            (
                float(position[0])
                + (float(size[0]) - float(bar_size[0])) * 0.5,
                float(position[1]) + native_top_inset,
            ),
            selection.get("count", 1),
            selection.get("splitTotal", _item_count(selection.get("item") or {})),
        )

    def _hide_directional_split_overlay(self):
        self.split_render_direction = None
        self.split_render_progress = None
        if self.screen_node is None or not self.overlay_path:
            return
        control = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/split_overlay"
        )
        if control is not None:
            control.SetVisible(False)

    def _hide_split_overlay(self):
        self._hide_directional_split_overlay()
        if self.screen_node is None or not self.overlay_path:
            return
        legacy = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/legacy_split_overlay"
        )
        if legacy is not None:
            legacy.SetVisible(False)

    def _cancel_transient_state(
        self,
        clear_selection=True,
        cancel_fly=True,
        clear_pending=False,
    ):
        """Drop UI-only gestures without mutating authoritative inventory."""
        if clear_selection:
            self.selection = None
            self.held_item_active = False
            self.held_item_reveal_tick = None
        self.touch_gesture_position = None
        self.quick_move_pressed = None
        self.split_state = None
        self.press_state = None
        self.drag_state = None
        self.committed_drag_preview = None
        self.last_click = None
        self.last_click_tick = -100
        self._hide_split_overlay()
        if self.screen_node is not None and self.overlay_path:
            held = self.screen_node.GetBaseUIControl(
                self.overlay_path + "/held_item"
            )
            if held is not None:
                held.SetVisible(False)
            if cancel_fly:
                fly = self.screen_node.GetBaseUIControl(
                    self.overlay_path + "/fly_item"
                )
                if fly is not None:
                    fly.SetVisible(False)
        if cancel_fly:
            self.fly_state = None
            self.fly_target_override = None
        if clear_pending:
            self.pending = None
            self.pending_ticks = 0
        if self.screen_node is not None and self.overlay_path:
            self._remove_touch_item_details()
        if self.created:
            self._rebuild_view_models()
            self.render_dirty = True

    def _item_at(self, domain, slot):
        values = self.inventory_items if domain == "inventory" else self.curio_items
        if not _is_int(slot) or int(slot) < 0 or int(slot) >= len(values):
            return {}
        return values[int(slot)]

    def _slot_center(self, domain, slot, fallback=None):
        control = self._slot_control(domain, slot)
        if control is None:
            return fallback
        position = control.GetGlobalPosition()
        size = control.GetSize()
        if position is None or size is None:
            return fallback
        return (
            float(position[0]) + float(size[0]) * 0.5,
            float(position[1]) + float(size[1]) * 0.5,
        )

    def _activate_slot(self, domain, slot, secondary=False):
        if (
            self.pending is not None
            or self.page_transition_target is not None
            or not self._chatelaine_visible()
        ):
            return
        item = self._item_at(domain, slot)
        mouse_mode = self._is_mouse_mode()
        if self.split_state and self.split_state.get("active"):
            split = self.split_state
            if split.get("domain") == domain and split.get("slot") == slot:
                self.selection = {
                    "domain": domain,
                    "slot": slot,
                    "count": split.get("count", 1),
                    "sourceHiddenCount": split.get("count", 1),
                    "item": copy.deepcopy(item),
                    "mouseMode": mouse_mode,
                }
                self.split_state = None
                self._hide_split_overlay()
                self._selection_changed()
                return
        self.split_state = None
        self._hide_split_overlay()

        if self.selection is None:
            if not item or (self._is_locked(item) and mouse_mode):
                return
            count = _item_count(item)
            take_count = (count + 1) // 2 if secondary else count
            if self._shift_down():
                # Both mouse buttons use native-style Shift quick move. The
                # keyboard modifier also remains valid when Pocket/F11 maps
                # pointer input through touch callbacks.  It takes precedence
                # over right-click half pickup and moves the complete stack.
                self.last_click = None
                self.last_click_tick = -100
                self._send_quick_move_from(
                    domain, slot, item, animate_fly=True
                )
                return
            double_click = bool(
                domain == "inventory"
                and self.last_click == (domain, slot)
                and self.tick_count - getattr(self, "last_click_tick", -100) <= 8
            )
            self.last_click = (domain, slot)
            self.last_click_tick = self.tick_count
            if double_click:
                if mouse_mode and self._shift_down():
                    # The first click is server-authoritative, so this branch
                    # only remains for touch/legacy selection timing.
                    self._send_quick_move(slot, item)
                else:
                    self._send_double_click(slot, item)
                return
            if mouse_mode:
                sent = self.client_system.PickCurioInventoryCursor(
                    domain, slot, take_count, item
                )
                if sent:
                    self.pending = {
                        "action": "cursor_pick",
                        "requestId": sent,
                        "sourceDomain": domain,
                        "sourceSlot": slot,
                        "sourceItem": copy.deepcopy(item),
                        "mouseMode": True,
                        "animateFly": False,
                        "preserveReplicaTouch": True,
                    }
                    self.pending_ticks = 0
                    # Keep the grid receiving presses while this pickup is in
                    # flight so the second physical click can be queued. All
                    # other actions remain guarded by self.pending.
                return
            self.selection = {
                "domain": domain,
                "slot": slot,
                "count": take_count,
                "sourceHiddenCount": take_count,
                "item": copy.deepcopy(item),
                "mouseMode": mouse_mode,
            }
            self._selection_changed()
            return

        source = self.selection
        if source.get("cursorOwned"):
            double_click = bool(
                domain == "inventory"
                and self.last_click == (domain, slot)
                and self.tick_count
                - getattr(self, "last_click_tick", -100) <= 8
            )
            self.last_click = (domain, slot)
            self.last_click_tick = self.tick_count
            if double_click:
                if self._shift_down():
                    self._send_cursor_quick_move(source)
                else:
                    self._send_cursor_double_click(source)
                return
            take_count = 1 if secondary else source.get("count", 1)
            self._send_transfer(source, domain, slot, take_count, item)
            return
        if source.get("domain") == domain and source.get("slot") == slot:
            if (
                domain == "inventory"
                and self.last_click == (domain, slot)
                and self.tick_count - getattr(self, "last_click_tick", -100) <= 8
            ):
                self._send_double_click(slot, item)
            else:
                self.selection = None
                self._selection_changed()
            return
        if self._is_locked(source.get("item") or {}):
            # Touch may select and split lock_in_slot stacks, but no transfer,
            # swap or distribution may originate from that virtual selection.
            return
        take_count = 1 if secondary else source.get("count", 1)
        self._send_transfer(source, domain, slot, take_count, item)

    @staticmethod
    def _is_locked(item):
        return _item_lock_mode(item) == "lock_in_slot"

    def _send_transfer(
        self,
        source,
        target_domain,
        target_slot,
        take_count,
        target,
        animate_fly=None,
        continue_mouse_hold=None,
    ):
        mouse_mode = bool(source.get("mouseMode"))
        if animate_fly is None:
            animate_fly = not mouse_mode
        # Ordinary mouse transfers still resolve None to False.  An explicit
        # True is reserved for Shift quick move, whose stack never becomes a
        # cursor-held item and therefore needs the same fly feedback as touch.
        if continue_mouse_hold is None:
            continue_mouse_hold = mouse_mode
        if source.get("cursorOwned"):
            sent = self.client_system.PlaceCurioInventoryCursor(
                target_domain,
                target_slot,
                take_count,
                source.get("item"),
                target,
            )
        else:
            sent = self.client_system.TransferCurioInventory(
                source.get("domain"),
                source.get("slot"),
                target_domain,
                target_slot,
                take_count,
                source.get("item"),
                target,
            )
        if sent:
            self.pending = {
                "action": "transfer",
                "requestId": sent,
                "sourceDomain": source.get("domain"),
                "sourceSlot": source.get("slot"),
                "targetDomain": target_domain,
                "targetSlot": target_slot,
                "item": copy.deepcopy(source.get("item") or {}),
                "targetItem": copy.deepcopy(target or {}),
                "mouseMode": mouse_mode,
                "cursorOwned": bool(source.get("cursorOwned")),
                "baseUnheld": max(
                    0,
                    _item_count(source.get("item") or {})
                    - int(source.get("count", 1)),
                ),
                "animateFly": bool(animate_fly),
                "continueMouseHold": bool(
                    continue_mouse_hold
                ),
                # Mouse placement remains guarded by pending in both Down and
                # Up activation paths. Keeping the already-enabled replica
                # root stable preserves its live hit target and Hover state;
                # touch still locks the root for the complete gesture.
                "preserveReplicaTouch": bool(mouse_mode),
            }
            self.pending_ticks = 0
            if not mouse_mode:
                self.replica_control.SetTouchEnable(False)

    def _activate_drop(self, secondary):
        if (
            self.client_system is None
            or self.pending is not None
            or self.drag_state is not None
            or self.page_transition_target is not None
            or not self._chatelaine_visible()
            or self.selection is None
        ):
            return
        source = self.selection
        source_item = source.get("item") or {}
        # A drop leaves the inventory entirely, so both vanilla item-lock
        # variants forbid it. The server repeats this check authoritatively.
        if _item_lock_mode(source_item) is not None:
            return
        selected_count = max(0, int(source.get("count", 0)))
        if selected_count <= 0 or not _item_name(source_item):
            return
        take_count = 1 if secondary else selected_count
        source_domain = (
            "cursor" if source.get("cursorOwned") else source.get("domain")
        )
        source_slot = source.get("slot")
        sent = self.client_system.DropCurioInventory(
            source_domain,
            source_slot,
            take_count,
            source_item,
        )
        if not sent:
            return
        mouse_mode = bool(source.get("mouseMode"))
        self.pending = {
            "action": "drop",
            "requestId": sent,
            "sourceDomain": source_domain,
            "sourceSlot": source_slot,
            "item": copy.deepcopy(source_item),
            "sourceItem": copy.deepcopy(source_item),
            "mouseMode": mouse_mode,
            "cursorOwned": bool(source.get("cursorOwned")),
            "baseUnheld": max(
                0,
                _item_count(source_item) - selected_count,
            ),
            "animateFly": False,
            "continueMouseHold": mouse_mode,
        }
        self.pending_ticks = 0
        if not mouse_mode:
            # Touch selection is released by the drop-zone Up edge. The item
            # removal itself still waits for the authoritative snapshot.
            self.selection = None
            self.split_state = None
            self.press_state = None
            self._selection_changed()
        self.replica_control.SetTouchEnable(False)

    @staticmethod
    def _same_stack(left, right):
        if _item_name(left) != _item_name(right):
            return False
        if not _item_name(left) or _item_aux(left) != _item_aux(right):
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
            if _normalized_item_value(left.get(key)) != _normalized_item_value(
                right.get(key)
            ):
                return False
        return True

    def _quick_move_target(self, source_slot, item):
        if (
            self.client_system is not None
            and _item_lock_mode(item) != "lock_in_inventory"
        ):
            candidates = [
                index
                for index, slot_id in enumerate(self.curio_slot_ids)
                if self.client_system.CanEquipCurio(slot_id, item)
            ]
            if candidates:
                target = next(
                    (
                        index for index in candidates
                        if self.curio_items[index]
                        and not self._is_locked(self.curio_items[index])
                        and self._same_stack(item, self.curio_items[index])
                        and _item_count(self.curio_items[index])
                        < self._curio_slot_capacity(index, item)
                    ),
                    None,
                )
                if target is None:
                    target = next(
                        (
                            index for index in candidates
                            if not self.curio_items[index]
                        ),
                        None,
                    )
            else:
                target = None
            # Quick move merges a compatible partial Curio stack before an
            # empty slot, and never swaps an occupied equipment slot.
            if target is not None:
                return ("curio", target)

        target_slots = range(9, 36) if int(source_slot) < 9 else range(0, 9)
        for target_slot in target_slots:
            target = self.inventory_items[target_slot]
            if (
                target
                and not self._is_locked(target)
                and self._same_stack(item, target)
                and _item_count(target) < self._client_max_stack_size(target)
            ):
                return ("inventory", target_slot)
        for target_slot in target_slots:
            if not self.inventory_items[target_slot]:
                return ("inventory", target_slot)
        return None

    def _curio_slot_capacity(self, index, item):
        slots = self._client_state().get("slots") or ()
        slot_limit = 1
        if 0 <= int(index) < len(slots):
            value = slots[int(index)].get("maxStack", 1)
            if _is_int(value) and int(value) > 0:
                slot_limit = int(value)
        return max(1, min(slot_limit, self._client_max_stack_size(item)))

    def _send_quick_move(self, slot, item, animate_fly=False):
        target = self._quick_move_target(slot, item)
        if target is None:
            self.selection = None
            self._selection_changed()
            return
        target_domain, target_slot = target
        source = {
            "domain": "inventory",
            "slot": int(slot),
            "count": _item_count(item),
            "item": copy.deepcopy(item),
            "mouseMode": self._is_mouse_mode(),
        }
        self._send_transfer(
            source,
            target_domain,
            target_slot,
            _item_count(item),
            self._item_at(target_domain, target_slot),
            animate_fly=animate_fly,
            continue_mouse_hold=False,
        )

    def _send_quick_move_from(
        self, domain, slot, item, animate_fly=False
    ):
        if domain == "inventory":
            self._send_quick_move(
                slot, item, animate_fly=animate_fly
            )
            return
        target = self._inventory_quick_move_target(item)
        if target is None:
            return
        source = {
            "domain": "curio",
            "slot": int(slot),
            "count": _item_count(item),
            "item": copy.deepcopy(item),
            "mouseMode": True,
        }
        self._send_transfer(
            source,
            "inventory",
            target,
            _item_count(item),
            self._item_at("inventory", target),
            animate_fly=animate_fly,
            continue_mouse_hold=False,
        )

    def _inventory_quick_move_target(self, item):
        # Native-style Shift removal from a Curio slot prefers the hotbar,
        # then falls back to the main inventory.
        ordered = tuple(range(0, 9)) + tuple(range(9, 36))
        for target_slot in ordered:
            target = self.inventory_items[target_slot]
            if (
                target
                and not self._is_locked(target)
                and self._same_stack(item, target)
                and _item_count(target) < self._client_max_stack_size(target)
            ):
                return target_slot
        for target_slot in ordered:
            if not self.inventory_items[target_slot]:
                return target_slot
        return None

    def _send_cursor_quick_move(self, source):
        item = source.get("item") or {}
        origin = source.get("cursorOrigin") or {}
        source_slot = origin.get("inventorySlot", 0)
        target = self._quick_move_target(source_slot, item)
        if target is None:
            return
        target_domain, target_slot = target
        self._send_transfer(
            source,
            target_domain,
            target_slot,
            _item_count(item),
            self._item_at(target_domain, target_slot),
            animate_fly=False,
            continue_mouse_hold=False,
        )

    def _send_cursor_double_click(self, source):
        item = source.get("item") or {}
        if not self._can_coalesce(-1, item):
            self._send_cursor_quick_move(source)
            return
        sent = self.client_system.CoalesceCurioInventoryCursor(item)
        if sent:
            self.pending = {
                "action": "cursor_coalesce",
                "requestId": sent,
                "mouseMode": True,
                "cursorOwned": True,
                "animateFly": False,
            }
            self.pending_ticks = 0
            self.replica_control.SetTouchEnable(False)

    def _can_coalesce(self, slot, item):
        if _item_count(item) >= self._client_max_stack_size(item):
            return False
        for index, candidate in enumerate(self.inventory_items):
            if (
                index != int(slot)
                and candidate
                and not self._is_locked(candidate)
                and self._same_stack(item, candidate)
            ):
                return True
        return False

    def _send_double_click(self, slot, item):
        # Native ordering is collect first; quick move is only the fallback
        # when no compatible stack can be collected into this source stack.
        if self._can_coalesce(slot, item):
            sent = self.client_system.CoalesceCurioInventory(slot, item)
            if sent:
                mouse_mode = self._is_mouse_mode()
                self.pending = {
                    "action": "coalesce",
                    "sourceDomain": "inventory",
                    "sourceSlot": int(slot),
                    "sourceItem": copy.deepcopy(item or {}),
                    "baseUnheld": 0,
                    "mouseMode": mouse_mode,
                    "continueDistribution": mouse_mode,
                    "animateFly": False,
                    "requestId": sent,
                }
                self.pending_ticks = 0
                self.replica_control.SetTouchEnable(False)
            return
        self._send_quick_move(slot, item)

    def _shift_down(self):
        return bool(self.client_system is not None and self.client_system.IsShiftDown())

    def _selection_changed(self):
        self._rebuild_view_models()
        self.render_dirty = True
        self._refresh_transient_controls()

    def _is_mouse_mode(self):
        # On PC the engine can keep reporting a mouse position while it is
        # deliberately translating mouse input into touch input.  Treat that
        # mode as touch first, otherwise a touch selection is rendered as an
        # invisible/stale cursor-held stack instead of the in-cell marker.
        touch_with_mouse = getattr(clientApi, "IsTouchWithMouse", None)
        if callable(touch_with_mouse) and touch_with_mouse():
            return False
        player_id = clientApi.GetLocalPlayerId()
        motion = (
            clientApi.GetEngineCompFactory().CreateActorMotion(player_id)
            if player_id else None
        )
        getter = getattr(motion, "GetMousePosition", None)
        return callable(getter) and getter() is not None

    @staticmethod
    def _mouse_position():
        player_id = clientApi.GetLocalPlayerId()
        motion = (
            clientApi.GetEngineCompFactory().CreateActorMotion(player_id)
            if player_id else None
        )
        getter = getattr(motion, "GetMousePosition", None)
        position = getter() if callable(getter) else None
        if (
            type(position).__name__ not in ("tuple", "list")
            or len(position) < 2
        ):
            return None
        return (float(position[0]), float(position[1]))

    def _refresh_transient_controls(self):
        held = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/held_item"
        )
        visible = bool(
            self.selection
            and self.selection.get("mouseMode")
            and int(self.selection.get("count", 0)) > 0
            and _item_name(self.selection.get("item") or {})
        )
        if not visible:
            if held is not None:
                held.SetVisible(False)
            self.held_item_active = False
            self.held_item_reveal_tick = None
        held_lock_mode = (
            _item_lock_mode(self.selection.get("item") or {})
            if visible else None
        )
        self.held_lock_in_inventory = bool(
            held_lock_mode == "lock_in_inventory"
        )
        self.held_lock_in_slot = bool(held_lock_mode == "lock_in_slot")
        held_item = (
            self.selection.get("item") or {}
            if visible else {}
        )
        (
            self.held_durability_visible,
            self.held_durability_total,
            self.held_durability_current,
        ) = self._client_durability_state(held_item)
        self.held_count_text = (
            str(self.selection.get("count"))
            if self.selection and int(self.selection.get("count", 1)) > 1
            else ""
        )
        if visible:
            item = self.selection.get("item") or {}
            renderer_control = self.screen_node.GetBaseUIControl(
                self.overlay_path + "/held_item/content/item"
            )
            starting_hold = not bool(getattr(self, "held_item_active", False))
            if starting_hold and held is not None:
                held.SetVisible(False)
                self.held_item_active = True
                self.held_item_reveal_tick = (
                    int(getattr(self, "tick_count", 0)) + 1
                )
            self._update_held_item_position()
            item_ready = self._set_ui_item(renderer_control, item)
            if not item_ready:
                if held is not None:
                    held.SetVisible(False)
                self.held_item_active = False
                self.held_item_reveal_tick = (
                    int(getattr(self, "tick_count", 0)) + 1
                )
            elif (
                not starting_hold
                and held is not None
                and self.held_item_reveal_tick is None
            ):
                held.SetVisible(True)
        touch_visible = bool(
            self.selection
            and not self.selection.get("mouseMode")
            and int(self.selection.get("count", 0)) > 0
            and _item_name(self.selection.get("item") or {})
        )
        if touch_visible:
            self.touch_hover_text = self._formatted_hover_text(
                self.selection.get("item") or {}
            )
            self._show_touch_item_details()
        else:
            # anim_item_details_alpha owns the normal lifetime of this
            # control.  Removing it as soon as touch selection ends cuts the
            # fade short and clearing the bound string makes the text vanish
            # even if the image survives.  Keep both alive for the animation,
            # but release the token so a selection made during that fade
            # replaces the old instance and restarts its timer/content.
            self._release_touch_item_details()
        self._sync_completed_touch_split_overlay()

    def _update_held_item_position(self):
        if not self.selection or not self.selection.get("mouseMode"):
            return False
        held = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/held_item"
        )
        if held is None:
            return False
        position = self._mouse_position()
        if position is None:
            return False
        size = (
            POCKET_HELD_ITEM_SIZE
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            else CLASSIC_HELD_ITEM_SIZE
        )
        target_position = (
            float(position[0]) - float(size[0]) * 0.5,
            float(position[1]) - float(size[1]) * 0.5,
        )
        self._set_global_position(held, target_position)
        # Position writes can be queued by the UI engine. Do not treat a
        # successful setter call as proof that the renderer has moved; reveal
        # only after the live global position reaches the cursor target.
        getter = getattr(held, "GetGlobalPosition", None)
        actual_position = getter() if callable(getter) else target_position
        if (
            type(actual_position).__name__ not in ("tuple", "list")
            or len(actual_position) < 2
        ):
            return False
        return bool(
            abs(float(actual_position[0]) - target_position[0]) <= 0.75
            and abs(float(actual_position[1]) - target_position[1]) <= 0.75
        )

    def _tick_held_item_reveal(self, positioned):
        """Reveal a new mouse-held renderer only after a stable position pass."""
        reveal_tick = getattr(self, "held_item_reveal_tick", None)
        if (
            not positioned
            or reveal_tick is None
            or int(getattr(self, "tick_count", 0)) < int(reveal_tick)
            or not self.selection
            or not self.selection.get("mouseMode")
            or int(self.selection.get("count", 0)) <= 0
        ):
            return
        held = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/held_item"
        )
        if held is None:
            return
        renderer = self.screen_node.GetBaseUIControl(
            self.overlay_path + "/held_item/content/item"
        )
        item = self.selection.get("item") or {}
        # Retry a not-yet-ready renderer without revealing its previous item
        # or layers. Use the current cursor payload, never its old source slot.
        if not _item_name(item) or not self._set_ui_item(renderer, item):
            held.SetVisible(False)
            return
        held.SetVisible(True)
        self.held_item_active = True
        self.held_item_reveal_tick = None

    def _show_touch_item_details(self):
        item = self.selection.get("item") or {}
        token = (
            self.selection.get("domain"),
            self.selection.get("slot"),
            self.selection.get("count"),
            _item_name(item),
            _item_aux(item),
        )
        if token == self.touch_details_token:
            return
        self._remove_touch_item_details()
        definition = (
            "chatelaine_inventory.touch_selected_item_details_pocket"
            if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
            else "chatelaine_inventory.touch_selected_item_details"
        )
        control = self.screen_node.CreateChildControl(
            definition,
            "selected_item_details",
            self.overlay_control,
            True,
        )
        self.touch_details_token = token if control is not None else None

    def _release_touch_item_details(self):
        """Let the current touch tooltip finish its JSON UI fade."""
        self.touch_details_token = None

    def _remove_touch_item_details(self):
        path = self.overlay_path + "/selected_item_details"
        if self.screen_node.GetBaseUIControl(path) is not None:
            self.screen_node.RemoveComponent(path, self.overlay_path)
        self.touch_details_token = None

    def _render_all_items(self):
        complete = True
        for grid_path, domain, first_slot, items in self._grid_specs():
            children = sorted(
                self.screen_node.GetChildrenName(grid_path) or (),
                key=self._grid_child_sort_key,
            )
            if len(children) < len(items):
                complete = False
            rendered_count = 0
            for cell_index, child_name in enumerate(children):
                slot_path = grid_path + "/" + child_name
                slot_control = self.screen_node.GetBaseUIControl(slot_path)
                logical_index = self._grid_logical_index(
                    domain, cell_index, len(items)
                )
                if logical_index is None:
                    # A JSON grid instantiates every cell described by
                    # grid_dimensions. Pages are data driven, so cells beyond
                    # the active page's slot count must be explicitly removed
                    # from both rendering and hit testing.
                    self._hide_unused_slot(slot_path, slot_control)
                    continue
                rendered_count += 1
                if slot_control is None:
                    complete = False
                elif slot_path not in getattr(
                    self, "prepared_slot_paths", set()
                ):
                    # Parent input state is also stable after first prepare.
                    # Rewriting it under a stationary pointer can invalidate
                    # the engine's cached descendant hit/hover route.
                    slot_control.SetVisible(True)
                    slot_control.SetTouchEnable(True)
                slot = first_slot + logical_index
                item = self._visual_item(
                    items[logical_index], domain, slot
                )
                dto = self._slot_view_model(domain, slot)
                if dto is None or not self._push_slot_visuals(
                    slot_path,
                    item,
                    dto,
                ):
                    complete = False
            if rendered_count < len(items):
                complete = False
        self.render_dirty = not complete

    def _hide_unused_slot(self, slot_path, slot_control=None):
        """Clear every retained layer of a collection cell no longer used."""
        getattr(self, "prepared_slot_paths", set()).discard(slot_path)
        durability = self.screen_node.GetBaseUIControl(
            slot_path + "/durability"
        )
        if durability is not None:
            durability.SetVisible(False)
        if slot_control is None:
            slot_control = self.screen_node.GetBaseUIControl(slot_path)
        if slot_control is not None:
            slot_control.SetVisible(False)
            slot_control.SetTouchEnable(False)
        for child_path in (
            "/background",
            "/selected_background",
            "/item",
            "/empty_icon",
            "/stack_count",
            "/durability",
            "/item_lock_cell_image",
            "/lock_in_inventory_overlay",
            "/lock_in_slot_overlay",
            "/selected_marker",
            "/slot_button",
        ):
            control = self.screen_node.GetBaseUIControl(
                slot_path + child_path
            )
            if control is not None:
                control.SetVisible(False)
                control.SetTouchEnable(False)

    def _slot_view_model(self, domain, slot):
        if domain == "curio":
            values = self.curio_slot_models
            index = int(slot)
        elif int(slot) < 9:
            values = self.inventory_hotbar
            index = int(slot)
        else:
            values = self.inventory_bag
            index = int(slot) - 9
        if index < 0 or index >= len(values):
            return None
        return values[index]

    def _push_slot_visuals(self, slot_path, item, dto):
        """Push one complete DTO without waiting for collection polling."""
        complete = True
        ready_controls = []
        prepared_paths = getattr(self, "prepared_slot_paths", None)
        if prepared_paths is None:
            prepared_paths = set()
            self.prepared_slot_paths = prepared_paths
        first_prepare = slot_path not in prepared_paths
        for child_name in ("background", "slot_button"):
            control = self.screen_node.GetBaseUIControl(
                slot_path + "/" + child_name
            )
            if control is None:
                complete = False
            else:
                # A freshly constructed grid cell is fail-closed. Once ready,
                # never hide/re-show its button during ordinary item updates:
                # JSON UI hover is edge-driven and would remain in default
                # state under a stationary cursor until another HoverIn.
                if first_prepare:
                    control.SetVisible(False)
                ready_controls.append(control)
        item_control = self.screen_node.GetBaseUIControl(slot_path + "/item")
        if item_control is None:
            complete = False
        else:
            # Hide the old renderer before changing its payload so an active
            # grid cannot expose a mixed old/new slot during this call.
            item_control.SetVisible(False)
            # Even a virtually held source keeps a live authoritative item.
            # Preload that payload while its renderer is hidden; otherwise a
            # swap leaves the pre-swap payload cached and returning the held
            # item exposes it for one frame before SetUiItem commits.
            item_ready = self._set_ui_item(
                item_control,
                item,
            )
            if not item_ready:
                complete = False
            item_control.SetVisible(bool(
                item_ready and _item_name(item) and dto.get("itemVisible")
            ))

        count_control = self.screen_node.GetBaseUIControl(
            slot_path + "/stack_count"
        )
        count_label = (
            count_control.asLabel() if count_control is not None else None
        )
        count_setter = getattr(count_label, "SetText", None)
        if callable(count_setter):
            count_control.SetVisible(False)
            count_setter(dto.get("stackText", ""))
            count_control.SetVisible(bool(dto.get("stackVisible")))
        else:
            complete = False

        for child_name, key in (
            ("selected_background", "selected"),
            ("selected_marker", "selected"),
            ("item_lock_cell_image", "locked"),
            ("lock_in_inventory_overlay", "lockInInventory"),
            ("lock_in_slot_overlay", "lockInSlot"),
        ):
            control = self.screen_node.GetBaseUIControl(
                slot_path + "/" + child_name
            )
            if control is None:
                complete = False
            else:
                control.SetVisible(bool(dto.get(key)))

        empty_control = self.screen_node.GetBaseUIControl(
            slot_path + "/empty_icon"
        )
        if empty_control is None:
            complete = False
        else:
            empty_control.SetVisible(False)
            empty_texture = dto.get("emptyTexture", "")
            if empty_texture:
                empty_image = empty_control.asImage()
                sprite_setter = getattr(empty_image, "SetSprite", None)
                if callable(sprite_setter):
                    sprite_setter(empty_texture)
                else:
                    complete = False
            empty_control.SetVisible(bool(dto.get("emptyVisible")))

        durability = self.screen_node.GetBaseUIControl(
            slot_path + "/durability"
        )
        if durability is None:
            complete = False
        else:
            durability.SetVisible(False)
            durability_visible = bool(dto.get("durabilityVisible"))
            # NetEase SetPropertyBag converts Python bool to an integer.
            # Keep the renderer's boolean gate owned by JSON (static Pocket)
            # or BF_BindBool (Grid). SetVisible owns this control's visibility;
            # only the numeric progress values may be written here.
            durability_properties = {
                "#progress_bar_total_amount": int(
                    dto.get("durabilityTotal", 1)
                ),
                "#progress_bar_current_amount": int(
                    dto.get("durabilityCurrent", 1)
                ),
            }
            if durability.SetPropertyBag(durability_properties) is False:
                complete = False
            durability.SetVisible(durability_visible)

        # This branch is created only while hovered. It does not gate renderer
        # completion, but when present it receives the same current DTO.
        hover_text = self.screen_node.GetBaseUIControl(
            slot_path + "/slot_button/hover/hover_text"
        )
        if hover_text is not None:
            hover_text.SetPropertyBag({
                "#hover_text": dto.get("hoverText", ""),
            })
        if complete:
            if first_prepare:
                for control in ready_controls:
                    control.SetVisible(True)
                    control.SetTouchEnable(True)
            prepared_paths.add(slot_path)
        return complete

    @staticmethod
    def _set_ui_item(control, item):
        renderer = control.asItemRenderer() if control is not None else None
        name = _item_name(item)
        if not name:
            if control is not None:
                # Additional layers are direct children of this renderer;
                # hiding it also retires every layer of an emptied cell.
                control.SetVisible(False)
            return True
        if renderer is None:
            return False
        # SetUiItem supplies all five local image bindings from userData.
        # Always send a complete payload, including an empty dict when a
        # plain item replaces a layered one; do not retain the old userData.
        return bool(renderer.SetUiItem(
            name,
            _item_aux(item),
            bool(item.get("isEnchanted") or item.get("enchantData")),
            item.get("userData") or {},
        ))

    def _tick_pending(self):
        if self.pending is None:
            return
        self.pending_ticks += 1
        if self.pending_ticks <= 100:
            return
        if self.pending.get("action") == "distribute_finish":
            # A generic refresh cannot clear a server-side active
            # distribution if the finish packet/response was lost. Retry the
            # idempotent completion with a new request id; a server that
            # already finished returns authoritative distribution_changed,
            # which still resolves this pending UI operation safely.
            request_id = self.client_system.FinishCurioInventoryDistribution(
                self.pending.get("distributionId")
            )
            if request_id:
                self.pending["requestId"] = request_id
                self.pending_ticks = 0
                return
        preserve_replica_touch = bool(
            self.pending.get("preserveReplicaTouch")
        )
        self._cancel_transient_state(
            clear_selection=True,
            cancel_fly=True,
            clear_pending=True,
        )
        if not preserve_replica_touch:
            self.replica_control.SetTouchEnable(True)
        self.client_system.RefreshCurioInventoryState()

    def _tick_page_transition(self):
        target = self.page_transition_target
        if target is None or self.page_transition_request_id is None:
            return
        self.page_transition_ticks += 1
        if self.page_transition_ticks <= NETWORK_RETRY_TICKS:
            return
        # Keep the current tree guarded and retry one authoritative page write.
        # A new request id makes a delayed response from the previous attempt
        # harmless; this is a timeout retry, not a stable-frame rewrite.
        request_id = self.client_system.SetCurioInventoryPage(target)
        self.page_transition_ticks = 0
        if request_id:
            self.page_transition_request_id = request_id
            if target == "armor":
                self.native_inventory_exit_request_id = request_id
                self.native_inventory_exit_pending = True
            return
        self.page_transition_request_id = None
        self.page_transition_target = None
        if target == "armor":
            self.native_inventory_exit_request_id = None
            self.native_inventory_exit_pending = False
            self._apply_page_visibility(self._chatelaine_visible())

    def _slot_path(self, domain, slot):
        if domain == "curio":
            grid_path = self._curio_grid_path()
            local_index = self._grid_cell_index(domain, int(slot))
        elif int(slot) < 9:
            grid_path = self.replica_path + "/hotbar_grid"
            local_index = int(slot)
        else:
            grid_path = (
                self._pocket_bag_slots_path()
                if self.screen_name == CURIO_INVENTORY_POCKET_SCREEN
                else self.bag_path + "/bag_grid"
            )
            local_index = int(slot) - 9
        children = sorted(
            self.screen_node.GetChildrenName(grid_path) or (),
            key=self._grid_child_sort_key,
        )
        if (
            local_index is None
            or local_index < 0
            or local_index >= len(children)
        ):
            return None
        return grid_path + "/" + children[local_index]

    def _slot_control(self, domain, slot):
        slot_path = self._slot_path(domain, slot)
        if slot_path is None:
            return None
        return self.screen_node.GetBaseUIControl(slot_path)

    def _start_fly(self, operation):
        source = self._slot_control(
            operation.get("sourceDomain"), operation.get("sourceSlot")
        )
        target = self._slot_control(
            operation.get("targetDomain"), operation.get("targetSlot")
        )
        fly = self.screen_node.GetBaseUIControl(self.overlay_path + "/fly_item")
        if fly is not None:
            fly.SetVisible(False)
        self.fly_state = None
        if source is None or target is None or fly is None:
            return False
        start = self._fly_origin_from_slot_center(source, fly)
        end = self._fly_origin_from_slot_center(target, fly)
        if start is None or end is None:
            return False
        item = operation.get("item") or {}
        if not _item_name(item) or not self._set_ui_item(fly, item):
            return False
        self._set_global_position(fly, start)
        fly.SetVisible(True)
        self.fly_state = {
            "control": fly,
            "start": start,
            "end": end,
            "tick": 0,
            "duration": FLY_ANIMATION_TICKS,
        }
        return True

    @staticmethod
    def _fly_origin_from_slot_center(slot_control, fly_control):
        """Convert the slot's reported centre to fly_item's top-left."""
        center = slot_control.GetGlobalPosition()
        fly_size = fly_control.GetSize()
        if center is None or fly_size is None or len(fly_size) < 2:
            return center
        return (
            float(center[0]) - float(fly_size[0]) * 0.5,
            float(center[1]) - float(fly_size[1]) * 0.5,
        )

    def _tick_fly(self):
        state = self.fly_state
        if state is None:
            return
        state["tick"] += 1
        ratio = min(1.0, float(state["tick"]) / float(state["duration"]))
        start = state["start"]
        end = state["end"]
        self._set_global_position(state["control"], (
            start[0] + (end[0] - start[0]) * ratio,
            start[1] + (end[1] - start[1]) * ratio,
        ))
        if ratio >= 1.0:
            self.fly_target_override = None
            self._rebuild_view_models()
            self.render_dirty = True
            self._render_all_items()
            state["control"].SetVisible(False)
            self.fly_state = None

    @staticmethod
    def _set_global_position(control, position):
        """Set one global position across Classic and Pocket parent anchors."""
        getter_global = getattr(control, "GetGlobalPosition", None)
        getter_local = getattr(control, "GetPosition", None)
        setter_local = getattr(control, "SetPosition", None)
        current_global = getter_global() if callable(getter_global) else None
        current_local = getter_local() if callable(getter_local) else None
        if (
            callable(setter_local)
            and current_global is not None
            and current_local is not None
        ):
            # Pocket's full-screen overlay is anchored at screen centre while
            # Classic's is anchored at top-left.  Translating by the observed
            # local/global delta handles both in one deterministic write.
            setter_local((
                float(current_local[0])
                + float(position[0]) - float(current_global[0]),
                float(current_local[1])
                + float(position[1]) - float(current_global[1]),
            ))
            return
        control.SetFullPosition(
            "x",
            {"followType": "none", "absoluteValue": float(position[0])},
        )
        control.SetFullPosition(
            "y",
            {"followType": "none", "absoluteValue": float(position[1])},
        )

    @staticmethod
    def _index(args):
        if type(args).__name__ != "dict":
            return 0
        value = args.get(
            "index",
            args.get("collection_index", args.get("#collection_index", 0)),
        )
        return int(value) if _is_int(value) else 0

    def _event_slot(self, args, domain, first_slot, count):
        if type(args).__name__ != "dict":
            return None
        button_path = args.get("ButtonPath")
        if type(button_path).__name__ in ("str", "unicode"):
            for path, target in self.bound_button_slots.items():
                if (
                    button_path == path
                    or path.endswith(button_path)
                    or button_path.endswith(path)
                ):
                    if target[0] == domain:
                        return int(target[1])
        value = args.get(
            "index",
            args.get("collection_index", args.get("#collection_index")),
        )
        if not _is_int(value):
            return None
        cell_index = int(value)
        local_index = self._grid_logical_index(domain, cell_index, count)
        if local_index is None:
            return None
        return int(first_slot) + local_index

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_toggle")
    def OnToggle(self, _args):
        if self._destroyed:
            return
        if (
            self.client_system is None
            or self._client_state().get("pageCount", 0) <= 0
            or self.pending is not None
            or self.drag_state is not None
            or self.page_transition_target is not None
            or self._native_selection_active()
        ):
            return
        if self.selection is not None and self.selection.get("cursorOwned"):
            request_id = self.client_system.ReturnCurioInventoryCursor()
            if request_id:
                self.pending = {
                    "action": "cursor_return",
                    "requestId": request_id,
                    "mouseMode": True,
                    "cursorOwned": True,
                    "animateFly": False,
                    "toggleAfterReturn": True,
                }
                self.pending_ticks = 0
                self.replica_control.SetTouchEnable(False)
            return
        self._cancel_transient_state(clear_selection=True, cancel_fly=True)

        self._request_next_page()

    def _request_next_page(self):
        state = self._client_state()
        next_page_id = state.get("nextPageId")
        page = next_page_id or "armor"
        if page == "armor":
            # SetCurioInventoryPage applies its local page value synchronously
            # before returning the request id. Install the guard first so that
            # refresh cannot expose a partially restored native control tree.
            self.native_inventory_exit_pending = True
        self.page_transition_target = page
        self.page_transition_ticks = 0
        request_id = self.client_system.NextChatelainePage()
        if request_id:
            self.page_transition_request_id = request_id
            if page == "armor":
                self.native_inventory_exit_request_id = request_id
            self.client_system.PlayInscriptionUiSound("random.click", 1.0)
        else:
            self.page_transition_target = None
            if page == "armor":
                self.native_inventory_exit_pending = False

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_drop_primary")
    def OnDropPrimary(self, _args):
        if self._destroyed:
            return
        self._activate_drop(False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_drop_secondary")
    def OnDropSecondary(self, _args):
        if self._destroyed:
            return
        self._activate_drop(True)

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_drop_active")
    def BindDropActive(self):
        # This binding guards the screen-level mapping itself. A false value
        # makes JSON UI skip the Chatelaine target so the later native
        # cursor_drop_all/one mapping remains the sole handler.
        return bool(self._chatelaine_visible() and self.selection is not None)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_inventory_bag_primary")
    def OnBagPrimary(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 9, 27)
            if slot is not None:
                self._on_press_up("inventory", slot, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_inventory_bag_primary")
    def OnBagPrimaryDown(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 9, 27)
            if slot is not None:
                self._on_press_down("inventory", slot, args, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_inventory_bag_secondary")
    def OnBagSecondary(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 9, 27)
            if slot is not None:
                self._on_press_up("inventory", slot, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_inventory_bag_secondary")
    def OnBagSecondaryDown(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 9, 27)
            if slot is not None:
                self._on_press_down("inventory", slot, args, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_inventory_bag_quick")
    def OnBagQuick(self, args):
        if self._destroyed:
            return
        self._quick_move_event("inventory", args, 9, 27, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_inventory_bag_quick")
    def OnBagQuickDown(self, args):
        if self._destroyed:
            return
        self._quick_move_event("inventory", args, 9, 27, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_inventory_hotbar_primary")
    def OnHotbarPrimary(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 0, 9)
            if slot is not None:
                self._on_press_up("inventory", slot, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_inventory_hotbar_primary")
    def OnHotbarPrimaryDown(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 0, 9)
            if slot is not None:
                self._on_press_down("inventory", slot, args, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_inventory_hotbar_secondary")
    def OnHotbarSecondary(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 0, 9)
            if slot is not None:
                self._on_press_up("inventory", slot, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_inventory_hotbar_secondary")
    def OnHotbarSecondaryDown(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "inventory", 0, 9)
            if slot is not None:
                self._on_press_down("inventory", slot, args, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_inventory_hotbar_quick")
    def OnHotbarQuick(self, args):
        if self._destroyed:
            return
        self._quick_move_event("inventory", args, 0, 9, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_inventory_hotbar_quick")
    def OnHotbarQuickDown(self, args):
        if self._destroyed:
            return
        self._quick_move_event("inventory", args, 0, 9, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_curio_primary")
    def OnCurioPrimary(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "curio", 0, len(self.curio_items))
            if slot is not None:
                self._on_press_up("curio", slot, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_curio_primary")
    def OnCurioPrimaryDown(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "curio", 0, len(self.curio_items))
            if slot is not None:
                self._on_press_down("curio", slot, args, False)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_curio_secondary")
    def OnCurioSecondary(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "curio", 0, len(self.curio_items))
            if slot is not None:
                self._on_press_up("curio", slot, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_curio_secondary")
    def OnCurioSecondaryDown(self, args):
        if self._destroyed:
            return
        if self._is_mouse_mode():
            slot = self._event_slot(args, "curio", 0, len(self.curio_items))
            if slot is not None:
                self._on_press_down("curio", slot, args, True)

    @ViewBinder.binding(ViewBinder.BF_ButtonClickUp, "#chatelaine_curio_quick")
    def OnCurioQuick(self, args):
        if self._destroyed:
            return
        self._quick_move_event(
            "curio", args, 0, len(self.curio_items), False
        )

    @ViewBinder.binding(ViewBinder.BF_ButtonClickDown, "#chatelaine_curio_quick")
    def OnCurioQuickDown(self, args):
        if self._destroyed:
            return
        self._quick_move_event(
            "curio", args, 0, len(self.curio_items), True
        )

    def _quick_move_event(
        self, domain, args, first_slot, count, pressed=False
    ):
        slot = self._event_slot(args, domain, first_slot, count)
        if slot is None:
            return
        key = (domain, int(slot))
        if not pressed and getattr(self, "quick_move_pressed", None) == key:
            self.quick_move_pressed = None
            self.shift_quick_suppress_until = self.tick_count + 2
            return
        if pressed:
            self.quick_move_pressed = key
        if (
            self.pending is not None
            or self.selection is not None
            or self.page_transition_target is not None
            or not self._chatelaine_visible()
            or self.tick_count <= getattr(
                self, "shift_quick_suppress_until", -1
            )
        ):
            return
        item = self._item_at(domain, slot)
        if not item or self._is_locked(item):
            return
        # menu_auto_place is a pressed mapping. Some PC profiles expose only
        # its down edge, while others also deliver the up edge and the ordinary
        # primary/secondary callback. Make every later edge a no-op and remove
        # any provisional long-press state created earlier in the same frame.
        self.shift_quick_suppress_until = self.tick_count + 2
        self.press_state = None
        self.split_state = None
        self.drag_state = None
        self._hide_split_overlay()
        self.last_click = None
        self.last_click_tick = -100
        self._send_quick_move_from(
            domain, slot, item, animate_fly=True
        )

    @ViewBinder.binding(ViewBinder.BF_BindString, "#chatelaine_held_count")
    def BindHeldCount(self):
        return getattr(self, "held_count_text", "")

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_held_lock_in_inventory")
    def BindHeldLockInInventory(self):
        return bool(getattr(self, "held_lock_in_inventory", False))

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_held_lock_in_slot")
    def BindHeldLockInSlot(self):
        return bool(getattr(self, "held_lock_in_slot", False))

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_held_durability_visible")
    def BindHeldDurabilityVisible(self):
        return bool(getattr(self, "held_durability_visible", False))

    @ViewBinder.binding(ViewBinder.BF_BindInt, "#chatelaine_held_durability_total")
    def BindHeldDurabilityTotal(self):
        return int(getattr(self, "held_durability_total", 1))

    @ViewBinder.binding(ViewBinder.BF_BindInt, "#chatelaine_held_durability_current")
    def BindHeldDurabilityCurrent(self):
        return int(getattr(self, "held_durability_current", 1))

    @ViewBinder.binding(ViewBinder.BF_BindString, "#chatelaine_split_text")
    def BindSplitText(self):
        return getattr(self, "split_text", "")

    @ViewBinder.binding(ViewBinder.BF_BindFloat, "#chatelaine_split_ratio")
    def BindSplitRatio(self):
        # JSON UI clip_ratio is the fraction removed, not the fraction filled.
        return 1.0 - float(getattr(self, "split_ratio", 0.0))

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_legacy_progress_visible")
    def BindLegacyProgressVisible(self):
        return True

    @ViewBinder.binding(ViewBinder.BF_BindInt, "#chatelaine_legacy_progress_total")
    def BindLegacyProgressTotal(self):
        return int(getattr(self, "legacy_progress_total", 1))

    @ViewBinder.binding(ViewBinder.BF_BindInt, "#chatelaine_legacy_progress_current")
    def BindLegacyProgressCurrent(self):
        return int(getattr(self, "legacy_progress_current", 0))

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_split_down_visible")
    def BindSplitDownVisible(self):
        return getattr(self, "split_direction", "down") == "down"

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_split_up_visible")
    def BindSplitUpVisible(self):
        return getattr(self, "split_direction", "down") == "up"

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_split_left_visible")
    def BindSplitLeftVisible(self):
        return getattr(self, "split_direction", "down") == "left"

    @ViewBinder.binding(ViewBinder.BF_BindBool, "#chatelaine_split_right_visible")
    def BindSplitRightVisible(self):
        return getattr(self, "split_direction", "down") == "right"

    @ViewBinder.binding(ViewBinder.BF_BindString, "#chatelaine_touch_hover_text")
    def BindTouchHoverText(self):
        return getattr(self, "touch_hover_text", "")

    # Collection bindings are deliberately O(1): all expensive item work is
    # precomputed by _rebuild_view_models after an authoritative state change.
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_item_visible")
    def BindBagVisible(self, index): return self._collection_value("inventory_bag", index, "itemVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_inventory_bag", "#chatelaine_stack_text")
    def BindBagCount(self, index): return self._collection_value("inventory_bag", index, "stackText", "")
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_stack_visible")
    def BindBagCountVisible(self, index): return self._collection_value("inventory_bag", index, "stackVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_selected")
    def BindBagSelected(self, index): return self._collection_value("inventory_bag", index, "selected", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_lock_in_inventory")
    def BindBagLockInInventory(self, index): return self._collection_value("inventory_bag", index, "lockInInventory", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_lock_in_slot")
    def BindBagLockInSlot(self, index): return self._collection_value("inventory_bag", index, "lockInSlot", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_item_locked")
    def BindBagItemLocked(self, index): return self._collection_value("inventory_bag", index, "locked", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_durability_visible")
    def BindBagDurabilityVisible(self, index): return self._collection_value("inventory_bag", index, "durabilityVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindInt, "chatelaine_inventory_bag", "#chatelaine_durability_total")
    def BindBagDurabilityTotal(self, index): return self._collection_value("inventory_bag", index, "durabilityTotal", 1)
    @ViewBinder.binding_collection(ViewBinder.BF_BindInt, "chatelaine_inventory_bag", "#chatelaine_durability_current")
    def BindBagDurabilityCurrent(self, index): return self._collection_value("inventory_bag", index, "durabilityCurrent", 1)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_inventory_bag", "#chatelaine_hover_text")
    def BindBagHover(self, index): return self._collection_value("inventory_bag", index, "hoverText", "")
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_bag", "#chatelaine_empty_visible")
    def BindBagEmptyVisible(self, index): return False
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_inventory_bag", "#chatelaine_empty_texture")
    def BindBagEmptyTexture(self, index): return ""
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_item_visible")
    def BindHotbarVisible(self, index): return self._collection_value("inventory_hotbar", index, "itemVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_inventory_hotbar", "#chatelaine_stack_text")
    def BindHotbarCount(self, index): return self._collection_value("inventory_hotbar", index, "stackText", "")
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_stack_visible")
    def BindHotbarCountVisible(self, index): return self._collection_value("inventory_hotbar", index, "stackVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_selected")
    def BindHotbarSelected(self, index): return self._collection_value("inventory_hotbar", index, "selected", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_lock_in_inventory")
    def BindHotbarLockInInventory(self, index): return self._collection_value("inventory_hotbar", index, "lockInInventory", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_lock_in_slot")
    def BindHotbarLockInSlot(self, index): return self._collection_value("inventory_hotbar", index, "lockInSlot", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_item_locked")
    def BindHotbarItemLocked(self, index): return self._collection_value("inventory_hotbar", index, "locked", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_durability_visible")
    def BindHotbarDurabilityVisible(self, index): return self._collection_value("inventory_hotbar", index, "durabilityVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindInt, "chatelaine_inventory_hotbar", "#chatelaine_durability_total")
    def BindHotbarDurabilityTotal(self, index): return self._collection_value("inventory_hotbar", index, "durabilityTotal", 1)
    @ViewBinder.binding_collection(ViewBinder.BF_BindInt, "chatelaine_inventory_hotbar", "#chatelaine_durability_current")
    def BindHotbarDurabilityCurrent(self, index): return self._collection_value("inventory_hotbar", index, "durabilityCurrent", 1)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_inventory_hotbar", "#chatelaine_hover_text")
    def BindHotbarHover(self, index): return self._collection_value("inventory_hotbar", index, "hoverText", "")
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_inventory_hotbar", "#chatelaine_empty_visible")
    def BindHotbarEmptyVisible(self, index): return False
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_inventory_hotbar", "#chatelaine_empty_texture")
    def BindHotbarEmptyTexture(self, index): return ""

    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_item_visible")
    def BindCurioVisible(self, index): return self._collection_value("curio_slots", index, "itemVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_curio_slots", "#chatelaine_stack_text")
    def BindCurioCount(self, index): return self._collection_value("curio_slots", index, "stackText", "")
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_stack_visible")
    def BindCurioCountVisible(self, index): return self._collection_value("curio_slots", index, "stackVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_selected")
    def BindCurioSelected(self, index): return self._collection_value("curio_slots", index, "selected", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_lock_in_inventory")
    def BindCurioLockInInventory(self, index): return self._collection_value("curio_slots", index, "lockInInventory", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_lock_in_slot")
    def BindCurioLockInSlot(self, index): return self._collection_value("curio_slots", index, "lockInSlot", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_item_locked")
    def BindCurioItemLocked(self, index): return self._collection_value("curio_slots", index, "locked", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_durability_visible")
    def BindCurioDurabilityVisible(self, index): return self._collection_value("curio_slots", index, "durabilityVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindInt, "chatelaine_curio_slots", "#chatelaine_durability_total")
    def BindCurioDurabilityTotal(self, index): return self._collection_value("curio_slots", index, "durabilityTotal", 1)
    @ViewBinder.binding_collection(ViewBinder.BF_BindInt, "chatelaine_curio_slots", "#chatelaine_durability_current")
    def BindCurioDurabilityCurrent(self, index): return self._collection_value("curio_slots", index, "durabilityCurrent", 1)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_curio_slots", "#chatelaine_hover_text")
    def BindCurioHover(self, index): return self._collection_value("curio_slots", index, "hoverText", "")
    @ViewBinder.binding_collection(ViewBinder.BF_BindBool, "chatelaine_curio_slots", "#chatelaine_empty_visible")
    def BindCurioEmptyVisible(self, index): return self._collection_value("curio_slots", index, "emptyVisible", False)
    @ViewBinder.binding_collection(ViewBinder.BF_BindString, "chatelaine_curio_slots", "#chatelaine_empty_texture")
    def BindCurioEmptyTexture(self, index): return self._collection_value("curio_slots", index, "emptyTexture", "")


