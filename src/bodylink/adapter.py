"""BaseExecutorAdapter — the SDK base for a robot device package (D3).

A real robot ships its own `ExecutorAdapter` (the brain dispatches `SubTask`s to
it, reads `StatusUpdate`s back). This base handles the boilerplate every body
shares — the verb gate (D3: refuse a verb the manifest does not declare), the
RUNNING → terminal stream, and echoing the subtask's node ids back (B9, so the
audit chain from memory to actuator stays closed) — so a device package only
implements `_execute()`: run one already-gated `SubTask`, return its terminal
`StatusUpdate`.

Subclass it, pass a `CapabilityManifest` (usually `load_manifest("h1")` or a
vendor YAML), and you have a conformant body. `MockBody` is itself a subclass.
Override `dispatch()` directly only if you need multiple progress updates mid-run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mindloop import StatusUpdate, TaskStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mindloop import CapabilityManifest, SubTask


class UnsupportedVerbError(ValueError):
    """Raised when a `SubTask` names a verb the body does not declare (D3).

    A programmer error, not a task outcome: the planner must gate on the body's
    `CapabilityManifest` and never emit an unsupported verb. Raised (not returned)
    because it signals a brain-side bug.
    """


class BaseExecutorAdapter:
    """Reusable `ExecutorAdapter` scaffold; subclasses implement `_execute`."""

    def __init__(self, manifest: CapabilityManifest) -> None:
        self._manifest = manifest

    def capabilities(self) -> CapabilityManifest:
        """Return this body's two-tier capability manifest (D3)."""
        return self._manifest

    def dispatch(self, subtask: SubTask) -> Iterator[StatusUpdate]:
        """Gate the verb (D3), stream RUNNING → terminal, echo node ids (B9).

        Refuses an undeclared verb with `UnsupportedVerbError`. Yields a RUNNING
        update, then the terminal `StatusUpdate` from `_execute`, re-stamping its
        `touched_node_ids` with the subtask's so the echo (B9) is guaranteed even
        if a subclass forgets.
        """
        verb = subtask.verb
        if not self._manifest.supports(verb):
            raise UnsupportedVerbError(
                f"body {self._manifest.body_profile.profile_id!r} does not support verb {verb!r}"
            )
        ids = subtask.target_node_ids
        yield StatusUpdate("", subtask.id, TaskStatus.RUNNING, progress=0.0, touched_node_ids=ids)
        terminal = self._execute(subtask)
        if terminal.touched_node_ids != ids:
            # guarantee the B9 echo regardless of what the subclass returned
            terminal = StatusUpdate(
                task_id=terminal.task_id,
                subtask_id=terminal.subtask_id,
                status=terminal.status,
                progress=terminal.progress,
                error_code=terminal.error_code,
                recovery_actions=terminal.recovery_actions,
                touched_node_ids=ids,
                message=terminal.message,
            )
        yield terminal

    def _execute(self, subtask: SubTask) -> StatusUpdate:
        """Run one already-gated `SubTask`; return its terminal `StatusUpdate`.

        Expected task failure is a `FAILED` update with a typed `ErrorCode` +
        `RecoveryHint` (B3), never an exception (returns-over-raises). Raise only
        for transport/IO failure.
        """
        raise NotImplementedError
