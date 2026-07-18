"""Environment-variable compatibility helpers for the Jouvence rename."""

from __future__ import annotations

import os
import warnings


def get_jouvence_env(name: str, default: str | None = None) -> str | None:
    """Read a ``JOUVENCE_*`` variable with its deprecated ``TXGNN_*`` alias.

    The Jouvence name always wins when both are present. This helper is intended
    for project-level configuration; upstream TxGNN library identifiers remain
    unchanged.
    """

    if not name.startswith("JOUVENCE_"):
        raise ValueError("Jouvence environment names must start with 'JOUVENCE_'")

    if name in os.environ:
        return os.environ[name]

    legacy_name = f"TXGNN_{name.removeprefix('JOUVENCE_')}"
    if legacy_name in os.environ:
        warnings.warn(
            f"{legacy_name} is deprecated; use {name} instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return os.environ[legacy_name]
    return default
