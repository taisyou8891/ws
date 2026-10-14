import xml.etree.ElementTree as ET
from pathlib import Path

ROBOT_DIR = Path(__file__).resolve().parent.parent / "unity" / "DigitalTwin" / "Assets" / "Robot" / "xarm6"
URDF = ROBOT_DIR / "xarm6.urdf"
PREFIX = "package://xarm_description/"


def load():
    return ET.parse(URDF).getroot()


def test_joint1_to_joint6_are_revolute():
    # robot 直下の joint だけを見る（ros2_control・transmission の中の joint は除く）
    joints = {j.get("name"): j.get("type") for j in load().findall("joint")}
    for i in range(1, 7):
        assert joints.get("joint%d" % i) == "revolute"


def test_gripper_drive_joint_exists():
    names = [j.get("name") for j in load().findall("joint")]
    assert "drive_joint" in names


def test_referenced_meshes_exist_under_xarm_description():
    files = [m.get("filename") for m in load().iter("mesh")]
    assert files
    for f in files:
        if f.startswith(PREFIX):
            assert (ROBOT_DIR / "xarm_description" / f[len(PREFIX):]).is_file(), f
