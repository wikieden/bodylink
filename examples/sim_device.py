"""SimDeviceAdapter — the reference shape of a real vendor device package (D3, D5).

`MockBody` is deterministic and minimal: it streams only RUNNING → terminal. A
real robot integration looks more like *this* — a body that streams realistic
intermediate progress as the actuator runs, and that talks to the hardware
through a pluggable **transport seam** instead of faking the outcome inline.

`SimDeviceAdapter` is that reference. It is what an out-of-tree vendor package
copies: subclass `BaseExecutorAdapter`, override `dispatch()` to add the
mid-run progress stream a real device emits, and route the actual actuation
through the `backend` callable — the one seam where a real robot's HTTP / ROS
bridge plugs in:

    def my_robot_backend(verb, params, node_ids):
        resp = requests.post("http://robot.local/exec", json={...})
        return resp.ok, resp.text

    body = SimDeviceAdapter(load_manifest("g1d"), backend=my_robot_backend)

Out of the box the backend defaults to a deterministic in-process sim, so the
example is network-free and runnable with no hardware. The base contract is
preserved verbatim: the verb gate refuses an undeclared verb (D3,
`UnsupportedVerbError`), every yielded update echoes the subtask's node ids (B9),
and the stream always ends on a terminal status. `StatusUpdate.task_id` is left
empty — a bare body does not own task identity (the brain / a real L2 populates
it); correlation here is by `subtask_id`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping

from mindloop import (
    CapabilityManifest,
    ErrorCode,
    RecoveryHint,
    RecoveryKind,
    StatusUpdate,
    SubTask,
    TaskStatus,
)

from bodylink import BaseExecutorAdapter, UnsupportedVerbError

_log = logging.getLogger("bodylink.sim_device")

__all__ = ["Backend", "SimDeviceAdapter"]

# The transport seam: a real robot's HTTP/ROS bridge fills this. Given the gated
# verb, its params, and the target node ids (B9), return (success, message).
Backend = Callable[[str, dict, tuple[int, ...]], tuple[bool, str]]


def _sim_backend(verb: str, params: dict, node_ids: tuple[int, ...]) -> tuple[bool, str]:
    """Default in-process transport: succeed deterministically, no hardware/network."""
    return True, f"sim {verb} ok"


# Typed recovery hints a body offers with a failure (B3) — what the brain's
# replanner (P4) consumes. GRASP_FAILED gets a positional nudge; everything else
# falls back to a generic retry.
_RECOVERY: dict[ErrorCode, tuple[RecoveryHint, ...]] = {
    ErrorCode.GRASP_FAILED: (RecoveryHint(RecoveryKind.POSITION_OFFSET, 0.02),),
}
_DEFAULT_RECOVERY: tuple[RecoveryHint, ...] = (RecoveryHint(RecoveryKind.RETRY),)

# A backend that reports failure (real transport said the actuation failed, vs a
# scripted/injected fault) maps to a comms-class error: the brain could not be
# sure the body did the thing.
_BACKEND_FAILURE: ErrorCode = ErrorCode.COMM_LOST


class SimDeviceAdapter(BaseExecutorAdapter):
    """A realistic streaming `ExecutorAdapter` over a pluggable transport (D3, D5).

    Models a real device integration: `dispatch()` is overridden to stream
    RUNNING → `progress_steps` intermediate progress updates (monotonically
    increasing `progress` from 0.0 toward 1.0) → a terminal update, the way a
    real actuator reports motion. Actuation is delegated to `backend`, the
    transport seam (defaults to a deterministic in-process sim). `fail` scripts a
    verb → `ErrorCode` typed failure (like `MockBody`) for replan tests (P4); on
    an injected failure the backend is *not* called.

    The base contract is preserved by the override: the verb gate (D3), the node
    id echo on **every** update (B9), and a terminal end state.
    """

    def __init__(
        self,
        manifest: CapabilityManifest,
        *,
        backend: Backend | None = None,
        progress_steps: int = 2,
        fail: Mapping[str, ErrorCode] | None = None,
    ) -> None:
        super().__init__(manifest)
        self._backend: Backend = backend or _sim_backend
        self._progress_steps = max(0, progress_steps)
        self._fail = dict(fail or {})

    def dispatch(self, subtask: SubTask) -> Iterator[StatusUpdate]:
        """Gate the verb (D3), stream RUNNING → progress → terminal, echo ids (B9).

        Overrides the base two-update stream to interleave `progress_steps`
        intermediate progress updates (status RUNNING, increasing `progress`) the
        way a real device reports actuation. Refuses an undeclared verb with
        `UnsupportedVerbError`; every yielded update carries the subtask's
        `target_node_ids` as `touched_node_ids` (B9); the stream ends terminal.
        """
        verb = subtask.verb
        if not self._manifest.supports(verb):
            raise UnsupportedVerbError(
                f"body {self._manifest.body_profile.profile_id!r} does not support verb {verb!r}"
            )
        ids = subtask.target_node_ids
        _log.debug("dispatch %s(%s) targets=%s", verb, subtask.id, ids)

        yield StatusUpdate("", subtask.id, TaskStatus.RUNNING, progress=0.0, touched_node_ids=ids)

        # Evenly spaced intermediate progress (e.g. steps=2 → 0.33, 0.66); the
        # terminal carries 1.0. Monotonically increasing toward, but below, 1.0.
        for step in range(1, self._progress_steps + 1):
            progress = step / (self._progress_steps + 1)
            yield StatusUpdate(
                "", subtask.id, TaskStatus.RUNNING, progress=progress, touched_node_ids=ids
            )

        yield self._terminal(subtask, ids)

    def _terminal(self, subtask: SubTask, ids: tuple[int, ...]) -> StatusUpdate:
        """Resolve the terminal update: injected fault, else backend outcome."""
        verb = subtask.verb

        err = self._fail.get(verb)
        if err is not None:
            # Injected fault: do not touch the backend, report the typed failure.
            return StatusUpdate(
                "",
                subtask.id,
                TaskStatus.FAILED,
                progress=1.0,
                error_code=err,
                recovery_actions=_RECOVERY.get(err, _DEFAULT_RECOVERY),
                touched_node_ids=ids,
                message=f"sim failure: {err.value}",
            )

        ok, message = self._backend(verb, dict(subtask.params), ids)
        if not ok:
            return StatusUpdate(
                "",
                subtask.id,
                TaskStatus.FAILED,
                progress=1.0,
                error_code=_BACKEND_FAILURE,
                recovery_actions=_DEFAULT_RECOVERY,
                touched_node_ids=ids,
                message=f"backend failure: {message}",
            )
        return StatusUpdate(
            "",
            subtask.id,
            TaskStatus.SUCCESS,
            progress=1.0,
            touched_node_ids=ids,
            message=message,
        )
