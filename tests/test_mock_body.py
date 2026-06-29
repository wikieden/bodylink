"""P0 Chunk B — MockBody reference ExecutorAdapter (D5, B9, B3)."""

from __future__ import annotations

import pytest
from mindloop import ErrorCode, ExecutorAdapter, RecoveryKind, SubTask, TaskStatus

from bodylink import MockBody, UnsupportedVerbError, g1d_manifest


def test_mockbody_is_an_executor_adapter() -> None:
    assert isinstance(MockBody(), ExecutorAdapter)


def test_default_manifest_is_g1d() -> None:
    m = MockBody().capabilities()
    assert m.body_profile.profile_id == "g1d"
    assert m.body_profile.dof == 32
    assert m.supports("grasp") and not m.supports("fly")


def test_dispatch_streams_running_then_success_echoing_node_ids() -> None:
    body = MockBody()
    updates = list(body.dispatch(SubTask(id="s1", verb="grasp", target_node_ids=(12, 7))))
    assert [u.status for u in updates] == [TaskStatus.RUNNING, TaskStatus.SUCCESS]
    final = updates[-1]
    assert final.status.is_terminal
    assert final.subtask_id == "s1"
    assert final.touched_node_ids == (12, 7)  # B9: ids echoed verbatim
    assert final.error_code is None


def test_scripted_failure_returns_typed_error_and_recovery() -> None:
    body = MockBody(fail={"grasp": ErrorCode.GRASP_FAILED})
    final = list(body.dispatch(SubTask(id="s2", verb="grasp", target_node_ids=(9,))))[-1]
    assert final.status is TaskStatus.FAILED
    assert final.error_code is ErrorCode.GRASP_FAILED  # B3 typed, not free text
    assert final.recovery_actions[0].kind is RecoveryKind.POSITION_OFFSET
    assert final.touched_node_ids == (9,)


def test_unsupported_verb_raises_programmer_error() -> None:
    # D3: the planner must gate on the manifest; dispatching an unknown verb is a bug.
    with pytest.raises(UnsupportedVerbError):
        list(MockBody().dispatch(SubTask(id="s3", verb="teleport")))


def test_custom_manifest_overrides_default() -> None:
    body = MockBody(g1d_manifest())
    assert body.capabilities().verb_names() == {
        "navigate",
        "grasp",
        "place",
        "detect",
        "open_door",
        "charging",
        "operate_appliance",
    }
