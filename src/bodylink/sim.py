"""bodylink.sim — physics-simulator backends for the executor seam (D5).

A simulator is just a `backend` behind `SimDeviceAdapter` (the `examples`
reference adapter) or any adapter: a callable
``(verb, params, node_ids) -> (success, message)`` that *realizes* a gated verb in
a physics world and reports the outcome. This module ships two:

  * `MockSimBackend` — deterministic, no physics, records calls. The CI/test
    default; needs nothing.
  * `GenesisSimBackend` — a real `Genesis` physics scene (behind the ``sim``
    extra). Builds ground + a robot body + a box per scene object, and advances
    physics per dispatched verb. Mirrors Brain2Robot's `GenesisL1`
    (`gs.init(backend=gs.cpu)` → `gs.Scene` → `add_entity(morphs…)` →
    `scene.build()` → `scene.step()`).

**Scope (first integration).** Verb realization is COARSE — a walking-skeleton
sim: locomotion verbs (`navigate`, `climb_stair`) nudge the robot toward the
target object and step physics; manipulation/appliance verbs settle the sim N
steps. The point is a **real physics loop wired to the verb seam**, end to end,
with no brain change (D3) — per-robot kinematics (IK / G1 keyframes like B2R)
deepen later. The brain never sends coordinates (B8): the backend owns the world
model and resolves a tempomem node id to a scene entity via its own `node_map`.

`backend=` is selected the same way B2R selects `L1_BACKEND`: `make_sim_backend(
"mock"|"genesis", ...)`; Isaac slots in later as another kind.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

_log = logging.getLogger("bodylink.sim")

__all__ = [
    "GenesisSimBackend",
    "MockSimBackend",
    "SceneObject",
    "SimBackend",
    "make_sim_backend",
]

# Verbs that physically move the base, vs in-place manipulation / idle settle.
_LOCOMOTION: frozenset[str] = frozenset({"navigate", "climb_stair"})


@dataclass(frozen=True, slots=True)
class SceneObject:
    """A static prop placed in the sim world: a named box at a world pose (meters)."""

    name: str
    pos: tuple[float, float, float]
    size: tuple[float, float, float] = (0.12, 0.12, 0.12)


@runtime_checkable
class SimBackend(Protocol):
    """A simulator backend: realize a gated verb, report `(success, message)`."""

    def __call__(
        self, verb: str, params: Mapping[str, Any], node_ids: tuple[int, ...]
    ) -> tuple[bool, str]: ...

    def close(self) -> None: ...


class MockSimBackend:
    """Deterministic no-physics backend — records calls; the test/CI default.

    Drop-in for the `SimDeviceAdapter` `backend` seam without a simulator: every
    verb succeeds instantly. `calls` records `(verb, params, node_ids)` for tests.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], tuple[int, ...]]] = []

    def __call__(
        self, verb: str, params: Mapping[str, Any], node_ids: tuple[int, ...]
    ) -> tuple[bool, str]:
        self.calls.append((verb, dict(params), tuple(node_ids)))
        return True, f"mock {verb} ok"

    def close(self) -> None:
        """No-op; present so a `MockSimBackend` satisfies `SimBackend`."""


def _import_genesis(injected: Any | None = None) -> Any:
    """Lazy-import the `genesis` module (or use an injected one for tests)."""
    if injected is not None:
        return injected
    try:
        import genesis as gs  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover - exercised via the extra
        # ImportError (not just ModuleNotFoundError): genesis raises a plain
        # ImportError when genesis is present but torch is missing — the 'sim'
        # extra ships both, so the same hint covers either gap.
        raise RuntimeError(
            "bodylink.sim Genesis backend needs the 'sim' extra (genesis-world + "
            "torch): pip install 'bodylink[sim]'  (or: uv sync --extra sim)"
        ) from e
    return gs


class GenesisSimBackend:
    """A `SimBackend` over a real Genesis physics scene (D5; mirrors B2R GenesisL1).

    Builds a scene (ground plane + a robot body + a fixed box per `SceneObject`)
    and steps physics per verb. `node_map` resolves a tempomem node id to a scene
    object name (the brain sends node ids, not coordinates — B8), so locomotion
    can head toward the right object; without a mapping it steps in place.

    `_genesis` injects a stand-in genesis module for GPU-free tests; in production
    it is imported lazily from the `sim` extra.
    """

    def __init__(
        self,
        objects: Sequence[SceneObject] = (),
        *,
        node_map: Mapping[int, str] | None = None,
        show_viewer: bool = False,
        dt: float = 0.01,
        settle_steps: int = 20,
        compute_backend: str = "cpu",
        _genesis: Any | None = None,
    ) -> None:
        gs = _import_genesis(_genesis)
        self._gs = gs
        self._settle = max(0, settle_steps)
        self._node_map: dict[int, str] = dict(node_map or {})

        gs.init(backend=getattr(gs, compute_backend, gs.cpu), logging_level="warning")
        self._scene = gs.Scene(
            show_viewer=show_viewer,
            rigid_options=gs.options.RigidOptions(dt=dt),
        )
        self._scene.add_entity(gs.morphs.Plane())
        # robot proxy — a single body standing at the origin (the coarse stand-in
        # for a full G1; deepened to a real MJCF/URDF robot later).
        self._robot = self._scene.add_entity(
            gs.morphs.Box(pos=(0.0, 0.0, 0.3), size=(0.3, 0.3, 0.6))
        )
        self._entities: dict[str, Any] = {}
        for obj in objects:
            self._entities[obj.name] = self._scene.add_entity(
                gs.morphs.Box(pos=obj.pos, size=obj.size, fixed=True)
            )
        self._scene.build()
        _log.info(
            "Genesis scene built: 1 robot + %d objects, settle=%d steps",
            len(self._entities),
            self._settle,
        )

    def __call__(
        self, verb: str, params: Mapping[str, Any], node_ids: tuple[int, ...]
    ) -> tuple[bool, str]:
        """Realize one gated verb in the sim, stepping physics; report the outcome."""
        try:
            if verb in _LOCOMOTION:
                self._approach(node_ids)
            self._step(self._settle)
            return True, f"genesis {verb} ok ({self._settle} steps)"
        except Exception as e:
            _log.warning("genesis verb %r failed: %s", verb, e)
            return False, f"genesis {verb} error: {e}"

    def _approach(self, node_ids: tuple[int, ...]) -> None:
        """Move the robot toward the first mapped target object (coarse), else idle."""
        target = next((self._entities[self._node_map[n]] for n in node_ids
                       if n in self._node_map and self._node_map[n] in self._entities), None)
        if target is None:
            return
        dst = self._read_xy(target.get_pos())
        if dst is None:
            return
        self._move_robot_xy(dst)

    def _move_robot_xy(self, dst: tuple[float, float]) -> None:
        """Teleport the robot base to a target xy (kinematic), keeping its height."""
        cur = self._read_xy(self._robot.get_pos())
        z = 0.3
        # a few interpolated hops so the motion is visible in the viewer
        steps = 5
        sx, sy = cur if cur is not None else (0.0, 0.0)
        for i in range(1, steps + 1):
            x = sx + (dst[0] - sx) * i / steps
            y = sy + (dst[1] - sy) * i / steps
            self._robot.set_pos((x, y, z))
            self._scene.step()

    @staticmethod
    def _read_xy(pos: Any) -> tuple[float, float] | None:
        """Read an (x, y) out of a Genesis pos (tensor/array/sequence), tolerantly."""
        try:
            seq = pos.tolist() if hasattr(pos, "tolist") else list(pos)
            return float(seq[0]), float(seq[1])
        except Exception:
            return None

    def _step(self, n: int) -> None:
        for _ in range(n):
            self._scene.step()

    def close(self) -> None:
        """Release the sim (best effort)."""
        import contextlib

        with contextlib.suppress(Exception):
            self._gs.destroy()


def make_sim_backend(kind: str = "mock", **kwargs: Any) -> SimBackend:
    """Build a simulator backend by kind — mirrors B2R's `L1_BACKEND` selection.

    ``"mock"`` → `MockSimBackend` (no deps). ``"genesis"`` → `GenesisSimBackend`
    (needs the ``sim`` extra). ``kwargs`` pass through to the chosen backend.
    """
    kind = kind.lower()
    if kind == "mock":
        return MockSimBackend()
    if kind == "genesis":
        return GenesisSimBackend(**kwargs)
    raise ValueError(f"unknown sim backend {kind!r}; known: 'mock', 'genesis'")
