import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "maps" / "build_map.py"


def make_images(d, names):
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"x")
    return d


def run_dry(images_dir, root):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--images_dir", str(images_dir),
         "--root", str(root), "--dry-run"],
        capture_output=True, text=True,
    )


def test_n_views_3(tmp_path):
    imgs = make_images(tmp_path / "imgs", ["a.jpg", "b.jpeg", "c.png"])
    r = run_dry(imgs, tmp_path / "root")
    assert r.returncode == 0
    assert "--n_views 3" in r.stdout


def test_n_views_8_case_insensitive(tmp_path):
    names = [f"{i}.jpg" for i in range(6)] + ["x.JPG", "y.PNG"]
    imgs = make_images(tmp_path / "imgs", names)
    r = run_dry(imgs, tmp_path / "root")
    assert r.returncode == 0
    assert "--n_views 8" in r.stdout


def test_non_images_not_counted(tmp_path):
    imgs = make_images(tmp_path / "imgs", ["a.jpg", "b.jpg", "notes.txt", "c.gif", "d.npy"])
    (imgs / "sub.jpg").mkdir()
    r = run_dry(imgs, tmp_path / "root")
    assert r.returncode == 0
    assert "--n_views 2" in r.stdout


def test_zero_images_exit_1(tmp_path):
    imgs = make_images(tmp_path / "imgs", ["notes.txt"])
    r = run_dry(imgs, tmp_path / "root")
    assert r.returncode == 1


def test_dry_run_creates_nothing(tmp_path):
    imgs = make_images(tmp_path / "imgs", ["a.jpg", "b.jpg"])
    root = tmp_path / "root"
    r = run_dry(imgs, root)
    assert r.returncode == 0
    assert not root.exists()


def run_dry_default(root):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--dry-run"],
        capture_output=True, text=True,
    )


def test_default_images_dir_is_input_data(tmp_path):
    root = tmp_path / "root"
    make_images(root / "data" / "input_data",["a.jpg", "b.jpg", "c.png", "d.jpeg"])
    r = run_dry_default(root)
    assert r.returncode == 0
    assert "--n_views 4" in r.stdout


def test_default_images_dir_missing_exit_1(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    r = run_dry_default(root)
    assert r.returncode == 1


def docker_lines(tmp_path):
    imgs = make_images(tmp_path / "imgs", ["a.jpg", "b.jpg"])
    r = run_dry(imgs, tmp_path / "root")
    assert r.returncode == 0
    return [l for l in r.stdout.splitlines() if "docker run" in l]


def test_docker_run_sets_weights_only_env(tmp_path):
    lines = docker_lines(tmp_path)
    assert len(lines) == 3
    for l in lines:
        assert "-e TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1" in l


def test_render_has_no_infer_video(tmp_path):
    lines = [l for l in docker_lines(tmp_path) if "./render.py" in l]
    assert len(lines) == 1
    assert "--infer_video" not in lines[0]


def test_init_geo_keeps_infer_video(tmp_path):
    lines = [l for l in docker_lines(tmp_path) if "./init_geo.py" in l]
    assert len(lines) == 1
    assert "--infer_video" in lines[0]
