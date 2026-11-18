import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "capture" / "extract_bag.py"
spec = importlib.util.spec_from_file_location("extract_bag", SCRIPT)
eb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eb)


def pack_rows(arr, step):
    """(h, w, c) または (h, w) の配列を、行末に詰めを付けたバイト列にする。"""
    h = arr.shape[0]
    flat = arr.reshape(h, -1)
    rows = []
    for r in range(h):
        b = flat[r].tobytes()
        rows.append(b + b"\xaa" * (step - len(b)))
    return b"".join(rows)


@pytest.mark.parametrize("pad", [0, 5])
def test_decode_bgr8(pad):
    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, size=(4, 6, 3), dtype=np.uint8)
    step = 6 * 3 + pad
    out = eb.decode_color(4, 6, "bgr8", step, pack_rows(img, step))
    assert out.shape == (4, 6, 3)
    assert np.array_equal(out, img)


@pytest.mark.parametrize("pad", [0, 7])
def test_decode_rgb8_gives_bgr(pad):
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, size=(3, 5, 3), dtype=np.uint8)
    step = 5 * 3 + pad
    out = eb.decode_color(3, 5, "rgb8", step, pack_rows(img, step))
    assert np.array_equal(out, img[:, :, ::-1])


@pytest.mark.parametrize("pad", [0, 6])
def test_decode_depth_16uc1_keeps_values(pad):
    rng = np.random.default_rng(2)
    img = rng.integers(0, 65536, size=(4, 5), dtype=np.uint16)
    step = 5 * 2 + pad
    out = eb.decode_depth(4, 5, "16UC1", step, pack_rows(img.astype("<u2"), step))
    assert out.dtype == np.uint16
    assert np.array_equal(out, img)


def test_unsupported_encodings_raise():
    with pytest.raises(ValueError):
        eb.decode_color(1, 1, "mono8", 1, b"\x00")
    with pytest.raises(ValueError):
        eb.decode_depth(1, 1, "32FC1", 4, b"\x00" * 4)


def test_nearest_index_within_and_over_20ms():
    stamps = [0, 33_000_000, 66_000_000]
    k, dt = eb.nearest_index(stamps, 40_000_000, eb.DEPTH_MAX_DT_NS)
    assert (k, dt) == (1, 7_000_000)
    k, dt = eb.nearest_index(stamps, 20_000_000, eb.DEPTH_MAX_DT_NS)
    assert k == 1  # 13 ms
    k, dt = eb.nearest_index(stamps, 53_000_000 + 40_000_000, eb.DEPTH_MAX_DT_NS)
    assert (k, dt) == (None, None)  # 27 ms 超
    k, _ = eb.nearest_index(stamps, 50_000_000)  # 上限なし
    assert k == 1 or k == 2
    assert eb.nearest_index([], 5) == (None, None)


def test_camera_info_to_dict():
    msg = SimpleNamespace(
        width=640, height=480, k=[float(i) for i in range(9)], d=[0.1, 0.2],
        distortion_model="plumb_bob", header=SimpleNamespace(frame_id="cam"))
    d = eb.camera_info_to_dict(msg)
    assert d["k"] == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    assert d["width"] == 640 and d["height"] == 480
    assert d["d"] == [0.1, 0.2]
    assert d["distortion_model"] == "plumb_bob" and d["frame_id"] == "cam"


def test_make_frame_row_with_joints():
    row = eb.make_frame_row(3, 123, "color/frame_000003.jpg", "depth/frame_000003.png",
                            4_000_000, ["j1", "j2"], [0.5, 1.0])
    assert row == [3, 123, "color/frame_000003.jpg", "depth/frame_000003.png",
                   "4.000", "j1;j2", "0.5;1.0"]
    assert len(row) == len(eb.CSV_COLUMNS)


def test_make_frame_row_without_joints_or_depth():
    row = eb.make_frame_row(0, 9, "color/frame_000000.jpg", "", None, [], [])
    assert row == [0, 9, "color/frame_000000.jpg", "", "", "", ""]


def test_depth_plan_keeps_every_index_sharing_one_depth():
    # 深度の位置 1 が index 1 と 2 の両方に選ばれ、index 3 は深度なし
    plan = eb.build_depth_plan([0, 1, 1, None, 2])
    assert plan == {0: [0], 1: [1, 2], 2: [4]}


def test_depth_plan_when_a_depth_frame_is_dropped():
    depth_stamps = [0, 33_000_000, 99_000_000]  # 66 ms の深度が欠けた
    color_stamps = [0, 33_000_000, 66_000_000, 99_000_000]
    positions = []
    for t in color_stamps:
        k, _ = eb.nearest_index(depth_stamps, t, eb.DEPTH_MAX_DT_NS)
        positions.append(k)
    plan = eb.build_depth_plan(positions)
    covered = sorted(i for v in plan.values() for i in v)
    assert covered == [i for i, p in enumerate(positions) if p is not None]
