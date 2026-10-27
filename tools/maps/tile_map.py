#!/usr/bin/env python3
"""登録済みの 3DGS 地図から不要なガウシアンを除き、空間の格子（タイル）ごとの PLY に分ける。"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent
REQUIRED_PROPS = [
    "x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2",
    "rot_0", "rot_1", "rot_2", "rot_3", "f_dc_0", "f_dc_1", "f_dc_2",
]
DEFAULTS = {
    "min_opacity": 0.05,
    "min_views": 4,
    "scale_quantile": 0.999,
    "bbox": None,
    "tiles_per_axis": 4,
}
PARAM_KEYS = {"source_sha256", *DEFAULTS}
MAX_PREVIEW_POINTS = 200_000
PREVIEW_SEED = 0


class InputError(Exception):
    pass


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True, help="地図の名前")
    p.add_argument("--replace", action="store_true", help="既存のタイルと tiles.json を作り直す")
    p.add_argument("--min_opacity", type=float, default=None, help="不透明度の下限（既定 0.05）")
    p.add_argument("--min_views", type=int, default=None, help="写るカメラ数の下限（既定 4）")
    p.add_argument("--scale_quantile", type=float, default=None, help="大きさの分位点（既定 0.999）")
    p.add_argument("--bbox", type=float, nargs=6, default=None,
                   metavar=("XMIN", "YMIN", "ZMIN", "XMAX", "YMAX", "ZMAX"), help="残す箱")
    p.add_argument("--tiles_per_axis", type=int, default=None, help="軸ごとのタイル数（既定 4）")
    p.add_argument("--params", default=None,
                   help="タイル分割の値のファイル（既定 data/maps/<名前>/tile_params.json）")
    p.add_argument("--root", default=str(DEFAULT_ROOT), help="リポジトリのルート（テスト用）")
    return p.parse_args(argv)


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def load_params(path):
    """tile_params.json を読み、検証して辞書を返す。"""
    try:
        params = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise InputError(f"tile_params.json を読めない: {path}")
    if not isinstance(params, dict):
        raise InputError("tile_params.json がオブジェクトでない")
    if not isinstance(params.get("source_sha256"), str):
        raise InputError("tile_params.json に文字列の source_sha256 がない")
    unknown = sorted(set(params) - PARAM_KEYS)
    if unknown:
        raise InputError(f"tile_params.json に知らない項目がある: {', '.join(unknown)}")
    for key in ("min_opacity", "scale_quantile"):
        if key in params and not is_number(params[key]):
            raise InputError(f"tile_params.json の {key} が数でない")
    for key in ("min_views", "tiles_per_axis"):
        if key in params and (not isinstance(params[key], int) or isinstance(params[key], bool)):
            raise InputError(f"tile_params.json の {key} が整数でない")
    if "bbox" in params and params["bbox"] is not None:
        b = params["bbox"]
        if not (isinstance(b, list) and len(b) == 6 and all(is_number(v) for v in b)):
            raise InputError("tile_params.json の bbox が null か 6 個の数の配列でない")
    return params


def read_header(path):
    """ヘッダを検証し、(ヘッダのバイト列, 頂点数, プロパティ名の並び) を返す。"""
    with open(path, "rb") as f:
        head = f.read(1 << 16)
    end = head.find(b"end_header\n")
    if end < 0:
        raise InputError("PLY のヘッダが見つからない")
    header = head[: end + len(b"end_header\n")]
    try:
        lines = header.decode("ascii").split("\n")[:-1]
    except UnicodeDecodeError:
        raise InputError("PLY のヘッダが ASCII でない")
    if not lines or lines[0] != "ply":
        raise InputError("PLY の 1 行目が ply でない")
    if len(lines) < 2 or lines[1] != "format binary_little_endian 1.0":
        raise InputError("PLY の形式が binary_little_endian 1.0 でない")
    count = None
    props = []
    n_elements = 0
    for line in lines[2:-1]:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "comment":
            continue
        if parts[0] == "element":
            n_elements += 1
            if len(parts) != 3 or parts[1] != "vertex" or n_elements > 1:
                raise InputError("PLY の要素は vertex の 1 つだけでなければならない")
            try:
                count = int(parts[2])
            except ValueError:
                raise InputError("PLY の頂点数が整数でない")
        elif parts[0] == "property":
            if count is None:
                raise InputError("PLY の property が element の前にある")
            if len(parts) != 3 or parts[1] != "float":
                raise InputError("PLY のプロパティが property float <名前> の形でない")
            props.append(parts[2])
        else:
            raise InputError("PLY のヘッダに想定外の行がある")
    if count is None:
        raise InputError("PLY に vertex 要素がない")
    missing = [n for n in REQUIRED_PROPS if n not in props]
    if missing:
        raise InputError(f"PLY に必要なプロパティがない: {', '.join(missing)}")
    return header, count, props


def load_cameras(path):
    try:
        cams = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise InputError("cameras.json を読めない")
    if not isinstance(cams, list):
        raise InputError("cameras.json が配列でない")
    out = []
    for c in cams:
        try:
            pos = np.asarray(c["position"], dtype=np.float64)
            rot = np.asarray(c["rotation"], dtype=np.float64)
            w, h, fx, fy = (float(c[k]) for k in ("width", "height", "fx", "fy"))
        except (KeyError, TypeError, ValueError):
            raise InputError("cameras.json の要素の形が正しくない")
        if pos.shape != (3,) or rot.shape != (3, 3):
            raise InputError("cameras.json の position か rotation の形が正しくない")
        out.append((pos, rot, w, h, fx, fy))
    return out


def count_views(xyz, cameras):
    views = np.zeros(len(xyz), dtype=np.int32)
    for pos, rot, w, h, fx, fy in cameras:
        p = (xyz - pos) @ rot
        z = p[:, 2]
        front = z > 0
        safe = np.where(front, z, 1.0)
        u = fx * p[:, 0] / safe + w / 2
        v = fy * p[:, 1] / safe + h / 2
        views += (front & (u >= 0) & (u < w) & (v >= 0) & (v < h)).astype(np.int32)
    return views


def write_previews(out_dir, xyz, f_dc, bbox):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(xyz)
    if n > MAX_PREVIEW_POINTS:
        rng = np.random.default_rng(PREVIEW_SEED)
        sel = np.sort(rng.choice(n, MAX_PREVIEW_POINTS, replace=False))
        xyz, f_dc = xyz[sel], f_dc[sel]
    colors = np.clip(0.5 + 0.28209479 * f_dc, 0.0, 1.0)
    for fname, (a, b) in {"preview_xy.png": (0, 1), "preview_xz.png": (0, 2),
                          "preview_zy.png": (2, 1)}.items():
        names = "xyz"
        fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
        ax.scatter(xyz[:, a], xyz[:, b], c=colors, s=0.3, linewidths=0)
        if bbox is not None:
            lo_a, hi_a, lo_b, hi_b = bbox[a], bbox[a + 3], bbox[b], bbox[b + 3]
            ax.plot([lo_a, hi_a, hi_a, lo_a, lo_a], [lo_b, lo_b, hi_b, hi_b, lo_b],
                    color="red", linewidth=1.0)
        ax.set_xlabel(names[a])
        ax.set_ylabel(names[b])
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, linewidth=0.3)
        fig.savefig(out_dir / fname)
        plt.close(fig)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root).resolve()
    maps_dir = root / "data" / "maps"
    map_dir = maps_dir / args.name
    raw = map_dir / "raw"
    tiles_dir = map_dir / "tiles"
    tiles_json = map_dir / "tiles.json"

    if args.tiles_per_axis is not None and args.tiles_per_axis < 1:
        print("error: --tiles_per_axis は 1 以上", file=sys.stderr)
        return 2

    try:
        registry_path = maps_dir / "maps.json"
        if not registry_path.is_file():
            raise InputError(f"maps.json が見つからない: {registry_path}")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entry = next((m for m in registry["maps"] if m["name"] == args.name), None)
        if entry is None:
            raise InputError(f"地図 '{args.name}' は登録されていない")
        ply_path = raw / "point_cloud.ply"
        cam_path = raw / "cameras.json"
        digests = {}
        for rel, path in (("point_cloud.ply", ply_path), ("cameras.json", cam_path)):
            if not path.is_file():
                raise InputError(f"入力が見つからない: {path}")
            digests[rel] = sha256_of(path)
            if digests[rel] != entry.get("files", {}).get(rel):
                raise InputError(f"{rel} の sha256 が登録と一致しない")
        header, n, props = read_header(ply_path)
        cameras = load_cameras(cam_path)

        params_path = Path(args.params) if args.params is not None else map_dir / "tile_params.json"
        file_params = {}
        params_file = None
        if args.params is not None or params_path.exists():
            file_params = load_params(params_path)
            if file_params["source_sha256"] != digests["point_cloud.ply"]:
                raise InputError(
                    "tile_params.json の source_sha256 が point_cloud.ply と一致しない。"
                    "地図が変わったので値を見直し、source_sha256 を maps.json の "
                    "files[\"point_cloud.ply\"] の値に書き換えること")
            try:
                params_file = params_path.resolve().relative_to(root).as_posix()
            except ValueError:
                params_file = str(params_path)
        used = {}
        for key, default in DEFAULTS.items():
            given = getattr(args, key)
            if given is not None:
                used[key] = given
            elif key in file_params:
                used[key] = file_params[key]
            else:
                used[key] = default
        if used["bbox"] is not None:
            used["bbox"] = list(used["bbox"])
        if used["tiles_per_axis"] < 1:
            raise InputError("tiles_per_axis は 1 以上")
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if (tiles_dir.exists() or tiles_json.exists()) and not args.replace:
        print(f"error: 出力が既にある: {tiles_dir} または {tiles_json}（作り直すには --replace）",
              file=sys.stderr)
        return 1

    data = np.memmap(ply_path, dtype="<f4", mode="r", offset=len(header), shape=(n, len(props)))
    col = {name: i for i, name in enumerate(props)}
    xyz = np.stack([data[:, col["x"]], data[:, col["y"]], data[:, col["z"]]], axis=1).astype(np.float64)

    alive = np.arange(n)
    counts = {"input": n}

    opacity = 1.0 / (1.0 + np.exp(-data[:, col["opacity"]].astype(np.float64)))
    keep = opacity >= used["min_opacity"]
    counts["removed_opacity"] = int(n - keep.sum())
    alive = alive[keep]

    if used["min_views"] > 0:
        keep = count_views(xyz[alive], cameras) >= used["min_views"]
    else:
        keep = np.ones(len(alive), dtype=bool)
    counts["removed_views"] = int(len(alive) - keep.sum())
    alive = alive[keep]

    if len(alive) > 0:
        s = np.stack([data[alive, col[f"scale_{i}"]] for i in range(3)], axis=1).astype(np.float64)
        size = np.exp(s.max(axis=1))
        keep = size <= np.quantile(size, used["scale_quantile"])
    else:
        keep = np.ones(0, dtype=bool)
    counts["removed_scale"] = int(len(alive) - keep.sum())
    alive = alive[keep]

    if used["bbox"] is not None:
        lo = np.asarray(used["bbox"][:3])
        hi = np.asarray(used["bbox"][3:])
        pts = xyz[alive]
        keep = np.all((pts >= lo) & (pts <= hi), axis=1)
    else:
        keep = np.ones(len(alive), dtype=bool)
    counts["removed_bbox"] = int(len(alive) - keep.sum())
    alive = alive[keep]
    counts["kept"] = int(len(alive))

    if len(alive) == 0:
        print("error: 残るガウシアンがない", file=sys.stderr)
        return 1

    pts = xyz[alive]
    origin = pts.min(axis=0)
    extent = float((pts.max(axis=0) - origin).max())
    tile_size = extent / used["tiles_per_axis"] if extent > 0 else 1.0
    idx = np.clip(np.floor((pts - origin) / tile_size).astype(np.int64), 0, used["tiles_per_axis"] - 1)
    key = (idx[:, 0] * used["tiles_per_axis"] + idx[:, 1]) * used["tiles_per_axis"] + idx[:, 2]
    order = np.argsort(key, kind="stable")  # 同じタイル内では入力の順を保つ
    sorted_key = key[order]
    uniq, starts = np.unique(sorted_key, return_index=True)
    ends = np.append(starts[1:], len(order))

    if args.replace and tiles_dir.exists():
        shutil.rmtree(tiles_dir)
    tiles_dir.mkdir(parents=True)

    header_text = header.decode("ascii")
    tiles = []
    for k, s0, e0 in zip(uniq, starts, ends):
        sel = order[s0:e0]
        i, j, kk = (int(v) for v in idx[sel[0]])
        rows = alive[sel]
        tile_header = header_text.replace(f"element vertex {n}\n", f"element vertex {len(rows)}\n", 1)
        fname = f"tile_{i}_{j}_{kk}.ply"
        with open(tiles_dir / fname, "wb") as f:
            f.write(tile_header.encode("ascii"))
            f.write(np.ascontiguousarray(data[rows]).tobytes())
        tp = pts[sel]
        tiles.append({
            "file": f"tiles/{fname}",
            "index": [i, j, kk],
            "count": int(len(rows)),
            "min": [float(v) for v in tp.min(axis=0)],
            "max": [float(v) for v in tp.max(axis=0)],
            "sha256": sha256_of(tiles_dir / fname),
        })
    tiles.sort(key=lambda t: t["index"])

    result = {
        "name": args.name,
        "source": f"data/maps/{args.name}/raw/point_cloud.ply",
        "source_sha256": digests["point_cloud.ply"],
        "cameras_sha256": digests["cameras.json"],
        "params_file": params_file,
        "params": dict(used),
        "counts": counts,
        "origin": [float(v) for v in origin],
        "tile_size": float(tile_size),
        "tiles": tiles,
    }
    tiles_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    f_dc = np.stack([data[alive, col[f"f_dc_{i}"]] for i in range(3)], axis=1).astype(np.float64)
    write_previews(tiles_dir, pts, f_dc, used["bbox"])

    print(f"counts={json.dumps(counts)} tiles={len(tiles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
