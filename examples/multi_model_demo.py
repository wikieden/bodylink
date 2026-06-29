"""Multi-model demo — one brain, many bodies (D3, "swap the body, keep the mind").

Runs the **same** Chronotope brain (memory + reasoner + intent router + the P2
Episteme laundry skill card) against several robot models, swapping **only** the
executor body. The wheeled humanoid (g1d) and the bipedal humanoid (h1) execute
the identical skill-card plan; a fixed-base arm (arm6) shows D3 graceful
degradation — the planner drops the verbs that body cannot do.

Bodies are driven through `SimDeviceAdapter`, the realistic streaming reference
adapter (the shape a real vendor device package follows), not the minimal
`MockBody` — so this exercises the production-shaped dispatch path with no
hardware.

Run: `uv run python bodylink/examples/multi_model_demo.py`
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

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

from bodylink import load_manifest

# sim_device is a sibling example module (examples/ is not an installed package);
# put this dir on the path so the import resolves whether run as a script or
# imported by a test.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_device import SimDeviceAdapter

_DIM = 8
_PROFILES = ("g1d", "h1", "gr1", "arm6")
_INSTRUCTION = "wash the wool sweater"


def _laundry_card() -> SkillCard:
    """The P2 laundry skill card (fabric-aware), built from a dict (dep-free)."""
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
                    "params": {"program": "normal", "temperature_c": 40},
                },
                {"verb": "speak", "target": "Starting the wash now."},
            ],
            "rules": [
                {
                    "when": {"fabric": "wool"},
                    "target_verb": "operate_appliance",
                    "set_params": {"program": "delicate", "temperature_c": 30},
                }
            ],
        }
    )


def _feat(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).standard_normal(_DIM).astype("float32")
    return v / np.linalg.norm(v)


def _scene() -> SpatialMemory:
    mem = SpatialMemory.open(":memory:", embedding_dim=_DIM)
    mem.add_detections(
        [
            Detection("washer", _feat(1), (2.0, 0.0, 0.5), (1.8, -0.3, 0.0), (2.2, 0.3, 1.0)),
            Detection("clothes", _feat(2), (1.0, 0.5, 0.4), (0.9, 0.4, 0.3), (1.1, 0.6, 0.5)),
        ]
    )
    mem.commit()
    return mem


@dataclass(frozen=True, slots=True)
class BodyRun:
    """The outcome of running the laundry card on one body."""

    profile_id: str
    display_name: str
    base_type: str
    verbs: tuple[str, ...]
    speak: str
    all_success: bool
    wash_program: str
    supports_climb_stair: bool


def run_demo() -> list[BodyRun]:
    """Run the laundry card on every model; the brain config is identical per body."""
    mem = _scene()
    card = _laundry_card()
    runs: list[BodyRun] = []

    for profile in _PROFILES:
        manifest = load_manifest(profile)
        body = SimDeviceAdapter(manifest)  # realistic streaming adapter, no hardware
        # Same memory + reasoner + router + skill card every time — only the body
        # (executor) and the manifest the planner gates on change.
        brain = Brain(
            mem,
            ScriptedReasoner(),
            router=ScriptedIntentRouter(default="task"),
            planner=SkillCardPlanner(SkillLibrary([card]), manifest),
            executor=body,
        )
        result = brain.handle(_INSTRUCTION)
        plan = result.plan
        assert plan is not None  # task intent always plans
        wash = next((s for s in plan.subtasks if s.verb == "operate_appliance"), None)
        runs.append(
            BodyRun(
                profile_id=manifest.body_profile.profile_id,
                display_name=manifest.body_profile.display_name,
                base_type=manifest.body_profile.base_type,
                verbs=tuple(s.verb for s in plan.subtasks),
                speak=plan.speak,
                all_success=all(s.status == TaskStatus.SUCCESS for s in result.statuses),
                wash_program=str(wash.params.get("program", "")) if wash else "",
                supports_climb_stair="climb_stair" in manifest.verb_names(),
            )
        )
    return runs


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    runs = run_demo()
    print(f'\nInstruction: "{_INSTRUCTION}"  (one brain + the laundry skill card)\n')
    header = f"{'body':<21}{'base_type':<10}{'climb_stair':<12}{'wash':<10}{'ok':<4}plan"
    print(header)
    print("-" * len(header))
    for r in runs:
        stair = "yes" if r.supports_climb_stair else "—"
        ok = "✓" if r.all_success else "✗"
        print(
            f"{r.display_name:<21}{r.base_type:<10}{stair:<12}"
            f"{r.wash_program:<10}{ok:<4}{' → '.join(r.verbs)}"
        )
    print(
        "\nSame brain, swapped body: g1d (wheeled) and h1 (bipedal) run the identical\n"
        "plan. arm6 (fixed) drops `navigate` — the D3 gate degrades the plan to what\n"
        "the body can actually do, with no brain change.\n"
    )


if __name__ == "__main__":
    main()
