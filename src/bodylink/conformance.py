"""Conformance kit — verify any `ExecutorAdapter` honors the brain's contract (D3).

"Swap the body, keep the mind" only holds if every body actually obeys the
executor seam. This is the portable check: a device package runs its adapter
through `check_executor_adapter()` and gets a pass/fail with reasons, so
conformance is *verified*, not hoped. The brain's own tests run the two reference
bodies (g1d, h1) through it.

The contract checked:

  * `capabilities()` returns a well-formed two-tier `CapabilityManifest` (≥1 verb,
    a known `base_type`).
  * `dispatch()` of a declared verb streams to a **terminal** `StatusUpdate`.
  * the terminal update **echoes the subtask's node ids** verbatim (B9).
  * an **undeclared verb is refused** (raises), never silently dispatched (D3).
  * a `FAILED` terminal carries a **typed** `ErrorCode` (B3), never a bare string.

Pure-stdlib; importable outside pytest. Returns the list of passed check names;
raises `AssertionError` (with a reason) on the first violation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mindloop import CapabilityManifest, ErrorCode, SubTask, TaskStatus

if TYPE_CHECKING:
    from mindloop import ExecutorAdapter

_BASE_TYPES = frozenset({"wheeled", "legged", "fixed"})


def check_executor_adapter(
    adapter: ExecutorAdapter, *, sample_node_ids: tuple[int, ...] = (1, 2)
) -> list[str]:
    """Run `adapter` through the executor-seam contract; return passed check names.

    `sample_node_ids` are forced onto the probe `SubTask` so the B9 echo can be
    asserted even on a body that would otherwise act on nothing. Raises
    `AssertionError` on the first contract violation.
    """
    passed: list[str] = []

    manifest = adapter.capabilities()
    assert isinstance(manifest, CapabilityManifest), "capabilities() must return CapabilityManifest"
    verbs = manifest.verb_names()
    assert verbs, "manifest declares no verbs"
    bt = manifest.body_profile.base_type
    assert bt in _BASE_TYPES, f"base_type {bt!r} not one of {sorted(_BASE_TYPES)}"
    passed.append("manifest_well_formed")

    verb = sorted(verbs)[0]
    probe = SubTask(id="conformance-0", verb=verb, target_node_ids=sample_node_ids)
    updates = list(adapter.dispatch(probe))
    assert updates, f"dispatch({verb!r}) yielded no StatusUpdate"
    terminal = updates[-1]
    assert terminal.status.is_terminal, f"stream did not end terminal (got {terminal.status})"
    passed.append("dispatch_reaches_terminal")

    assert terminal.touched_node_ids == sample_node_ids, (
        f"node ids not echoed (B9): sent {sample_node_ids}, got {terminal.touched_node_ids}"
    )
    passed.append("node_ids_echoed_B9")

    if terminal.status == TaskStatus.FAILED:
        assert terminal.error_code is None or isinstance(terminal.error_code, ErrorCode), (
            "FAILED update must carry a typed ErrorCode (B3), not a bare string"
        )
    passed.append("typed_error_contract")

    bogus = "____undeclared_verb____"
    assert bogus not in verbs, "test setup: bogus verb unexpectedly declared"
    refused = False
    try:
        list(adapter.dispatch(SubTask(id="conformance-1", verb=bogus)))
    except Exception:
        refused = True
    assert refused, f"adapter accepted undeclared verb {bogus!r} (D3 violation)"
    passed.append("undeclared_verb_refused_D3")

    return passed
