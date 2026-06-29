"""Genesis demo — drive the laundry skill card through a real physics sim (D5).

Wires the brain's `SimDeviceAdapter` to a `bodylink.sim` backend so a dispatched
plan actually steps a physics world. Defaults to the no-dependency `mock` backend
(runs anywhere); set `BODYLINK_SIM=genesis` to run the real Genesis scene (needs
the `sim` extra: `uv sync --extra sim`), and `GENESIS_VIEWER=true` to watch it.

    BODYLINK_SIM=mock     uv run python bodylink/examples/genesis_demo.py
    BODYLINK_SIM=genesis  uv run python bodylink/examples/genesis_demo.py
    BODYLINK_SIM=genesis GENESIS_VIEWER=true PROFILE=h1  uv run python …/genesis_demo.py

The brain sends verbs + tempomem node ids only (never coordinates — B8); the
backend owns the world model and resolves node id → scene object via `node_map`.
"""

from __future__ import annotations

import logging
import os
import sys

import numpy as np
from mindloop import (
    Brain,
    ScriptedIntentRouter,
    ScriptedReasoner,
    SkillCard,
    SkillCardPlanner,
    SkillLibrary,
    TaskStatus,
)
from tempomem import Detection, SpatialMemory

from bodylink import SceneObject, load_manifest, make_sim_backend

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_device import SimDeviceAdapter

_DIM = 8
# object name -> world centroid (meters); the sim places a box here and the scene
# graph stores a detection at the same spot, so node ids line up with sim entities.
_OBJECTS: dict[str, tuple[float, float, float]] = {
    "washer": (2.0, 0.0, 0.5),
    "clothes": (1.0, 0.5, 0.4),
}
_INSTRUCTION = "wash the wool sweater"


def _laundry_card() -> SkillCard:
    return SkillCard.from_dict(
        {
            "id": "laundry_basic",
            "category": "laundry",
            "steps": [
                {"verb": "navigate", "target": "washer"},
                {"verb": "open_door", "target": "washer"},
                {"verb": "grasp", "target": "clothes"},
                {"verb": "place", "target": "washer"},
                {
                    "verb": "operate_appliance",
                    "target": "washer",
                    "params": {"program": "normal"},
                },
                {"verb": "speak", "target": "Starting the wash now."},
            ],
            "rules": [
                {
                    "when": {"fabric": "wool"},
                    "target_verb": "operate_appliance",
                    "set_params": {"program": "delicate"},
                }
            ],
        }
    )


def _feat(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).standard_normal(_DIM).astype("float32")
    return v / np.linalg.norm(v)


def _scene_memory() -> tuple[SpatialMemory, dict[int, str], list[SceneObject]]:
    """Build the scene graph; return it plus the node-id→name map + sim objects."""
    mem = SpatialMemory.open(":memory:", embedding_dim=_DIM)
    for i, (name, c) in enumerate(_OBJECTS.items(), start=1):
        lo = (c[0] - 0.1, c[1] - 0.1, c[2] - 0.1)
        hi = (c[0] + 0.1, c[1] + 0.1, c[2] + 0.1)
        mem.add_detections([Detection(name, _feat(i), c, lo, hi)])
    mem.commit()
    node_map: dict[int, str] = {}
    for name in _OBJECTS:
        hits = mem.query(name, k=1)
        if hits.nodes:
            node_map[hits.nodes[0].id] = name
    objects = [SceneObject(name, pos) for name, pos in _OBJECTS.items()]
    return mem, node_map, objects


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    kind = os.getenv("BODYLINK_SIM", "mock").lower()
    profile = os.getenv("PROFILE", "g1d")
    show_viewer = os.getenv("GENESIS_VIEWER", "false").lower() == "true"

    mem, node_map, objects = _scene_memory()
    manifest = load_manifest(profile)

    backend = make_sim_backend(
        kind,
        objects=objects,
        node_map=node_map,
        show_viewer=show_viewer,
    ) if kind == "genesis" else make_sim_backend(kind)

    body = SimDeviceAdapter(manifest, backend=backend)
    brain = Brain(
        mem,
        ScriptedReasoner(),
        router=ScriptedIntentRouter(default="task"),
        planner=SkillCardPlanner(SkillLibrary([_laundry_card()]), manifest),
        executor=body,
    )

    print(
        f'\nSim backend: {kind}   body: {manifest.body_profile.display_name} '
        f'({manifest.body_profile.base_type})\nInstruction: "{_INSTRUCTION}"\n'
    )
    result = brain.handle(_INSTRUCTION)
    assert result.plan is not None
    for sub, st in zip(result.plan.subtasks, result.statuses, strict=True):
        mark = "✓" if st.status == TaskStatus.SUCCESS else "✗"
        print(f"  {mark} {sub.verb:<18} nodes={sub.target_node_ids}  {st.message}")
    print(f'\nspeak: "{result.plan.speak}"')
    ok = all(s.status == TaskStatus.SUCCESS for s in result.statuses)
    print(f"all steps succeeded: {ok}\n")

    if hasattr(backend, "close"):
        backend.close()


if __name__ == "__main__":
    main()
