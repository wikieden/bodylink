"""Sim backends (D5) — GPU-free: real genesis is absent, a fake stands in.

The Genesis code path is exercised through an injected fake `genesis` module that
mimics the API surface `GenesisSimBackend` uses (mirrors B2R's verified calls), so
the scene-build + verb-step + locomotion-approach logic is tested with no GPU and
no `genesis` install. The real sim is validated on the GPU host separately.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

# the realistic streaming adapter lives in examples/ (see test_sim_device.py)
from examples.sim_device import SimDeviceAdapter
from mindloop import SubTask, TaskStatus

from bodylink import (
    GenesisSimBackend,
    MockSimBackend,
    SceneObject,
    load_manifest,
    make_sim_backend,
)


# --------------------------------------------------------------------------- #
# mock backend + factory
# --------------------------------------------------------------------------- #
def test_mock_backend_drives_adapter_end_to_end() -> None:
    backend = MockSimBackend()
    body = SimDeviceAdapter(load_manifest("g1d"), backend=backend)
    updates = list(body.dispatch(SubTask(id="t", verb="navigate", target_node_ids=(7,))))
    assert updates[-1].status == TaskStatus.SUCCESS
    assert updates[-1].touched_node_ids == (7,)  # B9
    assert backend.calls == [("navigate", {}, (7,))]


def test_factory_kinds() -> None:
    assert isinstance(make_sim_backend("mock"), MockSimBackend)
    with pytest.raises(ValueError, match="unknown sim backend"):
        make_sim_backend("nope")


def test_genesis_missing_dep_raises_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    # force the genesis import to fail (whether or not it is installed) so the
    # 'sim' extra hint is verified deterministically — covers genesis OR torch
    # missing (genesis raises a plain ImportError when torch is absent).
    import builtins

    real_import = builtins.__import__

    def _fail_genesis(name: str, *args: object, **kwargs: object) -> object:
        if name == "genesis":
            raise ImportError("simulated: genesis/torch not installed")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fail_genesis)
    with pytest.raises(RuntimeError, match=r"sim extra|bodylink\[sim\]"):
        GenesisSimBackend()


# --------------------------------------------------------------------------- #
# genesis path via an injected fake module
# --------------------------------------------------------------------------- #
class _FakeEntity:
    def __init__(self, pos=(0.0, 0.0, 0.0)) -> None:
        self._pos = list(pos)

    def get_pos(self):
        return list(self._pos)

    def set_pos(self, pos) -> None:
        self._pos = list(pos)


class _FakeScene:
    def __init__(self) -> None:
        self.steps = 0
        self.built = False
        self.entities: list[_FakeEntity] = []

    def add_entity(self, morph, surface=None):
        e = _FakeEntity(pos=getattr(morph, "pos", (0.0, 0.0, 0.0)))
        self.entities.append(e)
        return e

    def build(self) -> None:
        self.built = True

    def step(self) -> None:
        self.steps += 1


def _fake_genesis() -> SimpleNamespace:
    """A stand-in `genesis` module covering the API GenesisSimBackend touches."""
    scene = _FakeScene()

    def _box(pos=(0.0, 0.0, 0.0), size=(0.1, 0.1, 0.1), fixed=False):
        return SimpleNamespace(pos=pos, size=size, fixed=fixed)

    return SimpleNamespace(
        cpu="cpu",
        init=lambda backend=None, logging_level=None: None,
        Scene=lambda show_viewer=False, rigid_options=None: scene,
        options=SimpleNamespace(RigidOptions=lambda dt=0.01: SimpleNamespace(dt=dt)),
        morphs=SimpleNamespace(Plane=lambda: SimpleNamespace(), Box=_box),
        surfaces=SimpleNamespace(Default=lambda **kw: SimpleNamespace(**kw)),
        destroy=lambda: None,
        _scene=scene,  # test handle
    )


def test_genesis_builds_scene_and_steps_per_verb() -> None:
    gs = _fake_genesis()
    be = GenesisSimBackend(
        [SceneObject("washer", (2.0, 0.0, 0.3))],
        node_map={1: "washer"},
        settle_steps=20,
        _genesis=gs,
    )
    assert gs._scene.built
    # a non-locomotion verb just settles N steps
    ok, msg = be("grasp", {}, (1,))
    assert ok and "genesis grasp ok" in msg
    assert gs._scene.steps == 20


def test_genesis_locomotion_approaches_mapped_target() -> None:
    gs = _fake_genesis()
    be = GenesisSimBackend(
        [SceneObject("washer", (2.0, 0.0, 0.3))],
        node_map={1: "washer"},
        settle_steps=10,
        _genesis=gs,
    )
    before = gs._scene.steps
    ok, _ = be("navigate", {}, (1,))
    assert ok
    # navigate = 5 approach hops + 10 settle steps
    assert gs._scene.steps - before == 15


def test_genesis_backend_drives_adapter() -> None:
    gs = _fake_genesis()
    be = GenesisSimBackend(node_map={}, settle_steps=3, _genesis=gs)
    body = SimDeviceAdapter(load_manifest("h1"), backend=be)
    updates = list(body.dispatch(SubTask(id="t", verb="open_door", target_node_ids=(2,))))
    assert updates[-1].status == TaskStatus.SUCCESS
    assert updates[-1].touched_node_ids == (2,)
