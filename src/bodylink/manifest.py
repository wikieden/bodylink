"""Capability manifests — how a robot model declares itself to the brain (D3).

A robot model is defined to the brain by **data, not code**: a two-tier
`CapabilityManifest` (a `BodyProfile` hardware tier + a `VerbSpec` verb tier, both
from `mindloop.execute`). The brain reads only the verb tier (what it may plan);
the Body Profile tier is executor-facing. So **supporting a new model is adding a
manifest** — the brain changes nothing ("swap the body, keep the mind", D3).

Two ways in:

  * **Builtin profiles** — `load_manifest("g1d")` / `load_manifest("h1")` resolve
    Python-dict builtins shipped here. Stdlib-only, no dependency. `g1d` is a
    wheeled humanoid (Unitree G1-D), `h1` a bipedal/legged humanoid (Unitree H1).
  * **Vendor files** — `load_manifest("/path/to/my_robot.yaml")` loads an external
    YAML a device package authors. Lazy-imports PyYAML (the `manifests` extra);
    `manifests/*.yaml` here are copy-me templates.

`base_type` is the locomotion class (``wheeled`` / ``legged`` / ``fixed``). The
brain does **not** branch on it (locomotion lives below L2, D3/B8) — a bipedal and
a wheeled humanoid differ to the brain only in their declared *verbs*, never in
how `navigate` is realized. `base_type` is carried for introspection + the device
layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mindloop import BodyProfile, CapabilityManifest, VerbSpec

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

# Verbs shared by both reference humanoids — manipulation + appliance use the
# brain plans in (D3 open-vocab). Locomotion-specific verbs are added per model.
_COMMON_VERBS: tuple[dict[str, Any], ...] = (
    {"name": "navigate", "params": ["target"]},
    {"name": "grasp", "params": ["target"]},
    {"name": "place", "params": ["target", "location"]},
    {"name": "detect"},
    {"name": "open_door", "params": ["target"]},
    {"name": "charging"},
    {
        "name": "operate_appliance",
        "params": ["target", "program"],
        "appliance_types": ["washer", "stove", "microwave", "dishwasher"],
    },
)

# Verbs for a fixed-base manipulator: manipulation + appliance use only. A bolted
# arm cannot move its base, so the locomotion/charging verbs (navigate, charging,
# climb_stair) of _COMMON_VERBS are deliberately omitted — demonstrating that the
# D3 verb tier, not code, is what gates what the brain may plan on a body.
_ARM_VERBS: tuple[dict[str, Any], ...] = (
    {"name": "grasp", "params": ["target"]},
    {"name": "place", "params": ["target", "location"]},
    {"name": "detect"},
    {"name": "open_door", "params": ["target"]},
    {
        "name": "operate_appliance",
        "params": ["target", "program"],
        "appliance_types": ["washer", "stove", "microwave", "dishwasher"],
    },
)

# Builtin model profiles (stdlib dicts — the canonical no-dependency source).
# Add a model here, or ship a YAML and `load_manifest(path)` it.
_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "g1d": {
        "profile_id": "g1d",
        "display_name": "Unitree G1-D",
        "dof": 32,
        "base_type": "wheeled",
        "verbs": list(_COMMON_VERBS),
    },
    "h1": {
        "profile_id": "h1",
        "display_name": "Unitree H1",
        "dof": 19,
        "base_type": "legged",
        # a bipedal humanoid declares a locomotion verb a wheeled base cannot
        # honor — the D3 gate lets a skill card use `climb_stair` only on bodies
        # that declare it, with no brain change.
        "verbs": [*_COMMON_VERBS, {"name": "climb_stair", "params": ["target"]}],
    },
    "gr1": {
        "profile_id": "gr1",
        "display_name": "Fourier GR-1",
        "dof": 40,
        # legged: a bipedal dexterous humanoid — like h1 it walks, so it declares
        # the same locomotion verb (climb_stair) a wheeled base cannot honor.
        "base_type": "legged",
        "verbs": [*_COMMON_VERBS, {"name": "climb_stair", "params": ["target"]}],
    },
    "arm6": {
        "profile_id": "arm6",
        "display_name": "Reference 6-DOF Arm",
        "dof": 6,
        # fixed: a bolted-down 6-DOF manipulator with no mobility — its verb set
        # (_ARM_VERBS) omits navigate/charging/climb_stair, proving the framework
        # covers non-locomotion bodies, not just humanoids.
        "base_type": "fixed",
        "verbs": list(_ARM_VERBS),
    },
}


def manifest_from_dict(data: Mapping[str, Any]) -> CapabilityManifest:
    """Build a `CapabilityManifest` from a plain dict (the YAML/JSON shape). Stdlib.

    Shape: ``{profile_id, display_name, dof, base_type, joints?, sensors?,
    gripper?, verbs: [{name, params?, appliance_types?}, ...]}``.
    """
    verbs = tuple(
        VerbSpec(
            name=str(v["name"]),
            params=tuple(v.get("params", ())),
            appliance_types=tuple(v.get("appliance_types", ())),
        )
        for v in data.get("verbs", ())
    )
    profile = BodyProfile(
        profile_id=str(data["profile_id"]),
        display_name=str(data.get("display_name", data["profile_id"])),
        dof=int(data.get("dof", 0)),
        base_type=str(data.get("base_type", "fixed")),
        joints=dict(data.get("joints", {})),
        sensors=dict(data.get("sensors", {})),
        gripper=dict(data.get("gripper", {})),
    )
    return CapabilityManifest(body_profile=profile, verbs=verbs)


def list_profiles() -> tuple[str, ...]:
    """The builtin model profile ids (``("g1d", "h1", "gr1", "arm6")``)."""
    return tuple(_BUILTIN_PROFILES)


def load_manifest(name_or_path: str | Path) -> CapabilityManifest:
    """Resolve a `CapabilityManifest` by builtin name or external YAML path.

    A bare builtin id (``"g1d"``, ``"h1"``) builds from the stdlib dicts shipped
    here — no dependency. Anything ending ``.yaml`` / ``.yml`` is read as a vendor
    file (lazy PyYAML, the ``manifests`` extra). Raises `KeyError` for an unknown
    builtin name, `RuntimeError` if PyYAML is missing for a file.
    """
    key = str(name_or_path)
    if key in _BUILTIN_PROFILES:
        return manifest_from_dict(_BUILTIN_PROFILES[key])
    if key.endswith((".yaml", ".yml")):
        return _load_yaml(name_or_path)
    raise KeyError(
        f"unknown body profile {key!r}; builtins are {list_profiles()}, "
        "or pass a path to a *.yaml manifest"
    )


def _load_yaml(path: str | Path) -> CapabilityManifest:
    try:
        import yaml
    except ModuleNotFoundError as e:  # pragma: no cover - exercised via extra
        raise RuntimeError(
            "loading a manifest from YAML needs PyYAML — install the 'manifests' "
            "extra: pip install 'bodylink[manifests]'"
        ) from e
    from pathlib import Path as _Path

    data = yaml.safe_load(_Path(path).read_text(encoding="utf-8"))
    return manifest_from_dict(data)
