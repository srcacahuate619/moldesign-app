"""Backward-compatibility shim: the catalog moved to ``tools.catalog``.

Kept for one version (PLAN tarea 3.1); removed in 0.3.
"""

import warnings

from .tools import (
    Capability,
    FieldSpec,
    PlanValidationError,
    capability,
    catalog,
)

warnings.warn(
    "molchat_agent.capabilities está obsoleto; usa molchat_agent.tools",
    DeprecationWarning, stacklevel=2)

CAPABILITIES = catalog()

__all__ = ["CAPABILITIES", "Capability", "FieldSpec", "PlanValidationError",
           "capability"]
