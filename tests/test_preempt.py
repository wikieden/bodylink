"""Cancel/pause/resume handshake on the executor seam (T5-8, closes D-E fully).

The brain (or a supervisor) may preempt an in-flight step: `cancel` turns the
stream's next update into an ABORTED terminal without running `_execute`;
`pause` holds the stream on PAUSED updates until `resume` (or `cancel`). All
consumer-stepped and deterministic — no threads, no wall-clock.
"""

from __future__ import annotations

from mindloop import StatusUpdate, SubTask, TaskStatus

from bodylink import MockBody


def _sub() -> SubTask:
    return SubTask(id="p1", verb="navigate", target_node_ids=(1,))


class _Counting(MockBody):
    def __init__(self) -> None:
        super().__init__()
        self.executed = 0

    def _execute(self, subtask: SubTask) -> StatusUpdate:
        self.executed += 1
        return super()._execute(subtask)


def test_cancel_mid_stream_aborts_without_executing() -> None:
    body = _Counting()
    it = body.dispatch(_sub())
    assert next(it).status is TaskStatus.RUNNING
    body.cancel("p1")
    updates = list(it)
    assert updates[-1].status is TaskStatus.ABORTED
    assert updates[-1].touched_node_ids == (1,)  # B9 echo holds on abort too
    assert body.executed == 0  # the skill never ran


def test_pause_streams_paused_until_resume() -> None:
    body = _Counting()
    it = body.dispatch(_sub())
    next(it)  # RUNNING
    body.pause("p1")
    assert next(it).status is TaskStatus.PAUSED
    assert next(it).status is TaskStatus.PAUSED  # stays paused while held
    body.resume("p1")
    rest = list(it)
    assert rest[-1].status is TaskStatus.SUCCESS
    assert body.executed == 1


def test_cancel_while_paused_aborts() -> None:
    body = _Counting()
    it = body.dispatch(_sub())
    next(it)
    body.pause("p1")
    assert next(it).status is TaskStatus.PAUSED
    body.cancel("p1")
    rest = list(it)
    assert rest[-1].status is TaskStatus.ABORTED
    assert body.executed == 0


def test_cancel_is_per_subtask_and_one_shot() -> None:
    body = _Counting()
    it = body.dispatch(_sub())
    next(it)
    body.cancel("p1")
    assert list(it)[-1].status is TaskStatus.ABORTED
    # a fresh dispatch of the same id runs normally (the flag was consumed)
    it2 = body.dispatch(_sub())
    assert list(it2)[-1].status is TaskStatus.SUCCESS
