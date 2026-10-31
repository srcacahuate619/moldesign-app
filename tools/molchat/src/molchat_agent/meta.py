"""Backward-compatibility shim: the planner moved to ``providers.meta``.

Kept for one version (PLAN tarea 1.2); removed in 0.2.
"""

import warnings

from .providers.meta import MetaPlanner, MetaProvider

warnings.warn(
    "molchat_agent.meta está obsoleto; usa molchat_agent.providers.meta",
    DeprecationWarning, stacklevel=2)

__all__ = ["MetaPlanner", "MetaProvider"]
