> 🌐 [English](../en/multi-model-adaptation-design.md) · **中文**

# 设计 —— 多机型机器人适配框架（D3）

**状态：** 已实现（2026-06-28）；本文为规范性设计依据。
**范围：** `bodylink` 如何让 Chronotope 大脑（`mindloop`）驱动**多种机型** —— 当下是
双足与轮式人形，未来更多本体类别 —— 且**大脑零改动**。配套 how-to：
[adding-a-robot-model.md](adding-a-robot-model.md)。
**决策脉络：** D3（开放词汇动词 + 两层 `CapabilityManifest`）、B8（大脑从不碰关节/底盘
几何）、B9（node id 过接缝）、B3（类型化错误）、B10（G1-D 参考体）、D5（MockBody / sim）。

---

## 1. 目标与非目标

**目标**

- 加机型是**声明式**的 —— 一份 manifest + 一个薄 adapter，绝不改大脑。
- 一个大脑用同一批计划驱动**双足与轮式人形**；只在本体真正不同处（动词集）才有差异。
- 「换本体、留大脑」是**被验证**的、非口头承诺 —— 每个本体都得过契约套件。
- 核心保持**轻依赖**（stdlib + numpy）；重/可选项（YAML、sim）放 extra 后面。

**非目标（本文）**

- 运动控制、IK、全身控制、步态 —— 在设备包里、**L2 以下**，大脑看不见（B8）。
- 计划的安全强制 —— 那是 **Phylax（P3）**、独立一层；本文只**携带**本体/技能声明的
  `safety` 标注。
- 隐空间 / VLA 动作接口 —— 当前接缝是**符号动词 + node id**（见
  `docs/en/research/l3-l2-fusion-roadmap.md`）；隐空间接缝是未来的**增量**选项、非替代。

---

## 2. 问题

人形机队是异构的：Unitree G1-D（轮式底盘）、Unitree H1（双足）、Fourier GR-1（双足、
灵巧手）、固定臂、未来四足。朴素集成会为每个机器人重碰规划器 —— 动词枚举、能力 `if`、
逐机器人分支 —— 大脑烂成一个对硬件的 switch。过了几台就不可扩展，每个新机器人都成了
大脑团队的项目。

**关键观察：** 在 S2 规划器眼里，这些本体真正变化的东西小而有界 —— **支持哪些技能动词**。
动词怎么实现（腿/轮/履带）是 L2 以下的控制问题。所以大脑应只依赖一个**声明的动词集**，
机型的其它一切都应是**大脑从不分支的数据**。

---

## 3. 设计原则

1. **机型即数据。** 机器人对大脑由 `CapabilityManifest` 定义、非代码。新机型 ⇒ 新 manifest。
2. **运动在 L2 以下（B8）。** 大脑规划 `navigate target`；本体决定腿/轮。`base_type` 是
   **大脑不分支**的元数据。
3. **能力门控规划（D3）。** 规划器/技能卡只能出 manifest 声明的动词；未声明的在派发前丢弃。
4. **闭合审计链（B9）。** 每个 `SubTask` 携带场景图 node id；本体在每条 `StatusUpdate`
   回显。记忆 → 执行器 → 记忆 跨任何本体可追溯。
5. **类型化故障（B3）。** 失败是带类型 `ErrorCode` + `RecoveryHint` 的 `FAILED` 更新，
   绝非自由文本或异常（只有传输/IO 才 raise）。
6. **验证合规。** 一个本体「兼容」当且仅当它过一致性套件 —— 兼容是测试、不是承诺。

---

## 4. 架构

```
        ┌──────────── mindloop (大脑, S2) —— 跨本体不变 ────────────┐
        │   IntentRouter → Planner / SkillCard → compile_commands → SubTask[]            │
        └───────────────────────────────────┬───────────────────────────────────────────┘
                                             │  ExecutorAdapter 接缝 (D1)
                                             │  • dispatch(SubTask) → Iterator[StatusUpdate]
                                             │  • capabilities() → CapabilityManifest
        ┌────────────────────────────────────┼────────────────────────────────────────────┐
        │                     bodylink —— 适配框架                                          │
        │                                                                                   │
        │   manifest 目录              BaseExecutorAdapter SDK        一致性套件             │
        │   load_manifest(name|path)  ├ 动词 gate (D3)               check_executor_adapter │
        │   ├ 内置: g1d, h1           ├ RUNNING→终态流               ├ manifest 良构         │
        │   ├ manifest_from_dict      ├ node-id 回显 (B9)           ├ dispatch→终态          │
        │   └ 厂商 *.yaml (extra)     └ _execute()  ◀── 设备填       ├ B9 回显 / D3 / B3      │
        └────────────────────────────────────┬────────────────────────────────────────────┘
                                             │  继承 + manifest
        ┌──────────────┬──────────────┬───────┴───────┬──────────────────┬─────────────────┐
        ▼              ▼              ▼               ▼                  ▼                 ▼
   MockBody(g1d)  MockBody(h1)   UnitreeG1D     UnitreeH1 (双足)     FourierGR1        你的机器人
   (开发/测试)    (开发/测试)    (厂商包)       (厂商包)            (厂商 *.yaml)     (厂商包)
```

三个组件，每个都是现有 D1 接缝之上的薄层：

| 组件 | 文件 | 职责 |
|---|---|---|
| **manifest 目录** | `manifest.py` | 按内置名或厂商 YAML 解析机型的 `CapabilityManifest` |
| **adapter SDK** | `adapter.py` | `BaseExecutorAdapter`：每个本体共享的样板；设备填 `_execute()` |
| **一致性套件** | `conformance.py` | `check_executor_adapter()`：证明一个本体守接缝 |

---

## 5. 两层 `CapabilityManifest`（机型即数据）

定义在 `mindloop.execute`；大脑拥有契约、本体填充。

- **Body Profile 层**（`BodyProfile`）—— 硬件身份：`profile_id`、`display_name`、
  `dof`、`base_type`（`wheeled` / `legged` / `fixed`）、可选 `joints` / `sensors` /
  `gripper`。**面向执行器**：大脑*不*读 joints/sensors/gripper（B8）—— 它们只为设备层
  与内省随行。
- **动词层**（`VerbSpec`）—— 规划器读的部分：`name`、`params`（affordance 级参数键，如
  `target`、`program`）、家电动词的 `appliance_types`。这是 manifest 中**唯一**改变大脑
  规划内容的部分。

机型要么写成 stdlib dict（`manifest._BUILTIN_PROFILES`，内置路径、零依赖），要么写成外部
YAML（`manifests/_TEMPLATE.yaml` → `load_manifest("path.yaml")`，惰性 PyYAML 在
`manifests` extra 后）。

---

## 6. 机型间变什么 —— 及其落点

| 差异 | 落在 | 大脑分支? |
|---|---|---|
| 双足 / 轮式 / 固定 | `BodyProfile.base_type` | **否** —— 仅元数据 |
| DOF、关节、夹爪运动学、传感器 | `BodyProfile.joints/gripper/sensors` | **否** —— L2 以下 |
| 支持的技能、其参数、可驱动家电 | `VerbSpec`（动词层） | **是** —— D3 gate |
| 动词如何物理实现 | 设备 adapter 的 `_execute()` | **否** |
| 可恢复故障模式 | 类型化 `ErrorCode` + `RecoveryHint`（B3） | 仅重规划时（P4） |

**实例 —— 双足 vs 轮式。** `g1d`（轮式）和 `h1`（双足）共享操作/家电动词。`h1` 额外声明
`climb_stair` —— 轮式底盘无法兑现的能力。出 `climb_stair` 的技能卡或规划器在 `h1` 上运行、
在 `g1d` 上被 D3 gate **丢弃**，无需改大脑、无需逐机器人条件。两本体在规划层**唯一**的
不对称就是那一个动词。

---

## 7. Adapter SDK —— `BaseExecutorAdapter`

设备包继承它、**只**实现 `_execute(subtask) → StatusUpdate`。基类一次性提供每个本体否则都要
重写（且重复踩坑）的契约：

- **动词 gate（D3）：** 拒绝 manifest 未声明动词的 `SubTask`（`UnsupportedVerbError`）——
  规划器 bug 永不应触达硬件。
- **流形状：** 先 yield `RUNNING`、再终态更新 —— 对齐本体团队的 `/l2/task_status` topic。
- **node-id 回显（B9）：** 用 subtask 的 ids 重新盖章终态更新的 `touched_node_ids`，使子类
  *无法*意外打断审计链。

`_execute` 是唯一本体特定代码：把 `(verb, params, node_ids)` 映射到机器人 SDK、报终态。
`MockBody` 本身就是子类（dogfood），参考体与真机共用完全相同的骨架。

---

## 8. 一致性套件 —— 兼容是测试

`check_executor_adapter(adapter)` 把任何 `ExecutorAdapter` 过一遍接缝契约、首个违反即 raise：

1. `capabilities()` 返回良构两层 manifest（≥1 动词、已知 `base_type`）。
2. 声明动词的 `dispatch()` 到达**终态**。
3. 终态更新**回显探针 node id**（B9）。
4. **未声明动词被拒**（D3）—— 不静默执行。
5. `FAILED` 终态带**类型化** `ErrorCode`（B3）。

两参考体（`g1d`、`h1`）在 `tests/test_conformance.py` 里参数化过它。厂商在自己的测试套件
import 同一函数 —— 于是「换本体、留大脑」按本体持续验证、不是靠赌。这是机队增长安全的关键：
不合规本体在 CI 挂掉、而非静默误驱。

---

## 9. 扩展到 N 个机型

- **目录、非代码。** 内置在一个 dict（`_BUILTIN_PROFILES`）；厂商发一份 YAML。
  `list_profiles()` 列内置。加第 10 个机型和第 2 个一样省力。
- **能力驱动规划，已就位。** 因为规划器和技能卡按 `manifest.verb_names()` 门控（D3），
  更强或更弱的本体无需新规划代码 —— 强本体多拿动词；弱本体多余动词被丢。（技能卡 P2 已经
  演练这个丢弃。）
- **无硬件干跑任意机型。** `MockBody(load_manifest("h1"))` 确定性执行任意机型计划 —— 新机型
  计划在机器人存在前就可测。
- **厂商隔离。** 每个真机是依赖 `bodylink` + `mindloop` 的树外包；工作区永不长出硬件依赖。

---

## 10. 版本与兼容

- **动词词汇是兼容面。** 大脑与本体在动词*名 + 参数键*上达成一致。加动词向后兼容（旧本体
  不声明、gate 丢弃）。改名/删动词是破坏性 —— 把共享动词词汇当作版本化契约（写 changelog）。
- **`SubTask` 字段是增量的。** 新可选字段（P1 加了
  `skill`/`preconditions`/`effects`/`timeout_s`）默认构造，旧本体照常工作 —— 读自己懂的字段。
- **manifest schema** 暂无显式版本；若 `BodyProfile`/`VerbSpec` 形状变，加 `schema_version`
  （对齐技能卡 K2 预留）。

---

## 11. 安全 —— untrusted 厂商 manifest

manifest（和社区技能卡）可带 `safety` 标注 + `provenance`。untrusted 来源的 manifest 是
**数据、非权威**：框架加载它，但采信 untrusted 未签名来源带 `safety` 的能力由 **Phylax
（P3）** gate —— 签名/审核后本体或卡的 `safety:` 主张才被信任。`load_manifest(path)` 无网络
IO、无代码执行（YAML 走 `safe_load`），所以加载 manifest 无副作用；信任决策推迟到策略层、
不在加载器。

---

## 12. 测试策略

- **逐本体一致性**（`check_executor_adapter`）—— 契约，对每个本体跑（含参考与厂商）。
- **无网络** —— 内置是 stdlib dict；测试永不需 PyYAML 或机器人。厂商 YAML 路径用
  `importorskip("yaml")`。
- **跨机型端到端** —— `MockBody(manifest)` 对每个机型跑真实大脑计划（及 P2 技能卡）；双足 H1
  和轮式 G1-D 都执行同一批洗衣/烹饪卡。

---

## 13. 路线图

| 状态 | 项 |
|---|---|
| ✅ 已完成 | manifest 目录、`BaseExecutorAdapter`、一致性套件、覆盖三种 base_type 的内置（g1d 轮式、h1+gr1 双足、arm6 固定）、厂商 YAML 路径、how-to 指南、**`SimDeviceAdapter`**（带 transport seam 的真实流式参考 adapter，越过 `MockBody`）、**多机型 demo**（一个大脑 + P2 洗衣卡驱动所有本体；g1d/h1/gr1 同一计划，arm6 经 D3 降级）|
| ✅ 已完成 | **物理仿真 backend**（`bodylink.sim`，`sim` extra）—— `MockSimBackend` + `GenesisSimBackend`（真 Genesis 场景，镜像 B2R `GenesisL1`）；`make_sim_backend("mock"\|"genesis")`。`examples/genesis_demo.py` 用真 Genesis 物理跑 H1 + 洗衣卡，**在 Linux RTX PRO 6000 主机和 macOS Apple Silicon 均验证通过** |
| 接下来 | 真正的**硬件** adapter —— `backend` 驱动真机（HTTP/ROS）的设备包，非 sim；并深化粗粒度 sim（逐机器人 IK / MJCF G1 关键帧，如 B2R）。`SimDeviceAdapter` 是参考*形态*、不是驱动 |
| 后续 | 更丰富 `VerbSpec`（类型化参数 schema、范围、单位）；能力*协商*（本体声明上限，规划器尊重载荷/可达）；更多 `base_type`（四足、双臂固定）；`[sim]` 后的 sim adapter（D5） |
| 待定 | `base_type` 是否该影响规划（如台阶感知导航），还是严格元数据？（当前答案：元数据；有证据再议） |

---

## 14. 备选方案权衡

- **逐机器人规划分支 / 动词枚举。** 否决 —— 把大脑变成硬件 switch；每个机器人都成大脑团队
  改动。（本框架就为避免这个而存在。）
- **一个含全机器人动词 + 运行时能力标志的巨型 manifest。** 否决 —— 耦合所有本体，且规划器
  仍须逐机器人过滤；逐机型 manifest + D3 gate 更简单、隔离厂商。
- **ROS 式 action server 当接缝。** 正交 —— 厂商 adapter 内部可用 ROS；面向大脑的接缝保持
  类型化 `ExecutorAdapter`，使大脑无 ROS 依赖。
- **隐空间 / VLA 动作接口替代符号动词。** 推迟、增量（见 l3-l2-fusion-roadmap）。符号接缝是
  当下让能力门控与审计链（B9）可行的关键；隐空间接缝将是并列的 adapter 类型、非替代。
