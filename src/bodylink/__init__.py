"""bodylink — the execution-adapter layer for Chronotope (D5, the 4th member).

The brain (`mindloop`) ships the `ExecutorAdapter` *protocol*; bodylink ships the
reference *fill* plus the adaptation framework: `MockBody` (a no-hardware body for
L3 dev/tests), a `BaseExecutorAdapter` SDK base, a model-`manifest` catalog
(`load_manifest`), and a `conformance` kit. Each real robot is a separate,
out-of-tree device package that subclasses `BaseExecutorAdapter` and ships its own
manifest — differentiated only by its Body Profile + verb set ("swap the body,
keep the mind", D3). Genesis/Isaac sim lives behind the `[sim]` extra; no heavy
deps in the core.
"""

from __future__ import annotations

from .adapter import BaseExecutorAdapter, UnsupportedVerbError
from .conformance import check_executor_adapter
from .manifest import list_profiles, load_manifest, manifest_from_dict
from .mock import MockBody, g1d_manifest
from .sim import (
    GenesisSimBackend,
    MockSimBackend,
    SceneObject,
    SimBackend,
    make_sim_backend,
)

__version__ = "0.1.0a0"


def h1_manifest():
    """The bipedal/legged reference manifest: Unitree H1 (19 DOF, legged base)."""
    return load_manifest("h1")


__all__ = [
    "BaseExecutorAdapter",
    "GenesisSimBackend",
    "MockBody",
    "MockSimBackend",
    "SceneObject",
    "SimBackend",
    "UnsupportedVerbError",
    "check_executor_adapter",
    "g1d_manifest",
    "h1_manifest",
    "list_profiles",
    "load_manifest",
    "make_sim_backend",
    "manifest_from_dict",
]
