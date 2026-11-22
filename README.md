# render-motion-vectors

## 题面

接入运动模糊后，静止物体也被拉出长影、镜头转动反而没糊：投影矩阵没有做 w 除法，远近物体在屏幕上的位置整体错位；重投影误用了当前帧矩阵而不是上一帧矩阵，纯相机运动被算成 0；相机运动与物体运动没有区分，静态物体也被加上运动向量；物体运动没有减去相机运动，动态物体被双重计算；屏幕空间 y 轴没有翻转，运动方向上下相反；向量本应以像素为单位却按 UV 计算，量级差了约 1000 倍；深度为 0 时没有校验，反投影直接除零；向量长度没有按 max_len 钳制，拖影被拉满整屏；批量生成时各帧共用同一块缓冲，帧与帧之间互相串数据；max_len<=0 没有校验，所有向量被静默归零。motionvec/vectors.py 是核心，tests/test_vectors.py 15个红。要修的是：上述 10 个缺陷，全部集中在 motionvec/vectors.py，不要修改 tests/test_vectors.py。

## 运行方式

要求 Python 3 和 pytest，在仓库根目录执行：

```powershell
python -m pytest tests -q
```

初始状态的输出末尾为 `15 failed`，其后只有耗时，例如：

```text
15 failed in 0.08s
```

耗时随机器变化，但结果必须是 `15 failed`，且不能出现 collection error、import error 或 syntax error。完成 `motionvec/vectors.py` 中的 8 个函数后，应变为 `15 passed`。测试只用标准库 `math` 与 pytest，离线运行，不使用随机数。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 图形渲染 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 目录结构

```text
render-motion-vectors/
├── README.md
├── conftest.py
├── .gitignore
├── motionvec/
│   ├── __init__.py
│   └── vectors.py
└── tests/
    └── test_vectors.py
```

`motionvec/vectors.py` 中的 8 个函数目前全部 `raise NotImplementedError`：

| 函数 | 职责 |
| --- | --- |
| `project` | 世界坐标到屏幕像素，含 w 除法与 y 轴翻转 |
| `reproject` | 屏幕像素加深度反投影回世界 |
| `pixel_motion` | 当前帧与上一帧的屏幕差（像素） |
| `camera_motion` | 静态物体对应的纯相机运动 |
| `object_motion` | 总运动减去相机运动后的物体相对运动 |
| `clamp_vectors` | 按欧氏长度钳制向量 |
| `validate` | 返回深度、NaN、越界等问题列表 |
| `vector_batch` | 批量生成；任一帧非法时整体回滚 |

矩阵均为 4x4 行主序，采用列向量约定；屏幕视口为 1000x1000 像素，左上角为 `(0, 0)`，y 轴向下；深度是相机前方的正距离；所有浮点比较容差为 `1e-6`，非法输入抛出 `MotionError`。

## 约束

- `tests/test_vectors.py` 不可修改。它包含 15 条验收测试：10 个缺陷各 1 条，另加 5 条组合测试（相机静止时相机运动为 0、钳制长度不超过 `max_len`、空帧返回空、`max_len=0` 抛 `MotionError`、批量成功时保持顺序）。
- 只使用标准库 `math` 和 pytest；离线、无随机。
- 不要修改测试来迁就实现；修复应全部落在 `motionvec/vectors.py`。
