# -*- coding: utf-8 -*-
"""Pure helpers for fail-closed native UI lifecycle hand-offs."""


def advance_stable_signature(
    previous_signature,
    stable_samples,
    current_signature,
    required_samples,
):
    """Advance consecutive observations of one complete control tree."""
    if not current_signature:
        return None, 0, False
    current_signature = tuple(current_signature)
    if current_signature != previous_signature:
        return current_signature, 1, required_samples <= 1
    stable_samples = int(stable_samples) + 1
    return (
        current_signature,
        stable_samples,
        stable_samples >= int(required_samples),
    )
