import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "robot" / "export_urdf_assets.py"

URDF = """<?xml version="1.0"?>
<!-- generated from /tmp/dummy/file.xacro -->
<robot name="dummy">
  <!-- link comment -->
  <link name="base">
    <visual><geometry><mesh filename="package://dummy_pkg/meshes/a.stl"/></geometry></visual>
  </link>
</robot>
"""


def make_pkg(tmp_path, with_mesh=True):
    pkg = tmp_path / "pkg"
    (pkg / "meshes").mkdir(parents=True)
    if with_mesh:
        (pkg / "meshes" / "a.stl").write_bytes(b"A")
    (pkg / "meshes" / "unused.stl").write_bytes(b"U")
    urdf = tmp_path / "in.urdf"
    urdf.write_text(URDF, encoding="utf-8")
    return pkg, urdf


def run(pkg, urdf, out):
    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--urdf", str(urdf),
            "--package_name", "dummy_pkg",
            "--package_dir", str(pkg),
            "--out_dir", str(out),
            "--out_name", "robot.urdf",
        ],
        capture_output=True,
        text=True,
    )


def test_copies_only_referenced_meshes_and_writes_urdf(tmp_path):
    pkg, urdf = make_pkg(tmp_path)
    out = tmp_path / "out"
    r = run(pkg, urdf, out)
    assert r.returncode == 0
    assert (out / "dummy_pkg" / "meshes" / "a.stl").read_bytes() == b"A"
    assert not (out / "dummy_pkg" / "meshes" / "unused.stl").exists()
    text = (out / "robot.urdf").read_text(encoding="utf-8")
    assert "package://dummy_pkg/meshes/a.stl" in text


def test_output_urdf_has_no_comments(tmp_path):
    pkg, urdf = make_pkg(tmp_path)
    out = tmp_path / "out"
    assert run(pkg, urdf, out).returncode == 0
    text = (out / "robot.urdf").read_text(encoding="utf-8")
    assert "<!--" not in text
    assert "/tmp/dummy" not in text


def test_missing_mesh_exits_1_and_writes_nothing(tmp_path):
    pkg, urdf = make_pkg(tmp_path, with_mesh=False)
    out = tmp_path / "out"
    r = run(pkg, urdf, out)
    assert r.returncode == 1
    assert not out.exists()
