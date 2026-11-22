"""render-motion-vectors 的 15 个验收测试。

所有测试只使用标准库 math 与 pytest。浮点比较容差为 1e-6。
"""

import math

import pytest

from motionvec.vectors import (
    MotionError,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    camera_motion,
    clamp_vectors,
    object_motion,
    pixel_motion,
    project,
    reproject,
    validate,
    vector_batch,
)

HALF_W = SCREEN_WIDTH * 0.5
HALF_H = SCREEN_HEIGHT * 0.5
FOVY_DEG = 60.0
FOCAL = 1.0 / math.tan(math.radians(FOVY_DEG) * 0.5)
NEAR = 0.1
FAR = 100.0
EPS = 1e-6


def perspective():
    """标准 OpenGL 透视矩阵，列向量约定，相机朝 -Z。"""
    return [
        [FOCAL, 0.0, 0.0, 0.0],
        [0.0, FOCAL, 0.0, 0.0],
        [0.0, 0.0, (FAR + NEAR) / (NEAR - FAR), (2.0 * FAR * NEAR) / (NEAR - FAR)],
        [0.0, 0.0, -1.0, 0.0],
    ]


def view_at(x=0.0, y=0.0, z=0.0):
    """相机位于 (x, y, z)、无旋转的视图矩阵。"""
    return [
        [1.0, 0.0, 0.0, -x],
        [0.0, 1.0, 0.0, -y],
        [0.0, 0.0, 1.0, -z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def camera(cur_xyz=(0.0, 0.0, 0.0), prev_xyz=None):
    """构造含四个矩阵的相机字典。"""
    if prev_xyz is None:
        prev_xyz = cur_xyz
    return {
        "view": view_at(*cur_xyz),
        "proj": perspective(),
        "prev_view": view_at(*prev_xyz),
        "prev_proj": perspective(),
    }


def prev_of(cam):
    """把相机字典中的上一帧矩阵取出，组成上一帧相机状态。"""
    return {
        "view": cam["prev_view"],
        "proj": cam["prev_proj"],
        "prev_view": cam["prev_view"],
        "prev_proj": cam["prev_proj"],
    }


def frame(pos, prev_pos, cam):
    return {"pos": pos, "prev_pos": prev_pos, "camera": cam}


def screen_x(world_x, depth, cam_x=0.0):
    return HALF_W + FOCAL * (world_x - cam_x) / depth * HALF_W


def screen_y(world_y, depth, cam_y=0.0):
    return HALF_H - FOCAL * (world_y - cam_y) / depth * HALF_H


def assert_close(actual, expected, eps=EPS):
    assert abs(actual - expected) <= eps, (actual, expected)


# 缺陷 1：投影不除 w，远近错位。
def test_project_applies_perspective_divide():
    cam = camera()
    near = project((1.0, 0.0, -2.0), cam["view"], cam["proj"])
    far = project((1.0, 0.0, -8.0), cam["view"], cam["proj"])
    assert_close(near[0], screen_x(1.0, 2.0))
    assert_close(far[0], screen_x(1.0, 8.0))
    assert near[0] > far[0]
    assert_close(near[2], 2.0)
    assert_close(far[2], 8.0)


# 缺陷 2：重投影误用当前矩阵，相机运动为 0。
def test_camera_motion_uses_previous_camera():
    cam = camera((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    motion = camera_motion((HALF_W, HALF_H), 5.0, cam, prev_of(cam))
    expected = HALF_W - screen_x(0.0, 5.0, cam_x=-1.0)
    assert_close(motion[0], expected)
    assert_close(motion[1], 0.0)
    assert abs(motion[0]) > 1.0


# 缺陷 3：相机运动不区分深度，所有物体被同一全局向量带动。
def test_camera_motion_is_depth_dependent_not_global():
    cam = camera((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    near = camera_motion((HALF_W, HALF_H), 2.0, cam, prev_of(cam))
    far = camera_motion((HALF_W, HALF_H), 10.0, cam, prev_of(cam))
    assert_close(near[0], HALF_W - screen_x(0.0, 2.0, cam_x=-1.0))
    assert_close(far[0], HALF_W - screen_x(0.0, 10.0, cam_x=-1.0))
    assert abs(near[0]) > abs(far[0]) + 1.0


# 缺陷 4：物体运动不减相机运动，动态物体被双重计算。
def test_object_motion_subtracts_camera_motion():
    cam = camera((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    previous_cam = prev_of(cam)

    static = object_motion((0.0, 0.0, -5.0), cam, previous_cam, (0.0, 0.0, -5.0))
    assert_close(static[0], 0.0)
    assert_close(static[1], 0.0)

    moving = object_motion(
        (0.2, 0.0, -5.0), cam, previous_cam, (0.0, 0.0, -5.0)
    )
    expected = FOCAL * 0.2 / 5.0 * HALF_W
    assert_close(moving[0], expected)
    assert_close(moving[1], 0.0)


# 缺陷 5：屏幕空间 y 轴不翻转，上下相反。
def test_project_flips_screen_y_axis():
    cam = camera()
    above = project((0.0, 1.0, -5.0), cam["view"], cam["proj"])
    below = project((0.0, -1.0, -5.0), cam["view"], cam["proj"])
    assert_close(above[1], screen_y(1.0, 5.0))
    assert_close(below[1], screen_y(-1.0, 5.0))
    assert above[1] < HALF_H < below[1]


# 缺陷 6：向量按 UV 而非像素计算，量级差约 1000 倍。
def test_pixel_motion_is_measured_in_pixels():
    cam = camera((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    motion = pixel_motion((0.0, 0.0, -5.0), cam, prev_of(cam))
    expected = HALF_W - screen_x(0.0, 5.0, cam_x=-1.0)
    assert_close(motion[0], expected)
    assert abs(motion[0]) > 100.0


# 缺陷 7：深度为 0 不校验，反投影除零。
def test_zero_depth_is_rejected():
    cam = camera()
    issues = validate((HALF_W, HALF_H), 0.0, [(0.0, 0.0)])
    assert issues
    with pytest.raises(MotionError):
        reproject((HALF_W, HALF_H), 0.0, cam["view"], cam["proj"])
    with pytest.raises(MotionError):
        reproject((HALF_W, HALF_H), -1.0, cam["view"], cam["proj"])


# 缺陷 8：不钳制长度，拖影拉满整屏。
def test_clamp_vectors_shortens_overlong_vectors():
    vecs = [(3.0, 4.0), (0.3, 0.4)]
    clamped = clamp_vectors(vecs, 2.0)
    assert len(clamped) == 2
    assert_close(math.hypot(*clamped[0]), 2.0)
    assert_close(clamped[0][0], 1.2)
    assert_close(clamped[0][1], 1.6)
    assert_close(clamped[1][0], 0.3)
    assert_close(clamped[1][1], 0.4)
    assert vecs == [(3.0, 4.0), (0.3, 0.4)]


# 缺陷 9：批量共用缓冲，帧与帧之间串数据。
def test_vector_batch_frames_do_not_share_buffers():
    cam = camera((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    first = frame((0.2, 0.0, -5.0), (0.0, 0.0, -5.0), cam)
    second = frame((-0.3, 0.0, -5.0), (0.0, 0.0, -5.0), cam)
    config = {"max_len": 1000.0}

    both = vector_batch([first, second], config)
    only_first = vector_batch([first], config)
    only_second = vector_batch([second], config)

    assert both["count"] == 2
    assert len(both["frames"]) == 2
    assert both["frames"][0]["index"] == 0
    assert both["frames"][1]["index"] == 1
    assert_close(
        both["frames"][0]["vector"][0], only_first["frames"][0]["vector"][0]
    )
    assert_close(
        both["frames"][1]["vector"][0], only_second["frames"][0]["vector"][0]
    )
    assert abs(
        both["frames"][0]["vector"][0] - both["frames"][1]["vector"][0]
    ) > 50.0

    bad = frame((float("nan"), 0.0, -5.0), (0.0, 0.0, -5.0), cam)
    with pytest.raises(MotionError):
        vector_batch([first, bad], config)
    after_failure = vector_batch([first], config)
    assert_close(
        after_failure["frames"][0]["vector"][0],
        only_first["frames"][0]["vector"][0],
    )


# 缺陷 10：max_len<=0 不校验，所有向量被静默归零。
def test_non_positive_max_len_is_rejected():
    with pytest.raises(MotionError):
        clamp_vectors([(1.0, 0.0)], -1.0)
    with pytest.raises(MotionError):
        vector_batch([], {"max_len": -2.0})


# 组合 1：相机静止时相机运动在 1e-6 内为 0。
def test_camera_motion_is_zero_when_camera_is_static():
    cam = camera()
    motion = camera_motion((HALF_W, HALF_H), 5.0, cam, prev_of(cam))
    assert abs(motion[0]) <= EPS
    assert abs(motion[1]) <= EPS
    still = pixel_motion((0.0, 0.0, -5.0), cam, prev_of(cam))
    assert abs(still[0]) <= EPS
    assert abs(still[1]) <= EPS


# 组合 2：clamp_vectors 的结果长度不超过 max_len。
def test_clamp_vectors_never_exceeds_max_length():
    vecs = [(100.0, 0.0), (-30.0, 40.0), (0.0, 0.0), (2.0, -3.0)]
    clamped = clamp_vectors(vecs, 10.0)
    assert len(clamped) == len(vecs)
    for vector in clamped:
        assert math.hypot(*vector) <= 10.0 + 1e-9
    assert clamped[2] == (0.0, 0.0)
    assert clamped[3] == (2.0, -3.0)


# 组合 3：空帧返回空结果。
def test_vector_batch_empty_frames_returns_empty():
    result = vector_batch([], {"max_len": 12.5})
    assert result == {"count": 0, "max_len": 12.5, "frames": []}


# 组合 4：max_len=0 抛 MotionError。
def test_zero_max_len_raises_motion_error():
    with pytest.raises(MotionError):
        vector_batch([], {"max_len": 0.0})
    with pytest.raises(MotionError):
        clamp_vectors([], 0.0)


# 组合 5：批量全部成功时保持输入顺序。
def test_vector_batch_preserves_order_when_all_succeed():
    cam = camera((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    frames = [
        frame((0.1, 0.05, -4.0), (0.0, 0.0, -4.0), cam),
        frame((0.0, 0.0, -6.0), (0.0, 0.0, -6.0), cam),
        frame((-0.2, -0.1, -5.0), (0.0, 0.0, -5.0), cam),
    ]
    config = {"max_len": 1000.0}
    batch = vector_batch(frames, config)

    assert batch["count"] == 3
    assert [item["index"] for item in batch["frames"]] == [0, 1, 2]
    for index, item in enumerate(batch["frames"]):
        single = vector_batch([frames[index]], config)["frames"][0]
        assert_close(item["uv"][0], single["uv"][0])
        assert_close(item["uv"][1], single["uv"][1])
        assert_close(item["vector"][0], single["vector"][0])
        assert_close(item["vector"][1], single["vector"][1])
