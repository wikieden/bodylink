"""SimDeviceAdapter — reference vendor-style streaming body over a transport seam."""

from __future__ import annotations

import pytest
from examples.sim_device import SimDeviceAdapter
from mindloop import ErrorCode, SubTask, TaskStatus

from bodylink import UnsupportedVerbError, check_executor_adapter, load_manifest


@pytest.mark.parametrize("profile", ["g1d", "h1"])
def test_conforms_to_executor_seam(profile: str) -> None:
    adapter = SimDeviceAdapter(load_manifest(profile))
    passed = check_executor_adapter(adapter)
    assert "node_ids_echoed_B9" in passed
    assert "undeclared_verb_refused_D3" in passed


def test_streams_monotonic_progress_to_single_terminal() -> None:
    body = SimDeviceAdapter(load_manifest("g1d"))
    updates = list(body.dispatch(SubTask(id="t", verb="navigate", target_node_ids=(5,))))

    # RUNNING(0.0) + 2 progress + terminal = 4 updates (progress_steps default 2).
    assert len(updates) >= 4

    progresses = [u.progress for u in updates]
    assert progresses == sorted(progresses), "progress must be non-decreasing"

    terminals = [u for u in updates if u.status.is_terminal]
    assert len(terminals) == 1
    assert updates[-1] is terminals[0], "only the last update may be terminal"

    assert all(u.touched_node_ids == (5,) for u in updates), "B9: every update echoes ids"


def test_injected_fault_returns_typed_error_and_recovery() -> None:
    body = SimDeviceAdapter(load_manifest("g1d"), fail={"grasp": ErrorCode.GRASP_FAILED})
    final = list(body.dispatch(SubTask(id="t", verb="grasp", target_node_ids=(9,))))[-1]

    assert final.status is TaskStatus.FAILED
    assert final.error_code is ErrorCode.GRASP_FAILED  # B3 typed, not free text
    assert final.recovery_actions, "a typed failure offers a recovery hint (B3)"
    assert final.touched_node_ids == (9,)  # B9 still echoed on failure


def test_custom_backend_is_called_and_failure_maps_to_comm_lost() -> None:
    calls: list[tuple[str, dict, tuple[int, ...]]] = []

    def recording_backend(
        verb: str, params: dict, node_ids: tuple[int, ...]
    ) -> tuple[bool, str]:
        calls.append((verb, params, node_ids))
        return False, "boom"

    body = SimDeviceAdapter(load_manifest("g1d"), backend=recording_backend)
    final = list(body.dispatch(SubTask(id="t", verb="navigate", target_node_ids=(3,))))[-1]

    assert final.status is TaskStatus.FAILED
    assert final.error_code is ErrorCode.COMM_LOST  # backend failure → comms-class error
    assert final.touched_node_ids == (3,)
    assert calls and calls[0][0] == "navigate", "backend received the dispatched verb"


def test_undeclared_verb_raises_programmer_error() -> None:
    # D3: dispatching a verb the manifest does not declare is a brain-side bug.
    with pytest.raises(UnsupportedVerbError):
        list(SimDeviceAdapter(load_manifest("g1d")).dispatch(SubTask(id="t", verb="teleport")))
