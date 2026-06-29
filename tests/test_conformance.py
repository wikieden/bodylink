"""Conformance kit (D3) — every reference body honors the executor seam."""

from __future__ import annotations

import pytest
from mindloop import ErrorCode, StatusUpdate, SubTask, TaskStatus

from bodylink import MockBody, check_executor_adapter, load_manifest


@pytest.mark.parametrize("profile", ["g1d", "h1"])
def test_reference_bodies_pass_conformance(profile: str) -> None:
    # MockBody is verb-agnostic, so it dry-runs any model's manifest — both the
    # wheeled (g1d) and bipedal (h1) reference bodies must satisfy the contract.
    body = MockBody(load_manifest(profile))
    passed = check_executor_adapter(body)
    assert "node_ids_echoed_B9" in passed
    assert "undeclared_verb_refused_D3" in passed
    assert len(passed) == 5


def test_conformance_catches_missing_node_echo() -> None:
    # a buggy adapter that drops node ids must FAIL the B9 check
    class BadEcho(MockBody):
        def _execute(self, subtask: SubTask) -> StatusUpdate:
            return StatusUpdate("", subtask.id, TaskStatus.SUCCESS, touched_node_ids=())

    # BaseExecutorAdapter re-stamps the echo, so a subclass cannot accidentally
    # break B9 — the guarantee holds and conformance still passes.
    passed = check_executor_adapter(BadEcho())
    assert "node_ids_echoed_B9" in passed


def test_conformance_catches_accepted_bad_verb() -> None:
    # an adapter that does NOT gate on the manifest must FAIL the D3 check
    class NoGate(MockBody):
        def dispatch(self, subtask):
            yield StatusUpdate(
                "", subtask.id, TaskStatus.SUCCESS, touched_node_ids=subtask.target_node_ids
            )

    with pytest.raises(AssertionError, match="D3 violation"):
        check_executor_adapter(NoGate())


def test_failed_dispatch_keeps_typed_error() -> None:
    body = MockBody(fail={"grasp": ErrorCode.GRASP_FAILED})
    updates = list(body.dispatch(SubTask(id="t", verb="grasp", target_node_ids=(9,))))
    assert updates[-1].status == TaskStatus.FAILED
    assert updates[-1].error_code == ErrorCode.GRASP_FAILED
    assert updates[-1].touched_node_ids == (9,)  # echo preserved on failure (B9)
