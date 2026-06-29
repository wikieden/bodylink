> 🌐 **English** · [中文](../zh/multi-model-adaptation-design.md)

# Design — Multi-model robot adaptation framework (D3)

**Status:** implemented (2026-06-28); this doc is the normative design rationale.
**Scope:** how `bodylink` lets the Chronotope brain (`mindloop`) drive **many robot
models** — bipedal and wheeled humanoids today, more body classes later — with **no
brain change**. Companion how-to: [adding-a-robot-model.md](adding-a-robot-model.md).
**Decision lineage:** D3 (open-vocab verbs + two-tier `CapabilityManifest`), B8
(brain never speaks joint/base geometry), B9 (node ids cross the seam), B3 (typed
errors), B10 (G1-D reference), D5 (MockBody / sim).

---

## 1. Goals & non-goals

**Goals**

- Adding a robot model is **declarative** — a manifest + a thin adapter, never a
  brain edit.
- One brain drives **bipedal and wheeled humanoids** from the same plans; differ
  only where the bodies genuinely differ (their verb set).
- "Swap the body, keep the mind" is **verified**, not asserted — a contract kit
  every body must pass.
- The core stays **dependency-light** (stdlib + numpy); heavy/optional concerns
  (YAML, sim) sit behind extras.

**Non-goals (here)**

- Locomotion, IK, whole-body control, gait — these live **below L2** in the device
  package, invisible to the brain (B8).
- Safety enforcement of plans — that is **Phylax (P3)**, a separate tier; this doc
  only carries the `safety` annotations a body/skill declares.
- Latent-space / VLA action interfaces — the current seam is **symbolic verbs +
  node ids** (see `docs/en/research/l3-l2-fusion-roadmap.md`); a latent seam is a
  future, additive option, not a replacement.

---

## 2. The problem

A humanoid fleet is heterogeneous: Unitree G1-D (wheeled base), Unitree H1
(bipedal), Fourier GR-1 (bipedal, dexterous hands), fixed-base arms, future
quadrupeds. A naive integration re-touches the planner for each robot — verb
enums, capability `if`s, per-robot branches — and the brain rots into a switch
statement over hardware. That does not scale past a handful of models and makes
every new robot a brain-team project.

**Key observation:** what actually varies across these bodies, *as seen by an S2
planner*, is small and bounded — **which skill verbs they support**. How a verb is
realized (legs vs wheels vs tracks) is a control problem below L2. So the brain
should depend only on a **declared verb set**, and everything else about a model
should be **data the brain never branches on**.

---

## 3. Design principles

1. **Model = data.** A robot is defined to the brain by a `CapabilityManifest`, not
   code. New model ⇒ new manifest.
2. **Locomotion below L2 (B8).** The brain plans `navigate target`; the body
   decides legs/wheels. `base_type` is metadata the **brain does not branch on**.
3. **Capability-gated planning (D3).** The planner/skill-cards may only emit verbs
   the manifest declares; undeclared verbs are dropped before dispatch.
4. **Closed audit chain (B9).** Every `SubTask` carries scene-graph node ids; the
   body echoes them in every `StatusUpdate`. Memory → actuator → memory stays
   traceable across any body.
5. **Typed faults (B3).** Failure is a `FAILED` update with a typed `ErrorCode` +
   `RecoveryHint`, never free text or an exception (raise only for transport/IO).
6. **Verified conformance.** A body is "compatible" only if it passes the
   conformance kit — compatibility is a test, not a promise.

---

## 4. Architecture

```
        ┌──────────────── mindloop (brain, S2) — UNCHANGED across bodies ───────────────┐
        │   IntentRouter → Planner / SkillCard → compile_commands → SubTask[]            │
        └───────────────────────────────────┬───────────────────────────────────────────┘
                                             │  ExecutorAdapter seam (D1)
                                             │  • dispatch(SubTask) → Iterator[StatusUpdate]
                                             │  • capabilities() → CapabilityManifest
        ┌────────────────────────────────────┼────────────────────────────────────────────┐
        │                    bodylink — the adaptation framework                            │
        │                                                                                   │
        │   manifest catalog          BaseExecutorAdapter SDK         conformance kit       │
        │   load_manifest(name|path)  ├ verb gate (D3)                check_executor_adapter │
        │   ├ builtins: g1d, h1       ├ RUNNING→terminal stream       ├ manifest well-formed │
        │   ├ manifest_from_dict      ├ node-id echo (B9)             ├ dispatch→terminal     │
        │   └ vendor *.yaml (extra)   └ _execute()  ◀── device fills  ├ B9 echo / D3 / B3     │
        └────────────────────────────────────┬────────────────────────────────────────────┘
                                             │  subclass + manifest
        ┌──────────────┬──────────────┬───────┴───────┬──────────────────┬─────────────────┐
        ▼              ▼              ▼               ▼                  ▼                 ▼
   MockBody(g1d)  MockBody(h1)   UnitreeG1D     UnitreeH1 (bipedal)  FourierGR1        your robot
   (dev/test)     (dev/test)     (vendor pkg)   (vendor pkg)         (vendor *.yaml)   (vendor pkg)
```

Three components, each a thin layer over the existing D1 seam:

| Component | File | Responsibility |
|---|---|---|
| **Manifest catalog** | `manifest.py` | resolve a model's `CapabilityManifest` by builtin name or vendor YAML |
| **Adapter SDK** | `adapter.py` | `BaseExecutorAdapter`: the boilerplate every body shares; device fills `_execute()` |
| **Conformance kit** | `conformance.py` | `check_executor_adapter()`: prove a body honors the seam |

---

## 5. The two-tier `CapabilityManifest` (model as data)

Defined in `mindloop.execute`; the brain owns the contract, bodies fill it.

- **Body Profile tier** (`BodyProfile`) — hardware identity: `profile_id`,
  `display_name`, `dof`, `base_type` (`wheeled` / `legged` / `fixed`), and optional
  `joints` / `sensors` / `gripper`. **Executor-facing**: the brain does *not* read
  joints/sensors/gripper (B8) — they ride along for the device layer and
  introspection only.
- **Verb tier** (`VerbSpec`) — the part the planner reads: `name`, `params` (the
  affordance-level argument keys, e.g. `target`, `program`), and `appliance_types`
  for appliance verbs. This is the **only** part of the manifest that changes what
  the brain plans.

A model is authored either as a stdlib dict (`manifest._BUILTIN_PROFILES`, the
builtin path, zero dependency) or an external YAML (`manifests/_TEMPLATE.yaml` →
`load_manifest("path.yaml")`, lazy PyYAML behind the `manifests` extra).

---

## 6. What varies across models — and where it goes

| Difference | Lands in | Brain branches on it? |
|---|---|---|
| bipedal / wheeled / fixed | `BodyProfile.base_type` | **No** — metadata only |
| DOF, joints, gripper kinematics, sensors | `BodyProfile.joints/gripper/sensors` | **No** — below L2 |
| supported skills, their params, drivable appliances | `VerbSpec` (verb tier) | **Yes** — D3 gate |
| how a verb is physically realized | the device adapter's `_execute()` | **No** |
| recoverable fault modes | typed `ErrorCode` + `RecoveryHint` (B3) | only at replan (P4) |

**Worked example — bipedal vs wheeled.** `g1d` (wheeled) and `h1` (bipedal)
share the manipulation/appliance verbs. `h1` additionally declares `climb_stair`
— a capability a wheeled base cannot honor. A skill card or planner that emits
`climb_stair` runs on `h1` and is **dropped on `g1d`** by the D3 gate, with no
brain change and no per-robot conditional. The *only* asymmetry between the two
bodies, at the planning layer, is that one verb.

---

## 7. Adapter SDK — `BaseExecutorAdapter`

A device package subclasses it and implements **only** `_execute(subtask) →
StatusUpdate`. The base provides, once, the contract every body would otherwise
re-implement (and re-bug):

- **Verb gate (D3):** refuse a `SubTask` whose verb the manifest does not declare
  (`UnsupportedVerbError`) — a planner bug should never reach hardware.
- **Stream shape:** yield `RUNNING`, then the terminal update — matching the body
  team's `/l2/task_status` topic.
- **Node-id echo (B9):** re-stamp the terminal update's `touched_node_ids` from
  the subtask, so a subclass *cannot* accidentally break the audit chain.

`_execute` is the only body-specific code: map `(verb, params, node_ids)` to the
robot SDK and report a terminal status. `MockBody` is itself a subclass (dogfood),
so the reference body and real bodies share the exact same scaffold.

---

## 8. Conformance kit — compatibility is a test

`check_executor_adapter(adapter)` runs any `ExecutorAdapter` through the seam
contract and raises on the first violation:

1. `capabilities()` returns a well-formed two-tier manifest (≥1 verb, known
   `base_type`).
2. `dispatch()` of a declared verb reaches a **terminal** status.
3. the terminal update **echoes the probe node ids** (B9).
4. an **undeclared verb is refused** (D3) — not silently run.
5. a `FAILED` terminal carries a **typed** `ErrorCode` (B3).

The two reference bodies (`g1d`, `h1`) are parametrized through it in
`tests/test_conformance.py`. A vendor imports the same function in their own test
suite — so "swap the body, keep the mind" is continuously verified per body, not
hoped. This is the linchpin that makes a growing fleet safe: a non-conformant body
fails CI, it does not silently mis-drive.

---

## 9. Scaling to N models

- **Catalog, not code.** Builtins live in one dict (`_BUILTIN_PROFILES`); vendors
  ship a YAML. `list_profiles()` enumerates builtins. Adding the 10th model is the
  same effort as the 2nd.
- **Capability-driven planning, already in place.** Because the planner and skill
  cards gate on `manifest.verb_names()` (D3), a richer or poorer body needs no new
  planning code — over-capable bodies simply get more verbs offered; under-capable
  bodies have extra verbs dropped. (Skill-card P2 already exercises this drop.)
- **Dry-run any model with no hardware.** `MockBody(load_manifest("h1"))` executes
  any model's plans deterministically — so a new model's plans are testable before
  a robot exists.
- **Vendor isolation.** Each real robot is an out-of-tree package depending on
  `bodylink` + `mindloop`; the workspace never grows a hardware dependency.

---

## 10. Versioning & compatibility

- **Verb vocabulary is the compatibility surface.** Brain and bodies agree on verb
  *names + param keys*. Adding a verb is backward-compatible (older bodies just
  don't declare it; the gate drops it). Renaming/removing a verb is breaking —
  treat the shared verb vocabulary as a versioned contract (changelog it).
- **`SubTask` fields are additive.** New optional fields (P1 added
  `skill`/`preconditions`/`effects`/`timeout_s`) default-construct, so old bodies
  keep working — they read the fields they understand.
- **Manifest schema** carries no explicit version yet; if the `BodyProfile`/
  `VerbSpec` shape changes, add a `schema_version` (mirrors the skill-card K2
  reservation).

---

## 11. Security — untrusted vendor manifests

A manifest (and a community skill card) can carry `safety` annotations and a
`provenance`. A manifest from an untrusted source is **data, not authority**: the
framework loads it, but honoring `safety`-bearing capabilities from an unsigned
source is gated by **Phylax (P3)** — signature/review before a body's or card's
`safety:` claims are trusted. `load_manifest(path)` performs no network IO and no
code execution (YAML via `safe_load`), so loading a manifest is side-effect-free;
the trust decision is deferred to the policy tier, not the loader.

---

## 12. Testing strategy

- **Per-body conformance** (`check_executor_adapter`) — the contract, run on every
  body incl. reference and vendor.
- **Network-free** — builtins are stdlib dicts; tests never need PyYAML or a robot.
  The vendor-YAML path is `importorskip("yaml")`.
- **Cross-model end-to-end** — `MockBody(manifest)` runs real brain plans (and P2
  skill cards) against each model; bipedal H1 and wheeled G1-D both execute the
  same laundry/cooking cards.

---

## 13. Roadmap

| State | Item |
|---|---|
| ✅ done | manifest catalog, `BaseExecutorAdapter`, conformance kit, builtins across all 3 base_types (g1d wheeled, h1+gr1 bipedal, arm6 fixed), vendor YAML path, how-to guide, **`SimDeviceAdapter`** (realistic streaming reference adapter w/ transport seam, past `MockBody`), **multi-model demo** (one brain + P2 laundry card drives every body; g1d/h1/gr1 identical plan, arm6 D3-degraded) |
| ✅ done | **physics-simulator backend** (`bodylink.sim`, `sim` extra) — `MockSimBackend` + `GenesisSimBackend` (real Genesis scene, mirrors B2R `GenesisL1`); `make_sim_backend("mock"\|"genesis")`. `examples/genesis_demo.py` runs H1 + the laundry card through real Genesis physics, **verified on a Linux RTX PRO 6000 host and macOS Apple Silicon** |
| next | a true **hardware** adapter — a device package whose `backend` drives a real robot (HTTP/ROS), not the sim; and deepening the coarse sim (per-robot IK / MJCF G1 keyframes like B2R). `SimDeviceAdapter` is the reference *shape*, not a driver |
| later | richer `VerbSpec` (typed param schemas, ranges, units); capability *negotiation* (body advertises limits, planner respects payload/reach); more `base_type`s (quadruped, dual-arm fixed); sim adapter behind `[sim]` (D5) |
| open | should `base_type` ever influence planning (e.g. stair-aware navigation), or stay strictly metadata? (current answer: metadata; revisit only with evidence) |

---

## 14. Alternatives considered

- **Per-robot planner branches / verb enums.** Rejected — turns the brain into a
  hardware switch; every robot becomes a brain-team change. (This framework exists
  to avoid exactly this.)
- **One mega-manifest with all robots' verbs + runtime capability flags.** Rejected
  — couples all bodies, and the planner must still filter per-robot; the per-model
  manifest + D3 gate is simpler and isolates vendors.
- **ROS-style action servers as the seam.** Orthogonal — a vendor adapter may use
  ROS internally; the brain-facing seam stays the typed `ExecutorAdapter` so the
  brain has no ROS dependency.
- **Latent / VLA action interface instead of symbolic verbs.** Deferred, additive
  (see l3-l2-fusion-roadmap). The symbolic seam is what makes capability gating and
  the audit chain (B9) tractable today; a latent seam would be a parallel adapter
  type, not a replacement for this one.
