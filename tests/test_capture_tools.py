import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "capture" / "record.sh"


def text():
    return SCRIPT.read_text(encoding="utf-8")


def test_records_depth_color_info_and_joint_states():
    t = text()
    assert re.search(r"\$PREFIX/aligned_depth_to_color/image_raw", t)
    assert re.search(r"\$PREFIX/color/image_raw", t)
    assert re.search(r"\$PREFIX/color/camera_info", t)
    assert re.search(r"^\s*/joint_states", t, re.M)


def test_default_prefix():
    assert 'PREFIX="/camera/camera"' in text()


def test_does_not_overwrite_existing_bag():
    t = text()
    assert re.search(r'if \[ -e "\$OUT" \]', t)
    assert 'OUT="$ROOT/data/captures/$NAME/bag"' in t
    assert re.search(r"ros2 bag record -o \"\$OUT\"", t)


def test_checks_color_topic_and_warns_on_missing_joint_states():
    t = text()
    assert "ros2 topic list" in t
    assert "カメラのノードが動いていない、または prefix が違う" in t
    assert "警告: /joint_states がない" in t
