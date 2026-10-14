import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "maps" / "import_instantsplat.py"


def make_dummy(root, tag="a", n_views=3, iteration=1000):
    out = root / "isplat_out"
    (out / "point_cloud" / f"iteration_{iteration}").mkdir(parents=True, exist_ok=True)
    (out / "pose" / f"ours_{iteration}").mkdir(parents=True, exist_ok=True)
    (out / "point_cloud" / f"iteration_{iteration}" / "point_cloud.ply").write_bytes(b"ply-" + tag.encode())
    (out / "cameras.json").write_text(f'{{"tag": "{tag}"}}')
    (out / "cfg_args").write_text(f"cfg-{tag}")
    (out / "pose" / f"ours_{iteration}" / "pose_optimized.npy").write_bytes(b"npy-" + tag.encode())
    images = root / "imgs"
    images.mkdir(exist_ok=True)
    for i in range(n_views):
        (images / f"im{i}.jpg").write_bytes(f"img{i}-{tag}".encode())
    return out, images


def run(root, out, images, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--output_dir", str(out),
         "--images_dir", str(images), "--name", "m", *extra],
        capture_output=True, text=True,
    )


def registry(root):
    return json.loads((root / "data/maps/maps.json").read_text())


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted((root / "data/maps").rglob("*")) if p.is_file()
    }


def test_copy_and_register(tmp_path):
    out, images = make_dummy(tmp_path)
    r = run(tmp_path, out, images)
    assert r.returncode == 0, r.stderr
    entry = registry(tmp_path)["maps"][0]
    assert entry["name"] == "m"
    assert entry["n_views"] == 3
    assert entry["iteration"] == 1000
    assert entry["frame"] == "unaligned"
    assert entry["source"] == "isplat_out"
    raw = tmp_path / "data/maps/m/raw"
    for rel in ["point_cloud.ply", "cameras.json", "cfg_args", "pose_optimized.npy",
                "images/im0.jpg", "images/im1.jpg", "images/im2.jpg"]:
        assert rel in entry["files"]
        assert (raw / rel).is_file()


def test_sha256_matches(tmp_path):
    out, images = make_dummy(tmp_path)
    assert run(tmp_path, out, images).returncode == 0
    entry = registry(tmp_path)["maps"][0]
    raw = tmp_path / "data/maps/m/raw"
    for rel, digest in entry["files"].items():
        assert hashlib.sha256((raw / rel).read_bytes()).hexdigest() == digest


def test_second_run_without_replace_fails(tmp_path):
    out, images = make_dummy(tmp_path)
    assert run(tmp_path, out, images).returncode == 0
    before = snapshot(tmp_path)
    make_dummy(tmp_path, tag="b")
    r = run(tmp_path, out, images)
    assert r.returncode == 1
    assert snapshot(tmp_path) == before


def test_replace_moves_previous(tmp_path):
    out, images = make_dummy(tmp_path, tag="a")
    assert run(tmp_path, out, images).returncode == 0
    old_sha = registry(tmp_path)["maps"][0]["files"]["point_cloud.ply"]
    make_dummy(tmp_path, tag="b")
    r = run(tmp_path, out, images, "--replace")
    assert r.returncode == 0, r.stderr
    maps = registry(tmp_path)["maps"]
    assert len(maps) == 1
    assert maps[0]["files"]["point_cloud.ply"] != old_sha
    assert maps[0]["frame"] == "unaligned"
    base = tmp_path / "data/maps/m"
    assert (base / "raw_prev/point_cloud.ply").read_bytes() == b"ply-a"
    assert (base / "raw/point_cloud.ply").read_bytes() == b"ply-b"
