from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "unity" / "DigitalTwin" / "Assets" / "Scripts" / "Ros" / "RosDomainSettings.cs"
)


def test_ros_domain_settings_contents():
    text = SCRIPT.read_text(encoding="utf-8")
    for needle in ("DefaultExecutionOrder(-1000)", "ROS_DOMAIN_ID", "setenv", "void Awake"):
        assert needle in text


def test_joint_state_subscriber_logs():
    path = (
        Path(__file__).resolve().parents[1]
        / "unity" / "DigitalTwin" / "Assets" / "Scripts" / "Ros" / "JointStateSubscriber.cs"
    )
    text = path.read_text(encoding="utf-8")
    assert "scene.IsValid()" in text
    assert text.count("Debug.Log(") >= 3
