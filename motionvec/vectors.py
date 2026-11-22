"""屏幕空间运动向量的核心计算。

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
"""

import math

SCREEN_WIDTH = 1000.0
SCREEN_HEIGHT = 1000.0

_W_EPS = 1e-12


class MotionError(Exception):
    """运动向量计算中的非法输入或不可逆变换。"""


def _check_finite(values, what):
    for v in values:
        if not math.isfinite(v):
            raise MotionError("%s 含 NaN/Inf" % what)


def _check_matrix(m, what):
    try:
        rows = [list(row) for row in m]
    except TypeError:
        raise MotionError("%s 不是 4x4 矩阵" % what)
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        raise MotionError("%s 不是 4x4 矩阵" % what)
    for row in rows:
        _check_finite(row, what)
    return rows


def _mat_vec(m, v):
    return [sum(m[i][j] * v[j] for j in range(4)) for i in range(4)]


def _invert4(m):
    """4x4 矩阵求逆（Gauss-Jordan，部分主元）；奇异时抛 MotionError。"""
    n = 4
    aug = [list(m[i]) + [1.0 if i == j else 0.0 for j in range(n)]
           for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) <= _W_EPS:
            raise MotionError("矩阵奇异，不可逆")
        aug[col], aug[piv] = aug[piv], aug[col]
        inv_piv = 1.0 / aug[col][col]
        aug[col] = [x * inv_piv for x in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0.0:
                factor = aug[r][col]
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def project(pos, view, proj):
    """把世界坐标投影到屏幕像素坐标。"""
    _check_finite(pos, "pos")
    view = _check_matrix(view, "view")
    proj = _check_matrix(proj, "proj")
    world = [pos[0], pos[1], pos[2], 1.0]
    view_pos = _mat_vec(view, world)
    clip = _mat_vec(proj, view_pos)
    w = clip[3]
    if not math.isfinite(w) or abs(w) <= _W_EPS:
        raise MotionError("齐次坐标 w 约等于 0，无法做透视除法")
    ndc_x = clip[0] / w
    ndc_y = clip[1] / w
    x_px = (ndc_x + 1.0) * 0.5 * SCREEN_WIDTH
    y_px = (1.0 - ndc_y) * 0.5 * SCREEN_HEIGHT
    depth = -view_pos[2]
    return (x_px, y_px, depth)


def reproject(uv, depth, view, proj):
    """把屏幕像素坐标加深度反投影回世界坐标。"""
    _check_finite(uv, "uv")
    if not math.isfinite(depth) or depth <= 0.0:
        raise MotionError("深度必须为正的有限数")
    view = _check_matrix(view, "view")
    proj = _check_matrix(proj, "proj")
    ndc_x = uv[0] / SCREEN_WIDTH * 2.0 - 1.0
    ndc_y = 1.0 - uv[1] / SCREEN_HEIGHT * 2.0
    # 视图空间点 p = (vx, vy, -depth, 1)，满足 ndc_i = (P[i]·p)/(P[3]·p)，
    # 即 (P[i] - ndc_i * P[3])·p = 0，对 vx / vy 是 2x2 线性方程组。
    vz = -depth
    eqs = []
    for i, ndc in ((0, ndc_x), (1, ndc_y)):
        a = proj[i][0] - ndc * proj[3][0]
        b = proj[i][1] - ndc * proj[3][1]
        c = -((proj[i][2] - ndc * proj[3][2]) * vz
              + (proj[i][3] - ndc * proj[3][3]))
        eqs.append((a, b, c))
    (a1, b1, c1), (a2, b2, c2) = eqs
    det = a1 * b2 - a2 * b1
    if abs(det) <= _W_EPS:
        raise MotionError("投影矩阵奇异，无法反投影")
    vx = (c1 * b2 - c2 * b1) / det
    vy = (a1 * c2 - a2 * c1) / det
    inv_view = _invert4(view)
    world = _mat_vec(inv_view, [vx, vy, vz, 1.0])
    w = world[3]
    if not math.isfinite(w) or abs(w) <= _W_EPS:
        raise MotionError("反投影结果的齐次 w 约等于 0")
    return (world[0] / w, world[1] / w, world[2] / w)


def pixel_motion(pos, cur, prev):
    """同一世界点在当前帧与上一帧相机下的屏幕位移（像素）。"""
    cx, cy, _ = project(pos, cur["view"], cur["proj"])
    px, py, _ = project(pos, prev["view"], prev["proj"])
    return (cx - px, cy - py)


def camera_motion(uv, depth, cur, prev):
    """纯相机运动：静态世界点从上一帧到当前帧的屏幕位移。"""
    world = reproject(uv, depth, cur["view"], cur["proj"])
    px, py, _ = project(world, prev["view"], prev["proj"])
    return (uv[0] - px, uv[1] - py)


def object_motion(pos, cur, prev, prev_pos):
    """物体相对相机的屏幕运动（像素），已减去纯相机运动。"""
    cx, cy, depth = project(pos, cur["view"], cur["proj"])
    px, py, _ = project(prev_pos, prev["view"], prev["proj"])
    cam_dx, cam_dy = camera_motion((cx, cy), depth, cur, prev)
    return ((cx - px) - cam_dx, (cy - py) - cam_dy)


def clamp_vectors(vecs, max_len):
    """按欧氏长度钳制一组二维向量，返回新列表。"""
    if (isinstance(max_len, bool)
            or not isinstance(max_len, (int, float))
            or not math.isfinite(max_len) or max_len <= 0.0):
        raise MotionError("max_len 必须为正的有限数")
    result = []
    for vec in vecs:
        dx, dy = vec
        if not math.isfinite(dx) or not math.isfinite(dy):
            raise MotionError("向量分量含 NaN/Inf")
        length = math.hypot(dx, dy)
        if length > max_len:
            scale = max_len / length
            result.append((dx * scale, dy * scale))
        else:
            result.append((dx, dy))
    return result


def validate(uv, depth, vecs):
    """检查一个像素的运动向量输入，返回问题列表（不抛异常）。"""
    issues = []
    if not math.isfinite(depth) or depth <= 0.0:
        issues.append("depth 必须为正的有限数")
    ux, uy = uv
    if not (math.isfinite(ux) and math.isfinite(uy)):
        issues.append("uv 含 NaN/Inf")
    elif not (0.0 <= ux <= SCREEN_WIDTH and 0.0 <= uy <= SCREEN_HEIGHT):
        issues.append("uv 超出视口")
    for vec in vecs:
        dx, dy = vec
        if not (math.isfinite(dx) and math.isfinite(dy)):
            issues.append("向量分量含 NaN/Inf")
            break
    return issues


def vector_batch(frames, config):
    """批量生成运动向量；任一帧非法时整体失败，不返回部分结果。"""
    max_len = config.get("max_len") if hasattr(config, "get") else None
    if (isinstance(max_len, bool)
            or not isinstance(max_len, (int, float))
            or not math.isfinite(max_len) or max_len <= 0.0):
        raise MotionError("max_len 必须为正的有限数")

    out_frames = []
    for index, f in enumerate(frames):
        cam = f["camera"]
        cur_view = _check_matrix(cam["view"], "view")
        cur_proj = _check_matrix(cam["proj"], "proj")
        prev_view = _check_matrix(cam["prev_view"], "prev_view")
        prev_proj = _check_matrix(cam["prev_proj"], "prev_proj")

        x, y, depth = project(f["pos"], cur_view, cur_proj)
        px, py, _ = project(f["prev_pos"], prev_view, prev_proj)
        vec = (x - px, y - py)

        issues = validate((x, y), depth, [vec])
        if issues:
            raise MotionError("帧 %d 非法: %s" % (index, "; ".join(issues)))

        (clamped,) = clamp_vectors([vec], max_len)
        out_frames.append({
            "index": index,
            "uv": (x, y),
            "depth": depth,
            "vector": clamped,
        })
    return {"count": len(out_frames), "max_len": max_len, "frames": out_frames}
