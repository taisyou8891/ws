from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUBMODULES = [
    "3DGS-Digital-Twin",
    "RGBD-3DGS-SLAM",
    "librealsense",
    "realsense-ros2-docker",
    "segment-anything",
]


def test_unity_project_version_exists():
    assert (ROOT / "unity/DigitalTwin/ProjectSettings/ProjectVersion.txt").is_file()


def test_gitignore_entries():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert "Library/" in lines
    assert "*.ply" in lines


def test_gitmodules_paths():
    text = (ROOT / ".gitmodules").read_text()
    for path in SUBMODULES:
        assert f"path = {path}" in text
