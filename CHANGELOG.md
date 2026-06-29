# Changelog

All notable changes to bodylink (the executor-adapter layer for Chronotope) are
documented here. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow SemVer (pre-1.0, the API may change between minor releases).

## [Unreleased]

### Added

- **Package created (P0, D5)** — the 4th Chronotope workspace member; ships the
  reference fill of the brain's `ExecutorAdapter` seam.
- **`MockBody`** — a no-hardware, no-network reference `ExecutorAdapter`: accepts
  `SubTask`s, streams `StatusUpdate`s (RUNNING → terminal), echoes node ids (B9),
  and reports success or a scripted typed failure with a `RecoveryHint` (B3).
  Raises `UnsupportedVerbError` for a verb outside the manifest (a planner bug).
- **`g1d_manifest()`** — the B10 reference `CapabilityManifest` (G1-D wheeled
  humanoid, 32 DOF, 2-D base, the declared verb set).
- **Multi-model adaptation framework (D3)** — supporting a new robot is now adding
  a manifest, not code:
  - **`manifest` catalog** — `load_manifest(name|path)` resolves builtin profiles
    from stdlib dicts (no dependency), or an external vendor `*.yaml`
    (`manifest_from_dict` + lazy PyYAML behind the `manifests` extra). Builtins
    (`list_profiles()`) span all three base_types: `g1d` (wheeled humanoid, 32
    DOF), `h1` + `gr1` (bipedal/legged humanoids — Unitree H1 19 DOF, Fourier GR-1
    40 DOF — both declare a `climb_stair` verb a wheeled base lacks), and `arm6` (a
    fixed 6-DOF manipulator that omits `navigate`/`charging`/`climb_stair`,
    proving the framework covers non-locomotion bodies). The D3 gate handles every
    capability difference with no brain change. `manifests/_TEMPLATE.yaml` +
    `manifests/fourier_gr1.yaml` are copy-me authoring templates.
  - **`BaseExecutorAdapter` SDK** — a device package subclasses it and implements
    only `_execute()`; the base handles the verb gate (D3), the RUNNING→terminal
    stream, and a guaranteed node-id echo (B9). `MockBody` is now a subclass.
  - **`check_executor_adapter()` conformance kit** — a portable contract check any
    body runs to prove it honors the seam (manifest well-formed, dispatch reaches
    terminal, node ids echoed B9, undeclared verb refused D3, typed error B3).
    All builtin bodies (g1d, h1, gr1, arm6) pass it.
  - **`SimDeviceAdapter` reference adapter** (`examples/sim_device.py`) — the
    realistic shape a real vendor device package follows, past `MockBody`: streams
    RUNNING → intermediate progress → terminal, and routes actuation through a
    pluggable `backend` transport seam (where a real robot's HTTP/ROS bridge
    plugs in; defaults to an in-process sim). Maps a backend failure to a typed
    `COMM_LOST`, supports injected typed faults for replan tests (P4).
  - **Physics-simulator backends** (`bodylink.sim`, behind the `sim` extra, D5) —
    a `backend` for `SimDeviceAdapter` that realizes a gated verb in a physics
    world. `MockSimBackend` (no deps, records calls — the CI default) and
    `GenesisSimBackend` (a real Genesis scene: `gs.init` → `gs.Scene` →
    `add_entity` → `build` → `step`, mirroring Brain2Robot's `GenesisL1`).
    `make_sim_backend("mock"|"genesis", …)` selects the backend the way B2R
    selects `L1_BACKEND`; Isaac slots in later. Verb realization is a coarse
    walking-skeleton (locomotion approaches the target object + steps physics,
    others settle N steps) — per-robot kinematics deepen later; the brain sends
    node ids only (B8), the backend resolves them via `node_map`. The `sim` extra
    ships `genesis-world` + `torch` (genesis needs torch but does not pin it).
    GPU-free CI tests exercise the Genesis path through an injected fake module;
    the **real sim** runs via `examples/genesis_demo.py` (`BODYLINK_SIM=genesis`)
    and was verified end-to-end on **both** a Linux RTX PRO 6000 host and macOS
    Apple Silicon (CPU backend) — H1 runs the laundry card, every verb stepping
    real physics.
  - **Multi-model demo** (`examples/multi_model_demo.py`, CI-tested) — one brain +
    the P2 laundry skill card driving every builtin body through `SimDeviceAdapter`:
    g1d (wheeled) and h1/gr1 (bipedal) run the identical plan to SUCCESS; arm6
    (fixed) has `navigate` dropped by the D3 gate — graceful degradation, no brain
    change.
  - **Docs** — `docs/en|zh/multi-model-adaptation-design.md` (design rationale: D3,
    alternatives, scaling/versioning/security) + `docs/en|zh/adding-a-robot-model.md`
    (how-to).

### Changed

- **`MockBody` refactored onto `BaseExecutorAdapter`** — identical behavior;
  `UnsupportedVerbError` now lives in `adapter.py` (re-exported, no API change).
- **`g1d_manifest()` adds the `operate_appliance` verb** (params `target`,
  `program`; `appliance_types` washer/stove/microwave/dishwasher) so the brain's
  Episteme skill cards (P2 — laundry, cooking) can drive appliances against
  `MockBody`. `dispatch()` is verb-agnostic, so no executor change was needed.

- **`g1d_manifest()` adds the `operate_appliance` verb** (params `target`,
  `program`; `appliance_types` washer/stove/microwave/dishwasher) so the brain's
  Episteme skill cards (P2 — laundry, cooking) can drive appliances against
  `MockBody`. `dispatch()` is verb-agnostic, so no executor change was needed.
