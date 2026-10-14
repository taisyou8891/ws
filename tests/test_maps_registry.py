import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_map_is_registered():
    registry = json.loads((ROOT / "data/maps/maps.json").read_text())
    entries = {m["name"]: m for m in registry["maps"]}
    assert "map" in entries
    m = entries["map"]
    assert m["frame"] == "unaligned"
    assert m["n_views"] == 6
    assert "point_cloud.ply" in m["files"]
    assert "cameras.json" in m["files"]
