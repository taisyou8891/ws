import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" / "gsicp"

spec = importlib.util.spec_from_file_location("captures_to_tum", TOOLS / "captures_to_tum.py")
c2t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c2t)


def _text(name):
    return (TOOLS / name).read_text(encoding="utf-8")


def test_dockerfile_pins_versions():
    text = _text("Dockerfile")
    assert "nvidia/cuda:12.8.1-devel-ubuntu24.04" in text
    assert "5f996a872a979406b270fe0ee3b0a8f25c5e9ae3" in text
    assert "torch==2.7.1" in text
    assert "torchvision==0.22.1" in text
    assert "cu128" in text
    assert "TORCH_CUDA_ARCH_LIST=12.0" in text


def test_run_script_uses_gpus_all_and_mounts():
    text = _text("run.sh")
    assert "--gpus all" in text
    assert ":/data" in text
    assert ":/captures:ro" in text


def test_build_script_builds_local_image():
    assert "gsicp:local" in _text("build.sh")


def test_download_script_targets_fr1_desk():
    assert "freiburg1_desk" in _text("download_tum.sh")


def test_depth_mm_to_tum():
    out = c2t.depth_mm_to_tum(np.array([0, 1000, 2000, 13108], dtype=np.uint16))
    assert out.dtype == np.uint16
    # TUM は 5000 で割ると m: 1000 mm = 1 m = 5000
    assert out.tolist() == [0, 5000, 10000, 65535]


def test_stamp_text():
    assert c2t.stamp_text(1_795_000_704_796_889_893) == "1795000704.796889"


def _make_capture(root):
    (root / "color").mkdir(parents=True)
    (root / "depth").mkdir()
    rows = ["index,stamp_ns,color,depth,depth_dt_ms,joint_names,joint_positions"]
    for i in range(3):
        Image.fromarray(np.full((4, 6, 3), 10 * i, dtype=np.uint8)).save(root / "color" / f"frame_{i:06d}.jpg")
        depth = ""
        if i != 0:  # 0 番目は深度なし
            Image.fromarray(np.full((4, 6), 1000 * i, dtype=np.uint16)).save(root / "depth" / f"frame_{i:06d}.png")
            depth = f"depth/frame_{i:06d}.png"
        rows.append(f"{i},{1_000_000_000 + i * 33_333_333},color/frame_{i:06d}.jpg,{depth},,,")
    (root / "frames.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    info = {"width": 6, "height": 4, "k": [[500.0, 0, 3.5], [0, 501.0, 2.5], [0, 0, 1]], "d": [0] * 5}
    (root / "camera_info.json").write_text(json.dumps(info), encoding="utf-8")


def test_convert_synthetic(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    _make_capture(src)
    n = c2t.convert(src, dst)
    assert n == 2  # 深度のない行を除く
    assert sorted(p.name for p in (dst / "rgb").iterdir()) == ["000001.jpg", "000002.jpg"]
    assert sorted(p.name for p in (dst / "depth").iterdir()) == ["000001.png", "000002.png"]
    d1 = np.array(Image.open(dst / "depth" / "000001.png"))
    assert d1.dtype == np.uint16 and int(d1[0, 0]) == 5000  # 1000 mm
    assert int(np.array(Image.open(dst / "depth" / "000002.png"))[0, 0]) == 10000  # 2000 mm

    def data_lines(name):
        return [ln for ln in (dst / name).read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]

    assert data_lines("rgb.txt") == ["1.033333 rgb/000001.jpg", "1.066666 rgb/000002.jpg"]
    assert data_lines("depth.txt") == ["1.033333 depth/000001.png", "1.066666 depth/000002.png"]
    assert data_lines("associations.txt")[0] == "1.033333 rgb/000001.jpg 1.033333 depth/000001.png"
    assert len(data_lines("groundtruth.txt")) == 2
    # 上流の読み込みと同じく、空白区切りで読め、# の行を飛ばせる
    arr = np.loadtxt(dst / "rgb.txt", delimiter=" ", dtype=str)
    assert arr.shape == (2, 2)
    cfg = (dst / "camera.txt").read_text(encoding="utf-8").splitlines()
    assert cfg[0] == "## camera parameters"
    assert cfg[1] == "W H fx fy cx cy depth_scale depth_trunc dataset_type"
    assert cfg[2] == "6 4 500.0 501.0 3.5 2.5 5000.0 3.0 tum"


def test_convert_refuses_existing_output(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    _make_capture(src)
    c2t.convert(src, dst)
    with pytest.raises(FileExistsError):
        c2t.convert(src, dst)
    assert c2t.convert(src, dst, replace=True) == 2
