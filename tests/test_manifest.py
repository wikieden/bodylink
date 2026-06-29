"""Manifest catalog (D3) — builtin profiles, dict + YAML loading, model verbs."""

from __future__ import annotations

import pytest

from bodylink import (
    g1d_manifest,
    h1_manifest,
    list_profiles,
    load_manifest,
    manifest_from_dict,
)


def test_builtin_profiles_listed() -> None:
    assert set(list_profiles()) == {"g1d", "h1", "gr1", "arm6"}


def test_g1d_is_wheeled_with_seven_verbs() -> None:
    m = load_manifest("g1d")
    assert m.body_profile.base_type == "wheeled"
    assert m.body_profile.profile_id == "g1d"
    assert m.verb_names() == {
        "navigate",
        "grasp",
        "place",
        "detect",
        "open_door",
        "charging",
        "operate_appliance",
    }


def test_g1d_manifest_alias_matches_load() -> None:
    assert g1d_manifest().verb_names() == load_manifest("g1d").verb_names()


def test_h1_is_legged_and_adds_climb_stair() -> None:
    m = h1_manifest()
    assert m.body_profile.base_type == "legged"
    assert m.body_profile.dof == 19
    # bipedal-only locomotion verb the wheeled g1d lacks (D3)
    assert "climb_stair" in m.verb_names()
    assert "climb_stair" not in g1d_manifest().verb_names()


def test_gr1_is_legged_dexterous() -> None:
    m = load_manifest("gr1")
    assert m.body_profile.base_type == "legged"
    assert m.body_profile.dof == 40
    assert "climb_stair" in m.verb_names()


def test_arm6_is_fixed_and_cannot_move() -> None:
    m = load_manifest("arm6")
    assert m.body_profile.base_type == "fixed"
    names = m.verb_names()
    # a bolted-down arm cannot move its base — no locomotion/charging verbs
    assert "navigate" not in names
    assert "charging" not in names
    assert "climb_stair" not in names
    # but it still manipulates and operates appliances
    assert "grasp" in names
    assert "operate_appliance" in names


def test_unknown_builtin_raises() -> None:
    with pytest.raises(KeyError):
        load_manifest("no_such_robot")


def test_manifest_from_dict_roundtrip() -> None:
    m = manifest_from_dict(
        {
            "profile_id": "x",
            "display_name": "X",
            "dof": 7,
            "base_type": "fixed",
            "verbs": [{"name": "grasp", "params": ["target"]}],
        }
    )
    assert m.body_profile.base_type == "fixed"
    assert m.supports("grasp")
    assert m.verbs[0].params == ("target",)


def test_load_vendor_yaml_file() -> None:
    pytest.importorskip("yaml")
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "manifests" / "fourier_gr1.yaml"
    m = load_manifest(path)
    assert m.body_profile.profile_id == "fourier_gr1"
    assert m.body_profile.base_type == "legged"
    assert "climb_stair" in m.verb_names()
