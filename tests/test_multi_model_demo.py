"""Multi-model demo (D3) — one brain drives wheeled + bipedal bodies end-to-end."""

from __future__ import annotations

from examples.multi_model_demo import run_demo


def test_one_brain_drives_every_model() -> None:
    runs = {r.profile_id: r for r in run_demo()}
    assert set(runs) == {"g1d", "h1", "gr1", "arm6"}

    # the wool rule fired identically on every body (skill card is body-agnostic)
    assert all(r.wash_program == "delicate" for r in runs.values())
    # every dispatched plan ran to terminal SUCCESS via the streaming SimDeviceAdapter
    assert all(r.all_success for r in runs.values())


def test_wheeled_and_bipedal_run_identical_plan() -> None:
    runs = {r.profile_id: r for r in run_demo()}
    full = ("navigate", "open_door", "grasp", "place", "operate_appliance")
    # g1d (wheeled) and h1 + gr1 (bipedal) execute the SAME plan — swap the body,
    # keep the mind: the brain config differs only in the executor.
    assert runs["g1d"].verbs == full
    assert runs["h1"].verbs == full
    assert runs["gr1"].verbs == full


def test_base_type_and_capability_differences() -> None:
    runs = {r.profile_id: r for r in run_demo()}
    assert runs["g1d"].base_type == "wheeled"
    assert runs["h1"].base_type == "legged"
    assert runs["arm6"].base_type == "fixed"
    # only legged bodies declare climb_stair (D3 capability gating)
    assert runs["h1"].supports_climb_stair and runs["gr1"].supports_climb_stair
    assert not runs["g1d"].supports_climb_stair
    # the fixed arm cannot navigate -> the D3 gate drops that step from its plan
    assert "navigate" not in runs["arm6"].verbs
    assert runs["arm6"].verbs[0] == "open_door"
