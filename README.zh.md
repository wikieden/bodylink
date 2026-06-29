> 🌐 [English](README.md) · **中文**

# bodylink

[Chronotope](https://github.com/wikieden/tempomem) 的**执行适配层** —— workspace
第 4 个成员（D5）。大脑（`mindloop`）发布 `ExecutorAdapter` *协议*；bodylink
发布参考*实现*与按机身的适配框架。

> **换机身不换心识。** 每个真机都是一个独立、出树的设备包，实现同一个
> `ExecutorAdapter` —— 仅靠 **Body Profile** + **动词集** 差异化。换机身时大脑
> 零改动（D3）。

## 内容一览

| 组件 | 职责 |
|---|---|
| `MockBody` | 无硬件参考 `ExecutorAdapter` —— 接收 `SubTask`、回带 node id（B9）、上报成功或脚本化类型化失败（B3）。让 L3 大脑无机器人、无网络即可端到端跑通。 |
| `g1d_manifest()` | B10 参考 `CapabilityManifest` —— G1-D 轮式人形（32 DOF、2D 底盘、声明的动词集）。 |

## 安装

```bash
pip install bodylink            # 参考执行器（依赖 mindloop）
pip install bodylink[sim]       # + Genesis/Isaac 物理仿真（预留）
```

## 快速上手

```python
from mindloop import SubTask
from bodylink import MockBody

body = MockBody()                                  # G1-D 参考清单
assert body.capabilities().supports("grasp")
for update in body.dispatch(SubTask(id="s1", verb="grasp", target_node_ids=(12,))):
    print(update.status, update.touched_node_ids)  # RUNNING … SUCCESS，id 回带
```

> **状态：** P0 参考实现。行为树运行时与真机适配器后续落地；本包当前从
> workspace 内目录形态，在发布前毕业为独立仓库。

## 许可证

Apache-2.0 —— 见 [LICENSE](LICENSE)。
