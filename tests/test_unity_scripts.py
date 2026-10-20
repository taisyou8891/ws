from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "unity" / "DigitalTwin" / "Assets" / "Scripts" / "Ros" / "RosDomainSettings.cs"
)


def test_ros_domain_settings_contents():
    text = SCRIPT.read_text(encoding="utf-8")
    for needle in ("DefaultExecutionOrder(-1000)", "ROS_DOMAIN_ID", "setenv", "void Awake"):
        assert needle in text
