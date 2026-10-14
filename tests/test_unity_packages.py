import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "unity" / "DigitalTwin" / "Packages" / "manifest.json"


def test_urdf_importer_is_pinned():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    value = manifest["dependencies"]["com.unity.robotics.urdf-importer"]
    assert value.endswith("#v0.5.2")
