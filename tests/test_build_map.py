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
