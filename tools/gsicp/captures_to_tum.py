#!/usr/bin/env python3
"""extract_bag.py の出力を、GS-ICP SLAM が読める TUM RGB-D の形に変える。

使い方:
  python3 tools/gsicp/captures_to_tum.py <名前> [--depth-trunc 3.0] [--replace]

入力は data/captures/<名前>/（frames.csv・camera_info.json・color/・depth/）。
出力は data/gsicp/captures/<名前>/ の下:
  rgb/ depth/            色（jpg のままコピー）と深度（TUM の単位に直した 16bit png）
  rgb.txt depth.txt      「秒 相対パス」の一覧（上流の TrajManager が読む）
  associations.txt       「rgb の秒 rgb のパス depth の秒 depth のパス」
  groundtruth.txt        正解の姿勢がないので、単位の姿勢を並べたダミー（ATE は意味を持たない）
  camera.txt             上流の configs/TUM/*.txt と同じ項目の設定ファイル
深度のない行（frames.csv の depth が空）は除く。

深度の単位: 入力の png は mm。TUM は 5000 で割ると m になる値なので、mm を 5 倍して書く。
"""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CAPTURES = REPO_ROOT / "data" / "captures"
OUT_ROOT = REPO_ROOT / "data" / "gsicp" / "captures"

TUM_DEPTH_SCALE = 5000.0
MM_TO_TUM = TUM_DEPTH_SCALE / 1000.0  # 5.0


def depth_mm_to_tum(depth_mm):
    """uint16 の mm を、TUM の単位（5000 で割ると m）の uint16 にする。表せない値は 65535 で頭打ち。"""
    scaled = np.asarray(depth_mm, dtype=np.float64) * MM_TO_TUM
    return np.clip(np.rint(scaled), 0, 65535).astype(np.uint16)


def stamp_text(stamp_ns):
    """ナノ秒の整数を「秒.マイクロ秒」の文字列にする。"""
    sec, ns = divmod(int(stamp_ns), 1_000_000_000)
    return f"{sec}.{ns // 1000:06d}"


def read_rows_with_depth(frames_csv):
    """frames.csv から、深度のある行だけを (index, stamp_ns, color, depth) で返す。"""
    rows = []
    with open(frames_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["depth"]:
                continue
            rows.append((int(r["index"]), int(r["stamp_ns"]), r["color"], r["depth"]))
    return rows


def camera_config_text(info, depth_trunc):
    """camera_info.json から、上流の configs/TUM/*.txt と同じ形の設定を作る。"""
    k = info["k"]
    w, h = int(info["width"]), int(info["height"])
    fx, fy, cx, cy = k[0][0], k[1][1], k[0][2], k[1][2]
    return (
        "## camera parameters\n"
        "W H fx fy cx cy depth_scale depth_trunc dataset_type\n"
        f"{w} {h} {fx} {fy} {cx} {cy} {TUM_DEPTH_SCALE} {depth_trunc} tum"
    )


def convert(src, dst, depth_trunc=3.0, replace=False):
    """src（extract_bag の出力）を dst（TUM の形）に変える。書いたフレーム数を返す。"""
    src, dst = Path(src), Path(dst)
    if dst.exists():
        if not replace:
            raise FileExistsError(f"{dst} が既にある（作り直すなら --replace）")
        shutil.rmtree(dst)
    rows = read_rows_with_depth(src / "frames.csv")
    info = json.loads((src / "camera_info.json").read_text(encoding="utf-8"))

    (dst / "rgb").mkdir(parents=True)
    (dst / "depth").mkdir()
    rgb_lines, depth_lines, assoc_lines, gt_lines = [], [], [], []
    for index, stamp_ns, color, depth in rows:
        name = f"{index:06d}"
        t = stamp_text(stamp_ns)
        rgb_rel, depth_rel = f"rgb/{name}{Path(color).suffix}", f"depth/{name}.png"
        shutil.copyfile(src / color, dst / rgb_rel)
        with Image.open(src / depth) as im:
            arr = np.array(im)
        if arr.dtype != np.uint16:
            raise ValueError(f"{src / depth}: 深度が uint16 ではない（{arr.dtype}）")
        Image.fromarray(depth_mm_to_tum(arr)).save(dst / depth_rel)
        rgb_lines.append(f"{t} {rgb_rel}")
        depth_lines.append(f"{t} {depth_rel}")
        assoc_lines.append(f"{t} {rgb_rel} {t} {depth_rel}")
        gt_lines.append(f"{t} 0 0 0 0 0 0 1")

    def write(name, title, lines):
        head = [f"# {title}", f"# file: '{dst.name}/{name}'"]
        (dst / name).write_text("\n".join(head + lines) + "\n", encoding="utf-8")

    write("rgb.txt", "color images\n# timestamp filename", rgb_lines)
    write("depth.txt", "depth maps\n# timestamp filename", depth_lines)
    (dst / "associations.txt").write_text("\n".join(assoc_lines) + "\n", encoding="utf-8")
    write("groundtruth.txt", "ダミーの姿勢（単位の姿勢）。ATE は意味を持たない\n# timestamp tx ty tz qx qy qz qw", gt_lines)
    (dst / "camera.txt").write_text(camera_config_text(info, depth_trunc), encoding="utf-8")
    return len(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", help="data/captures/ の下の名前")
    p.add_argument("--depth-trunc", type=float, default=3.0, help="設定の depth_trunc（m）。既定 3.0")
    p.add_argument("--replace", action="store_true", help="出力が既にあれば作り直す")
    args = p.parse_args()
    src = CAPTURES / args.name
    if not (src / "frames.csv").is_file():
        sys.exit(f"エラー: {src / 'frames.csv'} がない（先に extract_bag.py を実行する）")
    dst = OUT_ROOT / args.name
    try:
        n = convert(src, dst, args.depth_trunc, args.replace)
    except FileExistsError as e:
        sys.exit(f"エラー: {e}")
    print(f"{n} フレームを {dst} に書いた")


if __name__ == "__main__":
    main()
