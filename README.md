> 🌐 **English** · [中文](README.zh.md)

# bodylink

The **execution-adapter layer** for [Chronotope](https://github.com/wikieden/tempomem) —
the 4th workspace member (D5). The brain (`mindloop`) ships the `ExecutorAdapter`
*protocol*; bodylink ships the reference *fill* and the per-body adaptation
framework.

> **Swap the body, keep the mind.** Each real robot is a separate, out-of-tree
> device package that implements the same `ExecutorAdapter` — differentiated only
> by its **Body Profile** + **verb set**. The brain never changes when you change
> the body (D3).

## What's here

| Piece | Role |
|---|---|
| `MockBody` | no-hardware reference `ExecutorAdapter` — accepts `SubTask`s, echoes node ids (B9), reports success or scripted typed failures (B3). Lets the L3 brain run end-to-end with no robot, no network. |
| `g1d_manifest()` | the B10 reference `CapabilityManifest` — G1-D wheeled humanoid (32 DOF, 2-D base, the declared verb set). |

## Install

```bash
pip install bodylink            # reference executor (depends on mindloop)
pip install bodylink[sim]       # + Genesis/Isaac physics sim (reserved)
```

## Quickstart

```python
from mindloop import SubTask
from bodylink import MockBody

body = MockBody()                                  # G1-D reference manifest
assert body.capabilities().supports("grasp")
for update in body.dispatch(SubTask(id="s1", verb="grasp", target_node_ids=(12,))):
    print(update.status, update.touched_node_ids)  # RUNNING … SUCCESS, ids echoed
```

> **Status:** P0 reference impl. The behaviour-tree runtime and real-body
> adapters land later; this package currently graduates from a workspace-tracked
> directory to its own repository before publish.

## License

Apache-2.0 — see [LICENSE](LICENSE).
