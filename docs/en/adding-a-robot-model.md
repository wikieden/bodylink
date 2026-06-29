> 🌐 **English** · [中文](../zh/adding-a-robot-model.md)

# Adding a robot model (D3)

Chronotope's brain (`mindloop`) plans in **skill verbs** and dispatches `SubTask`s
carrying scene-graph **node ids** — never joint angles or base-frame geometry
(D3/B8). So a robot model is defined to the brain entirely by **data + a thin
adapter**, and the brain code never changes. "Swap the body, keep the mind."

A bipedal humanoid and a wheeled humanoid differ to the brain **only in their
declared verbs**. How `navigate` is realized — legs vs wheels — lives below L2, in
the device package, invisible to the planner.

> This is the **how-to**. For *why* it is shaped this way (the D3 rationale,
> alternatives, scaling/versioning/security), see the design doc:
> [multi-model-adaptation-design.md](multi-model-adaptation-design.md).

## Two pieces

### 1. A `CapabilityManifest` — the model, as data

The two-tier contract the brain reads at plan time:

- **Body Profile** — hardware identity: `profile_id`, `display_name`, `dof`,
  `base_type` (`wheeled` / `legged` / `fixed`), optional `joints`/`sensors`/`gripper`
  (executor-facing; the brain does not read these).
- **Verb tier** — the `VerbSpec`s the brain may plan. Only declared verbs are
  dispatched; a skill card using an undeclared verb is dropped (the D3 gate).

Ship it as a builtin dict (see `manifest._BUILTIN_PROFILES`) or an external YAML
(copy `manifests/_TEMPLATE.yaml`). Load it:

```python
from bodylink import load_manifest
m = load_manifest("h1")                      # builtin: Unitree H1, legged
m = load_manifest("/opt/myrobot/model.yaml") # vendor file (needs the `manifests` extra)
```

A bipedal body just declares its locomotion capability — e.g. `h1` adds
`climb_stair`, which the wheeled `g1d` lacks. The brain plans `climb_stair` only
on bodies that declare it; no brain change.

### 2. An `ExecutorAdapter` — run the verbs

Subclass `BaseExecutorAdapter` and implement only `_execute()`. The base handles
the verb gate (D3), the RUNNING→terminal stream, and the node-id echo (B9):

```python
from bodylink import BaseExecutorAdapter, load_manifest
from mindloop import StatusUpdate, SubTask, TaskStatus

class MyRobot(BaseExecutorAdapter):
    def __init__(self):
        super().__init__(load_manifest("/opt/myrobot/model.yaml"))

    def _execute(self, subtask: SubTask) -> StatusUpdate:
        ok = my_sdk.run(subtask.verb, subtask.params, subtask.target_node_ids)
        status = TaskStatus.SUCCESS if ok else TaskStatus.FAILED
        return StatusUpdate("", subtask.id, status, progress=1.0,
                            touched_node_ids=subtask.target_node_ids)
```

Expected task failure is a `FAILED` update with a **typed** `ErrorCode` +
`RecoveryHint` (B3) — never an exception. Raise only for transport/IO failure.

## 3. Prove it conforms

Run your adapter through the conformance kit before shipping — this is what makes
"swap the body" safe, not hoped:

```python
from bodylink import check_executor_adapter
check_executor_adapter(MyRobot())   # raises AssertionError on any contract violation
```

It checks: manifest well-formed, dispatch reaches a terminal status, node ids are
echoed (B9), an undeclared verb is refused (D3), a `FAILED` update carries a typed
error (B3). The two reference bodies — `g1d` (wheeled) and `h1` (bipedal) — pass
it in `tests/test_conformance.py`; parametrize the same test over your body.

## Checklist

1. Write the manifest (builtin dict or `*.yaml`) — set `base_type`, list verbs.
2. Subclass `BaseExecutorAdapter`, implement `_execute()`.
3. Map your faults onto the typed `ErrorCode`s (B3).
4. Pass `check_executor_adapter()`.
5. Dry-run plans with `MockBody(your_manifest)` before touching hardware.
