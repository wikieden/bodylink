"""MockBody — a deterministic reference `ExecutorAdapter` for tests and dev (D5).

`bodylink` is the adaptation framework: the 4th Chronotope member ships the
reference fill of the brain's executor seam. `MockBody` is a no-hardware,
no-network body — it accepts `SubTask`s, echoes their node ids (B9), and reports
success (or a scripted failure with a typed recovery hint). It lets the L3 brain
be built and tested end-to-end with no real robot. A real robot ships its own
package implementing the same `ExecutorAdapter` (subclass `BaseExecutorAdapter`);
only the Body Profile + verb set differ ("swap the body, keep the mind", D3).

`MockBody` is verb-agnostic — point it at any model's manifest
(`MockBody(load_manifest("h1"))`) to dry-run that body's plans.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from mindloop import (
    CapabilityManifest,
    ErrorCode,
    RecoveryHint,
    RecoveryKind,
    StatusUpdate,
    SubTask,
    TaskStatus,
)

from .adapter import BaseExecutorAdapter, UnsupportedVerbError
from .manifest import load_manifest

_log = logging.getLogger("bodylink.mock")

__all__ = ["MockBody", "UnsupportedVerbError", "g1d_manifest"]


def g1d_manifest() -> CapabilityManifest:
    """The B10 reference manifest: G1-D wheeled humanoid (32 DOF, 2-D base).

    Thin alias for ``load_manifest("g1d")``; kept for back-compat.
    """
    return load_manifest("g1d")


# Typed recovery hints a body offers with a failure (B3) — what the brain's
# replanner (P4) will consume.
_RECOVERY: dict[ErrorCode, tuple[RecoveryHint, ...]] = {
    ErrorCode.GRASP_FAILED: (RecoveryHint(RecoveryKind.POSITION_OFFSET, 0.02),),
    ErrorCode.OBJECT_LOST: (RecoveryHint(RecoveryKind.REPLAN),),
}


class MockBody(BaseExecutorAdapter):
    """A reference `ExecutorAdapter` that fakes execution deterministically.

    `manifest` defaults to the G1-D reference (`g1d_manifest`). `fail` scripts a
    verb → `ErrorCode` mapping so a dispatch of that verb terminates `FAILED`
    with the matching typed recovery hint — used to drive replan tests (P4). The
    `StatusUpdate.task_id` is left empty: a bare body does not own task identity
    (the brain / a real L2 populates it); correlation here is by `subtask_id`. The
    verb gate, RUNNING→terminal stream, and node-id echo (B9) are inherited from
    `BaseExecutorAdapter`.
    """

    def __init__(
        self,
        manifest: CapabilityManifest | None = None,
        *,
        fail: Mapping[str, ErrorCode] | None = None,
    ) -> None:
        super().__init__(manifest or g1d_manifest())
        self._fail = dict(fail or {})

    def _execute(self, subtask: SubTask) -> StatusUpdate:
        """Fake one gated `SubTask`: scripted typed failure, else success."""
        verb = subtask.verb
        ids = subtask.target_node_ids
        _log.debug("dispatch %s(%s) targets=%s", verb, subtask.id, ids)
        err = self._fail.get(verb)
        if err is not None:
            return StatusUpdate(
                "",
                subtask.id,
                TaskStatus.FAILED,
                progress=1.0,
                error_code=err,
                recovery_actions=_RECOVERY.get(err, ()),
                touched_node_ids=ids,
                message=f"mock failure: {err.value}",
            )
        return StatusUpdate(
            "",
            subtask.id,
            TaskStatus.SUCCESS,
            progress=1.0,
            touched_node_ids=ids,
            message=f"mock {verb} ok",
        )
