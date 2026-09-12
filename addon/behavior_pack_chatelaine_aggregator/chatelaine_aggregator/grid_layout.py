# -*- coding: utf-8 -*-
"""Pure Chatelaine grid index mapping shared by rendering and input handling."""


EXPANDED_GRID_SIDE = 4
EXPANDED_GRID_CAPACITY = EXPANDED_GRID_SIDE * EXPANDED_GRID_SIDE


def logical_slot_to_cell(logical_index, expanded):
    """Return the row-major UI cell for one page-local logical slot."""
    logical_index = int(logical_index)
    if logical_index < 0:
        return None
    if not expanded:
        return logical_index
    if logical_index >= EXPANDED_GRID_CAPACITY:
        return None
    return (
        (logical_index % EXPANDED_GRID_SIDE) * EXPANDED_GRID_SIDE
        + logical_index // EXPANDED_GRID_SIDE
    )


def cell_to_logical_slot(cell_index, slot_count, expanded):
    """Return the logical slot displayed by a row-major UI cell, if any."""
    cell_index = int(cell_index)
    slot_count = int(slot_count)
    if cell_index < 0 or slot_count < 0:
        return None
    if expanded:
        if cell_index >= EXPANDED_GRID_CAPACITY:
            return None
        logical_index = (
            (cell_index % EXPANDED_GRID_SIDE) * EXPANDED_GRID_SIDE
            + cell_index // EXPANDED_GRID_SIDE
        )
    else:
        logical_index = cell_index
    return logical_index if logical_index < slot_count else None
