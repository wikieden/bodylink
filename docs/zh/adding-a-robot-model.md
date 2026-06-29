> 🌐 [English](../en/adding-a-robot-model.md) · **中文**

# 接入一个机器人机型（D3）

Chronotope 的大脑（`mindloop`）以**技能动词**规划、派发携带场景图 **node id** 的
`SubTask` —— 从不碰关节角或底盘几何（D3/B8）。所以一个机型对大脑而言完全由
**数据 + 一个薄适配器**定义，大脑代码永不改。「换本体、留大脑」。

双足人形和轮式人形对大脑的区别**只在声明的动词**。`navigate` 怎么实现 —— 腿还是轮 ——
在 L2 以下、设备包里，规划器看不见。

> 这是**怎么做**。要看*为什么*这样设计（D3 依据、备选权衡、扩展/版本/安全），见设计方案：
> [multi-model-adaptation-design.md](multi-model-adaptation-design.md)。

## 两件东西

### 1. 一个 `CapabilityManifest` —— 机型即数据

大脑规划时读的两层契约：

- **Body Profile** —— 硬件身份：`profile_id`、`display_name`、`dof`、`base_type`
  （`wheeled` / `legged` / `fixed`）、可选 `joints`/`sensors`/`gripper`
  （面向执行器；大脑不读）。
- **动词层** —— 大脑可规划的 `VerbSpec`。只有声明过的动词才派发；技能卡用了未声明
  的动词会被丢弃（D3 gate）。

以内置 dict 发布（见 `manifest._BUILTIN_PROFILES`）或外部 YAML
（复制 `manifests/_TEMPLATE.yaml`）。加载：

```python
from bodylink import load_manifest
m = load_manifest("h1")                      # 内置：Unitree H1，腿式
m = load_manifest("/opt/myrobot/model.yaml") # 厂商文件（需 `manifests` extra）
```

双足体只需声明自己的运动能力 —— 如 `h1` 加了 `climb_stair`，轮式 `g1d` 没有。大脑只在
声明了它的本体上规划 `climb_stair`；大脑不改。

### 2. 一个 `ExecutorAdapter` —— 执行动词

继承 `BaseExecutorAdapter`，只实现 `_execute()`。基类处理动词 gate（D3）、
RUNNING→终态流、node-id 回显（B9）：

```python
from bodylink import BaseExecutorAdapter, load_manifest
from mindloop import StatusUpdate, SubTask, TaskStatus

class MyRobot(BaseExecutorAdapter):
    def __init__(self):
        super().__init__(load_manifest("/opt/myrobot/model.yaml"))

    def _execute(self, subtask: SubTask) -> StatusUpdate:
        ok = my_sdk.run(subtask.verb, subtask.params, subtask.target_node_ids)
        status = TaskStatus.SUCCESS if ok else TaskStatus.FAILED
        return StatusUpdate("", subtask.id, status, progress=1.0,
                            touched_node_ids=subtask.target_node_ids)
```

预期的任务失败是带**类型化** `ErrorCode` + `RecoveryHint`（B3）的 `FAILED` 更新 ——
绝不抛异常。只有传输/IO 故障才 raise。

## 3. 验证合规

发布前用一致性套件跑一遍 —— 这是「换本体」安全的保障，不是靠赌：

```python
from bodylink import check_executor_adapter
check_executor_adapter(MyRobot())   # 任何契约违反都 raise AssertionError
```

它检查：manifest 格式良好、dispatch 到达终态、node id 回显（B9）、未声明动词被拒
（D3）、`FAILED` 更新带类型化错误（B3）。两个参考体 —— `g1d`（轮式）和 `h1`（双足）——
在 `tests/test_conformance.py` 里通过；把同一参数化测试套到你的本体上。

## 清单

1. 写 manifest（内置 dict 或 `*.yaml`）—— 设 `base_type`、列动词。
2. 继承 `BaseExecutorAdapter`，实现 `_execute()`。
3. 把你的故障映射到类型化 `ErrorCode`（B3）。
4. 通过 `check_executor_adapter()`。
5. 碰硬件前先用 `MockBody(your_manifest)` 干跑计划。
