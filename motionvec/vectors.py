"""屏幕空间运动向量的核心计算（待实现）。

约定
----
* 坐标系为右手系，相机朝向 -Z；``view`` / ``proj`` 均为 4x4 行主序矩阵，
  采用列向量约定 ``v' = M v``。
* 屏幕空间使用像素单位：左上角为 ``(0, 0)``，x 向右、y 向下，视口为
  ``SCREEN_WIDTH x SCREEN_HEIGHT``。所有浮点比较的容差为 ``1e-6``。
* ``depth`` 是相机前方的正距离，即视图空间 ``-z``。
* 相机状态是一个字典；当前帧矩阵为 ``view`` / ``proj``，上一帧矩阵为
  ``prev_view`` / ``prev_proj``。接受两个相机状态的函数从各自的
  ``view`` / ``proj`` 读取当前帧与上一帧，额外的键会被忽略。
* 非法输入统一抛出 :class:`MotionError`。

``motionvec/vectors.py`` 是本题的核心，tests/test_vectors.py 中的 15 个
测试当前全部失败；需要实现下面 8 个函数，契约见各函数 docstring。
"""

SCREEN_WIDTH = 1000.0
SCREEN_HEIGHT = 1000.0


class MotionError(Exception):
    """运动向量计算中的非法输入或不可逆变换。"""


def project(pos, view, proj):
    """把世界坐标投影到屏幕像素坐标。

    参数:
        pos: ``(x, y, z)`` 世界坐标。
        view: 4x4 行主序视图矩阵。
        proj: 4x4 行主序投影矩阵。

    返回:
        ``(x_px, y_px, depth)``。``x_px`` / ``y_px`` 为像素坐标，必须做
        ``w`` 除法并翻转屏幕 y 轴；``depth`` 为相机前方的正距离
        （视图空间 ``-z``）。

    异常:
        MotionError: 输入含 NaN/Inf，或齐次坐标 ``w`` 约等于 0。
    """
    raise NotImplementedError


def reproject(uv, depth, view, proj):
    """把屏幕像素坐标加深度反投影回世界坐标。

    参数:
        uv: ``(x_px, y_px)`` 屏幕像素坐标。
        depth: 相机前方正距离（视图空间 ``-z``）。
        view: 4x4 行主序视图矩阵。
        proj: 4x4 行主序投影矩阵。

    返回:
        ``(x, y, z)`` 世界坐标。

    异常:
        MotionError: 深度非正或含 NaN/Inf、uv 非有限、矩阵奇异。
    """
    raise NotImplementedError


def pixel_motion(pos, cur, prev):
    """同一世界点在当前帧与上一帧相机下的屏幕位移。

    参数:
        pos: ``(x, y, z)`` 世界坐标。
        cur: 当前相机状态（至少含 ``view`` / ``proj``）。
        prev: 上一帧相机状态（至少含 ``view`` / ``proj``）。

    返回:
        ``(dx, dy)``，单位为像素，等于当前帧屏幕坐标减上一帧屏幕坐标。
    """
    raise NotImplementedError


def camera_motion(uv, depth, cur, prev):
    """纯相机运动：静态世界点从上一帧到当前帧的屏幕位移。

    用当前相机把 ``(uv, depth)`` 反投影成世界点，再用上一帧相机投影，
    结果等于当前 uv 减上一帧 uv。该函数用于静态物体；相机完全静止时
    返回值应在 ``1e-6`` 内为 ``(0, 0)``。

    参数:
        uv: 当前帧的屏幕像素坐标。
        depth: 该像素对应的相机前方正距离。
        cur: 当前相机状态（至少含 ``view`` / ``proj``）。
        prev: 上一帧相机状态（至少含 ``view`` / ``proj``）。

    返回:
        ``(dx, dy)`` 像素位移。
    """
    raise NotImplementedError


def object_motion(pos, cur, prev, prev_pos):
    """物体相对相机的屏幕运动，单位为像素。

    先计算总屏幕位移
    ``project(pos, cur) - project(prev_pos, prev)``，再减去当前像素处的
    纯相机运动 :func:`camera_motion`，避免动态物体被双重计算。
    ``pos == prev_pos`` 的静态物体结果应在 ``1e-6`` 内为 ``(0, 0)``。

    参数:
        pos: 当前帧世界坐标。
        cur: 当前相机状态。
        prev: 上一帧相机状态。
        prev_pos: 上一帧世界坐标。

    返回:
        ``(dx, dy)`` 像素位移。
    """
    raise NotImplementedError


def clamp_vectors(vecs, max_len):
    """按欧氏长度钳制一组二维向量，返回新列表。

    长度超过 ``max_len`` 的向量保持方向并缩放到 ``max_len``；未超长的
    向量原样返回；零向量保持为零。输入序列不会被修改。

    参数:
        vecs: 可迭代的 ``(dx, dy)`` 序列。
        max_len: 最大长度，必须为正的有限数（像素）。

    返回:
        与输入等长、同序的 ``[(dx, dy), ...]``。

    异常:
        MotionError: ``max_len <= 0``、非有限，或某个分量非有限。
    """
    raise NotImplementedError


def validate(uv, depth, vecs):
    """检查一个像素的运动向量输入，返回问题列表（不抛异常）。

    检查项：``depth <= 0`` 或非有限；uv 含 NaN/Inf 或超出视口
    ``[0, SCREEN_WIDTH] x [0, SCREEN_HEIGHT]``；向量分量含 NaN/Inf。
    边界像素视为合法。

    参数:
        uv: 屏幕像素坐标。
        depth: 相机前方正距离。
        vecs: 待检查的 ``(dx, dy)`` 序列。

    返回:
        字符串问题列表；全部合法时为空列表 ``[]``。
    """
    raise NotImplementedError


def vector_batch(frames, config):
    """批量生成运动向量；任一帧非法时整体失败，不返回部分结果。

    每个帧字典为 ``{"pos": (x, y, z), "prev_pos": (x, y, z),
    "camera": {...}}``，其中相机字典含 ``view``、``proj``、
    ``prev_view``、``prev_proj``。``config`` 至少含正的 ``max_len``
    （像素）。

    每帧的向量为纯相机运动与物体相对运动之和，即当前帧世界点与上一帧
    世界点在屏幕上的总位移，最后按 ``max_len`` 钳制。各帧使用独立局部
    结果，不共享可变缓冲；计算过程中任一步失败都必须整体回滚，不能
    留下部分结果或被污染的状态。

    参数:
        frames: 帧字典序列，可为空。
        config: ``{"max_len": float}``。

    返回:
        ``{"count": int, "max_len": float, "frames": [
        {"index": i, "uv": (x, y), "depth": d, "vector": (dx, dy)}, ...]}``；
        空输入返回 ``count == 0`` 且 ``frames == []``。

    异常:
        MotionError: ``max_len <= 0`` 或非有限；任一帧的相机/位置非法、
        uv 越界、深度非正、向量非有限。
    """
    raise NotImplementedError
