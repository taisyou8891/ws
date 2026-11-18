from pathlib import Path

SUBSCRIBER = (
    Path(__file__).resolve().parents[1]
    / "unity" / "DigitalTwin" / "Assets" / "Scripts" / "Ros" / "JointStateSubscriber.cs"
)


def test_joint_state_subscriber_uses_ros_tcp_connector():
    text = SUBSCRIBER.read_text(encoding="utf-8")
    assert "ROSConnection" in text
    assert "Subscribe<JointStateMsg>" in text
    assert "ROS2UnityComponent" not in text


def test_joint_state_subscriber_logs():
    text = SUBSCRIBER.read_text(encoding="utf-8")
    assert "scene.IsValid()" in text
    assert text.count("Debug.Log(") >= 3


MAP_TILE_LOADER = (
    Path(__file__).resolve().parents[1]
    / "unity" / "DigitalTwin" / "Assets" / "Scripts" / "Editor" / "MapTileLoader.cs"
)


def test_map_tile_loader_has_main_parts():
    text = MAP_TILE_LOADER.read_text(encoding="utf-8")
    assert "namespace DigitalTwin" in text
    for needle in (
        "Tools/Digital Twin/Load Map Tiles",
        "tiles.json",
        "import_state.json",
        "GaussianSplatAssetCreator",
        "CreateAsset",
        "m_ErrorMessage",
        "GaussianSplatRenderer",
        "m_Asset",
        "MarkSceneDirty",
        "ClearProgressBar",
    ):
        assert needle in text, needle
