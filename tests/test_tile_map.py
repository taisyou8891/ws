import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "maps" / "tile_map.py"

PROPS = ["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
         "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
COL = {n: i for i, n in enumerate(PROPS)}

# 画像 100x100、焦点距離 100、原点・単位回転のカメラ
CAM = {"id": 0, "width": 100, "height": 100, "position": [0.0, 0.0, 0.0],
       "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "fx": 100.0, "fy": 100.0}


def header_bytes(n, props=PROPS, fmt="binary_little_endian 1.0", ptype="float"):
    lines = ["ply", f"format {fmt}", f"element vertex {n}"]
    lines += [f"property {ptype} {p}" for p in props]
    lines.append("end_header")
    return ("\n".join(lines) + "\n").encode("ascii")


def make_rows(n, seed=0):
    rng = np.random.default_rng(seed)
    rows = rng.normal(size=(n, len(PROPS))).astype("<f4")
    rows[:, COL["opacity"]] = 5.0  # 不透明度 約 0.993
    rows[:, COL["scale_0"]:COL["scale_2"] + 1] = -3.0
    return rows


def sha(data):
    return hashlib.sha256(data).hexdigest()


def setup(root, rows, cameras=None, ply_bytes=None, name="m"):
    raw = root / "data/maps" / name / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    ply = ply_bytes if ply_bytes is not None else header_bytes(len(rows)) + rows.astype("<f4").tobytes()
    cams = json.dumps([CAM] if cameras is None else cameras).encode()
    (raw / "point_cloud.ply").write_bytes(ply)
    (raw / "cameras.json").write_bytes(cams)
    registry = {"maps": [{"name": name, "files": {
        "point_cloud.ply": sha(ply), "cameras.json": sha(cams)}}]}
    (root / "data/maps/maps.json").write_text(json.dumps(registry))
    return raw


def run(root, *extra, name="m"):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--name", name, *extra],
        capture_output=True, text=True,
    )


def load(root, name="m"):
    return json.loads((root / "data/maps" / name / "tiles.json").read_text())


def read_tile(root, tile, name="m"):
    data = (root / "data/maps" / name / tile["file"]).read_bytes()
    end = data.index(b"end_header\n") + len(b"end_header\n")
    return data[:end], np.frombuffer(data[end:], dtype="<f4").reshape(-1, len(PROPS))


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted((root / "data/maps").rglob("*")) if p.is_file()
    }


def place(rows, pts):
    rows[:, COL["x"]:COL["z"] + 1] = np.asarray(pts, dtype="<f4")


# 除く処理を 1 つずつ確かめるための引数（ほかは何も除かない）

def opts(**kw):
    base = {"--min_opacity": "0", "--min_views": "0", "--scale_quantile": "1.0"}
    base.update({"--" + k: str(v) for k, v in kw.items()})
    return [s for kv in base.items() for s in kv]


# ---- 入力の確かめ ----

def test_header_ascii_format_fails(tmp_path):
    rows = make_rows(5)
    ply = header_bytes(5, fmt="ascii 1.0") + rows.tobytes()
    setup(tmp_path, rows, ply_bytes=ply)
    r = run(tmp_path)
    assert r.returncode == 2
    assert "error:" in r.stderr
    assert not (tmp_path / "data/maps/m/tiles").exists()
    assert not (tmp_path / "data/maps/m/tiles.json").exists()


def test_header_missing_opacity_fails(tmp_path):
    props = [p for p in PROPS if p != "opacity"]
    rows = make_rows(5)[:, [COL[p] for p in props]]
    ply = header_bytes(5, props=props) + rows.tobytes()
    setup(tmp_path, rows, ply_bytes=ply)
    r = run(tmp_path)
    assert r.returncode == 2
    assert not (tmp_path / "data/maps/m/tiles").exists()
    assert not (tmp_path / "data/maps/m/tiles.json").exists()


def test_header_double_property_fails(tmp_path):
    rows = make_rows(5)
    ply = header_bytes(5, ptype="double") + rows.tobytes()
    setup(tmp_path, rows, ply_bytes=ply)
    r = run(tmp_path)
    assert r.returncode == 2
    assert not (tmp_path / "data/maps/m/tiles").exists()
    assert not (tmp_path / "data/maps/m/tiles.json").exists()


def test_unregistered_name_fails(tmp_path):
    setup(tmp_path, make_rows(5))
    r = run(tmp_path, name="other")
    assert r.returncode == 2
    assert "error:" in r.stderr


def test_ply_sha_mismatch_fails(tmp_path):
    raw = setup(tmp_path, make_rows(5))
    with open(raw / "point_cloud.ply", "ab") as f:
        f.write(b"\0")
    r = run(tmp_path)
    assert r.returncode == 2
    assert not (tmp_path / "data/maps/m/tiles").exists()


def test_cameras_sha_mismatch_fails(tmp_path):
    raw = setup(tmp_path, make_rows(5))
    (raw / "cameras.json").write_text(json.dumps([CAM, CAM]))
    r = run(tmp_path)
    assert r.returncode == 2
    assert not (tmp_path / "data/maps/m/tiles").exists()


def test_bad_cameras_shape_fails(tmp_path):
    bad = dict(CAM)
    del bad["fx"]
    setup(tmp_path, make_rows(5), cameras=[bad])
    r = run(tmp_path)
    assert r.returncode == 2
    assert not (tmp_path / "data/maps/m/tiles").exists()


# ---- 除く処理 ----

def test_remove_opacity(tmp_path):
    rows = make_rows(10)
    rows[:3, COL["opacity"]] = -5.0  # 約 0.0067
    setup(tmp_path, rows)
    r = run(tmp_path, *opts(min_opacity=0.05))
    assert r.returncode == 0, r.stderr
    c = load(tmp_path)["counts"]
    assert c == {"input": 10, "removed_opacity": 3, "removed_views": 0,
                 "removed_scale": 0, "removed_bbox": 0, "kept": 7}
    kept = np.concatenate([read_tile(tmp_path, t)[1] for t in load(tmp_path)["tiles"]])
    assert (kept[:, COL["opacity"]] == 5.0).all()


def test_remove_views(tmp_path):
    rows = make_rows(6)
    place(rows, [[0, 0, 1], [0.1, 0.1, 2], [0, 0, -1], [5, 0, 1], [0, -5, 1], [0.2, 0, 3]])
    # 全点が 1 台に写るか写らないか。点 2（後ろ）、3・4（画像の外）が除かれる
    setup(tmp_path, rows)
    r = run(tmp_path, *opts(min_views=1))
    assert r.returncode == 0, r.stderr
    c = load(tmp_path)["counts"]
    assert c["removed_views"] == 3
    assert c["kept"] == 3
    assert c["input"] == 6


def test_views_boundary(tmp_path):
    rows = make_rows(6)
    # u = fx * x / z + 50。z = 1 のとき x = -0.5 で u = 0（写る）、x = 0.5 で u = 100（写らない）
    place(rows, [[-0.5, 0, 1], [0.5, 0, 1], [0, -0.5, 1], [0, 0.5, 1], [0.4999, 0, 1], [0, 0, 0]])
    setup(tmp_path, rows)
    r = run(tmp_path, *opts(min_views=1))
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["counts"]["kept"] == 3  # u=0、v=0、u<100
    kept = np.concatenate([read_tile(tmp_path, x)[1] for x in t["tiles"]])
    got = {(float(a), float(b)) for a, b in kept[:, [COL["x"], COL["y"]]]}
    assert got == {(-0.5, 0.0), (0.0, -0.5), (np.float32(0.4999).item(), 0.0)}


def test_views_counts_multiple_cameras(tmp_path):
    cam2 = dict(CAM)
    cam2["position"] = [10.0, 0.0, 0.0]  # 点 (0,0,1) は cam2 から見て x=-10 で画像の外
    rows = make_rows(2)
    place(rows, [[0, 0, 1], [10, 0, 1]])
    # 点 0 は cam1 のみ、点 1 は cam2 のみに写る。--min_views 2 なら両方除かれる
    setup(tmp_path, rows, cameras=[CAM, cam2])
    r = run(tmp_path, *opts(min_views=2))
    assert r.returncode == 1  # 全部除かれて何も残らない
    r = run(tmp_path, *opts(min_views=1))
    assert r.returncode == 0, r.stderr
    assert load(tmp_path)["counts"]["kept"] == 2


def test_remove_scale(tmp_path):
    rows = make_rows(10)
    rows[:, COL["scale_0"]] = np.linspace(-3, -1, 10)
    rows[:, COL["scale_1"]] = -4.0
    setup(tmp_path, rows)
    r = run(tmp_path, *opts(scale_quantile=0.9))
    assert r.returncode == 0, r.stderr
    c = load(tmp_path)["counts"]
    assert c["removed_scale"] == 1
    assert c["kept"] == 9


def test_remove_bbox(tmp_path):
    rows = make_rows(5)
    place(rows, [[0, 0, 0], [1, 1, 1], [2, 0, 0], [0.5, 0.5, -0.5], [1, 1, 1.5]])
    setup(tmp_path, rows)
    r = run(tmp_path, *opts(), "--bbox", "0", "0", "-1", "1", "1", "1")
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["counts"]["removed_bbox"] == 2  # 境界上の (1,1,1) は残る
    assert t["counts"]["kept"] == 3
    assert t["params"]["bbox"] == [0, 0, -1, 1, 1, 1]


def test_counts_sum(tmp_path):
    rows = make_rows(400, seed=3)
    rows[:, COL["opacity"]] = np.random.default_rng(4).normal(size=400) * 3
    place(rows, np.random.default_rng(5).uniform(-1, 1, size=(400, 3)))
    rows[:, COL["z"]] += 2.0
    rows[:, COL["scale_0"]] = np.random.default_rng(6).uniform(-4, -1, size=400)
    setup(tmp_path, rows)
    r = run(tmp_path, "--min_opacity", "0.1", "--min_views", "1", "--scale_quantile", "0.95",
            "--bbox", "-1", "-1", "0", "1", "1", "2.5")
    assert r.returncode == 0, r.stderr
    c = load(tmp_path)["counts"]
    assert c["input"] == 400
    assert c["input"] == (c["removed_opacity"] + c["removed_views"] + c["removed_scale"]
                          + c["removed_bbox"] + c["kept"])
    assert c["removed_opacity"] > 0 and c["removed_scale"] > 0 and c["removed_bbox"] > 0
    assert f"tiles={len(load(tmp_path)['tiles'])}" in r.stdout


# ---- タイル分け ----

def expected_tiles(pts, tpa):
    pts = pts.astype(np.float64)
    origin = pts.min(axis=0)
    extent = (pts.max(axis=0) - origin).max()
    size = extent / tpa if extent > 0 else 1.0
    idx = np.clip(np.floor((pts - origin) / size).astype(int), 0, tpa - 1)
    return origin, size, idx


def test_tiles_bytes_order_and_index(tmp_path):
    rows = make_rows(800, seed=7)
    place(rows, np.random.default_rng(8).uniform(-1, 1, size=(800, 3)))
    setup(tmp_path, rows)
    r = run(tmp_path, *opts())
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    origin, size, idx = expected_tiles(rows[:, :3], 4)
    assert t["origin"] == [float(v) for v in origin]
    assert t["tile_size"] == float(size)
    assert sum(x["count"] for x in t["tiles"]) == t["counts"]["kept"] == 800
    assert [x["index"] for x in t["tiles"]] == sorted(x["index"] for x in t["tiles"])
    in_hdr = header_bytes(800)
    for tile in t["tiles"]:
        hdr, body = read_tile(tmp_path, tile)
        sel = np.where((idx == np.array(tile["index"])).all(axis=1))[0]
        assert tile["file"] == "tiles/tile_{}_{}_{}.ply".format(*tile["index"])
        assert len(sel) == tile["count"] == len(body)
        assert body.tobytes() == rows[sel].tobytes()  # 入力と同じ行、同じ順
        assert hdr == in_hdr.replace(b"element vertex 800", f"element vertex {len(sel)}".encode())
        assert tile["min"] == [float(v) for v in rows[sel, :3].astype(np.float64).min(axis=0)]
        assert tile["max"] == [float(v) for v in rows[sel, :3].astype(np.float64).max(axis=0)]


def test_tile_edges_are_clipped(tmp_path):
    rows = make_rows(5)
    # 範囲 4、tiles_per_axis 4 なら tile_size 1。最大値の点は番号 4 ではなく 3 に収める
    place(rows, [[0, 0, 0], [4, 4, 4], [1, 1, 1], [0.999, 2, 3.999], [2, 0, 3]])
    setup(tmp_path, rows)
    r = run(tmp_path, *opts())
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["tile_size"] == 1.0
    got = {tuple(x["index"]) for x in t["tiles"]}
    assert got == {(0, 0, 0), (3, 3, 3), (1, 1, 1), (0, 2, 3), (2, 0, 3)}
    assert len(t["tiles"]) == 5  # 空のタイルは作らない


def test_zero_extent_tile_size(tmp_path):
    rows = make_rows(3)
    place(rows, [[1, 2, 3]] * 3)
    setup(tmp_path, rows)
    r = run(tmp_path, *opts())
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["tile_size"] == 1.0
    assert [x["index"] for x in t["tiles"]] == [[0, 0, 0]]
    assert t["tiles"][0]["count"] == 3


def test_tiles_json_sha_matches(tmp_path):
    rows = make_rows(300, seed=11)
    place(rows, np.random.default_rng(12).uniform(-1, 1, size=(300, 3)))
    raw = setup(tmp_path, rows)
    assert run(tmp_path, *opts()).returncode == 0
    t = load(tmp_path)
    assert t["source"] == "data/maps/m/raw/point_cloud.ply"
    assert t["source_sha256"] == sha((raw / "point_cloud.ply").read_bytes())
    assert t["cameras_sha256"] == sha((raw / "cameras.json").read_bytes())
    for tile in t["tiles"]:
        assert sha((tmp_path / "data/maps/m" / tile["file"]).read_bytes()) == tile["sha256"]
    assert t["params"] == {"min_opacity": 0.0, "min_views": 0, "scale_quantile": 1.0,
                           "bbox": None, "tiles_per_axis": 4}


def test_tiles_json_format(tmp_path):
    setup(tmp_path, make_rows(20))
    assert run(tmp_path, *opts()).returncode == 0
    text = (tmp_path / "data/maps/m/tiles.json").read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert text == json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n"


# ---- 確認用の図 ----

def test_previews_written(tmp_path):
    rows = make_rows(100, seed=2)
    setup(tmp_path, rows)
    assert run(tmp_path, *opts(), "--bbox", "-5", "-5", "-5", "5", "5", "5").returncode == 0
    for name in ["preview_xy.png", "preview_xz.png", "preview_zy.png"]:
        data = (tmp_path / "data/maps/m/tiles" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
    t = load(tmp_path)
    assert not any("preview" in x["file"] for x in t["tiles"])


# ---- 既存の出力・再現性 ----

def test_second_run_without_replace_fails(tmp_path):
    setup(tmp_path, make_rows(50))
    assert run(tmp_path, *opts()).returncode == 0
    before = snapshot(tmp_path)
    r = run(tmp_path, *opts())
    assert r.returncode == 1
    assert "error:" in r.stderr
    assert snapshot(tmp_path) == before


def test_only_tiles_json_exists_fails(tmp_path):
    setup(tmp_path, make_rows(5))
    (tmp_path / "data/maps/m/tiles.json").write_text("{}")
    r = run(tmp_path, *opts())
    assert r.returncode == 1
    assert (tmp_path / "data/maps/m/tiles.json").read_text() == "{}"
    assert not (tmp_path / "data/maps/m/tiles").exists()


def test_replace_rebuilds(tmp_path):
    setup(tmp_path, make_rows(50))
    assert run(tmp_path, *opts()).returncode == 0
    stale = tmp_path / "data/maps/m/tiles/stale.ply"
    stale.write_bytes(b"x")
    other = tmp_path / "data/maps/m/keep.txt"
    other.write_text("keep")
    r = run(tmp_path, *opts(min_opacity=0), "--replace", "--tiles_per_axis", "2")
    assert r.returncode == 0, r.stderr
    assert not stale.exists()
    assert other.read_text() == "keep"
    assert load(tmp_path)["params"]["tiles_per_axis"] == 2
    assert (tmp_path / "data/maps/m/tiles/preview_xy.png").is_file()


def test_deterministic(tmp_path):
    rows = make_rows(600, seed=21)
    place(rows, np.random.default_rng(22).uniform(-1, 1, size=(600, 3)))
    setup(tmp_path, rows)
    assert run(tmp_path, *opts()).returncode == 0

    def outputs():
        base = tmp_path / "data/maps/m"
        d = {"tiles.json": (base / "tiles.json").read_bytes()}
        for p in sorted((base / "tiles").glob("tile_*.ply")):
            d[p.name] = p.read_bytes()
        return d

    first = outputs()
    assert run(tmp_path, *opts(), "--replace").returncode == 0
    assert outputs() == first


# ---- tile_params.json ----

def write_params(root, raw, name="m", path=None, **kw):
    """合成データの point_cloud.ply の sha256 を入れた tile_params.json を書く。"""
    body = {"source_sha256": sha((raw / "point_cloud.ply").read_bytes())}
    body.update(kw)
    path = path or root / "data/maps" / name / "tile_params.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def params_setup(tmp_path, n=300):
    rows = make_rows(n, seed=31)
    place(rows, np.random.default_rng(32).uniform(-1, 1, size=(n, 3)))
    return setup(tmp_path, rows)


def assert_no_output(root):
    assert not (root / "data/maps/m/tiles").exists()
    assert not (root / "data/maps/m/tiles.json").exists()


def test_params_file_values_used(tmp_path):
    raw = params_setup(tmp_path)
    write_params(tmp_path, raw, min_opacity=0.0, min_views=0, scale_quantile=1.0,
                 bbox=[-0.5, -0.5, -0.5, 0.5, 0.5, 0.5], tiles_per_axis=2)
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["params_file"] == "data/maps/m/tile_params.json"
    assert t["params"] == {"min_opacity": 0.0, "min_views": 0, "scale_quantile": 1.0,
                           "bbox": [-0.5, -0.5, -0.5, 0.5, 0.5, 0.5], "tiles_per_axis": 2}
    assert t["counts"]["removed_bbox"] > 0
    assert max(max(x["index"]) for x in t["tiles"]) <= 1


def test_args_override_params_file(tmp_path):
    raw = params_setup(tmp_path)
    write_params(tmp_path, raw, min_opacity=0.0, min_views=0, scale_quantile=1.0,
                 bbox=[-0.5, -0.5, -0.5, 0.5, 0.5, 0.5], tiles_per_axis=2)
    r = run(tmp_path, "--tiles_per_axis", "3", "--bbox", "-1", "-1", "-1", "1", "1", "1",
            "--min_views", "0")
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["params"]["tiles_per_axis"] == 3
    assert t["params"]["bbox"] == [-1, -1, -1, 1, 1, 1]
    assert t["params"]["min_opacity"] == 0.0  # 指定しない項目はファイルの値
    assert t["counts"]["removed_bbox"] == 0
    assert t["params_file"] == "data/maps/m/tile_params.json"


def test_params_file_omitted_items_use_defaults(tmp_path):
    raw = params_setup(tmp_path)
    write_params(tmp_path, raw, min_views=0, bbox=None)
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert load(tmp_path)["params"] == {"min_opacity": 0.05, "min_views": 0,
                                        "scale_quantile": 0.999, "bbox": None,
                                        "tiles_per_axis": 4}


def test_no_params_file_same_as_before(tmp_path):
    params_setup(tmp_path)
    r = run(tmp_path, *opts())
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["params_file"] is None
    assert t["params"] == {"min_opacity": 0.0, "min_views": 0, "scale_quantile": 1.0,
                           "bbox": None, "tiles_per_axis": 4}


def test_params_file_sha_mismatch_fails(tmp_path):
    raw = params_setup(tmp_path)
    p = write_params(tmp_path, raw, min_views=0)
    body = json.loads(p.read_text())
    body["source_sha256"] = "0" * 64
    p.write_text(json.dumps(body))
    r = run(tmp_path)
    assert r.returncode == 2
    assert "source_sha256" in r.stderr
    assert_no_output(tmp_path)


def test_params_file_bad_content_fails(tmp_path):
    raw = params_setup(tmp_path)
    good = sha((raw / "point_cloud.ply").read_bytes())
    cases = [
        "{not json",
        "[1, 2]",
        json.dumps({"min_views": 0}),
        json.dumps({"source_sha256": good, "unknown_item": 1}),
        json.dumps({"source_sha256": good, "bbox": [0, 0, 0, 1, 1]}),
        json.dumps({"source_sha256": good, "bbox": [0, 0, 0, 1, 1, "x"]}),
        json.dumps({"source_sha256": good, "bbox": 5}),
        json.dumps({"source_sha256": good, "min_views": "4"}),
        json.dumps({"source_sha256": good, "min_views": 1.5}),
        json.dumps({"source_sha256": good, "tiles_per_axis": 0}),
        json.dumps({"source_sha256": good, "min_opacity": True}),
    ]
    for text in cases:
        (tmp_path / "data/maps/m/tile_params.json").write_text(text)
        r = run(tmp_path)
        assert r.returncode == 2, text
        assert "error:" in r.stderr
        assert_no_output(tmp_path)


def test_params_option_selects_other_file(tmp_path):
    raw = params_setup(tmp_path)
    write_params(tmp_path, raw, tiles_per_axis=3, min_views=0)  # 既定の場所のファイル
    other = write_params(tmp_path, raw, path=tmp_path / "elsewhere/p.json",
                         tiles_per_axis=2, min_views=0)
    r = run(tmp_path, "--params", str(other))
    assert r.returncode == 0, r.stderr
    t = load(tmp_path)
    assert t["params"]["tiles_per_axis"] == 2
    assert t["params_file"] == "elsewhere/p.json"
    missing = run(tmp_path, "--params", str(tmp_path / "none.json"), "--replace")
    assert missing.returncode == 2
