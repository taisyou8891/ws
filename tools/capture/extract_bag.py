#!/usr/bin/env python3
"""bag からカラー画像・深度・カメラの内部の値・関節角を取り出す。

使い方:
  python3 tools/capture/extract_bag.py <名前> [--every N] [--max-frames M]
                                        [--prefix /camera/camera] [--replace]

入力は data/captures/<名前>/bag/、出力は data/captures/<名前>/ の下。
ROS のモジュールは main の中で読み込む（ROS なしでテストするため）。
"""
import argparse
import bisect
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CAPTURES = REPO_ROOT / "data" / "captures"

DEPTH_MAX_DT_NS = 20_000_000  # 20 ms
JPEG_QUALITY = 95
CSV_COLUMNS = ["index", "stamp_ns", "color", "depth", "depth_dt_ms",
               "joint_names", "joint_positions"]


def decode_color(height, width, encoding, step, data):
    """rgb8 / bgr8 の画像を BGR の (height, width, 3) uint8 に戻す。"""
    if encoding not in ("rgb8", "bgr8"):
        raise ValueError(f"対応しないカラーのエンコーディング: {encoding}")
    row_bytes = width * 3
    if step < row_bytes:
        raise ValueError(f"step({step}) が width*3({row_bytes}) より小さい")
    buf = np.frombuffer(bytes(data), dtype=np.uint8)
    if buf.size < step * height:
        raise ValueError("データが step*height より短い")
    rows = buf[:step * height].reshape(height, step)[:, :row_bytes]
    img = rows.reshape(height, width, 3)
    if encoding == "rgb8":
        img = img[:, :, ::-1]
    return np.ascontiguousarray(img)


def decode_depth(height, width, encoding, step, data):
    """16UC1 の深度を (height, width) uint16 に戻す（値は変えない）。"""
    if encoding != "16UC1":
        raise ValueError(f"対応しない深度のエンコーディング: {encoding}")
    row_bytes = width * 2
    if step < row_bytes:
        raise ValueError(f"step({step}) が width*2({row_bytes}) より小さい")
    buf = np.frombuffer(bytes(data), dtype=np.uint8)
    if buf.size < step * height:
        raise ValueError("データが step*height より短い")
    rows = buf[:step * height].reshape(height, step)[:, :row_bytes]
    return np.ascontiguousarray(rows).view("<u2").reshape(height, width).astype(np.uint16)


def nearest_index(stamps, t, max_dt_ns=None):
    """昇順の stamps の中で t に最も近い要素の位置と差(ns)を返す。

    max_dt_ns を超える場合、または stamps が空の場合は (None, None)。
    """
    if not stamps:
        return None, None
    i = bisect.bisect_left(stamps, t)
    cands = [j for j in (i - 1, i) if 0 <= j < len(stamps)]
    best = min(cands, key=lambda j: abs(stamps[j] - t))
    dt = abs(stamps[best] - t)
    if max_dt_ns is not None and dt > max_dt_ns:
        return None, None
    return best, dt


def build_depth_plan(depth_positions):
    """index ごとの深度の位置（なければ None）から、深度の位置 -> index のリストを作る。

    同じ深度が複数のカラーに選ばれても、すべての index に保存できるようにする。
    """
    plan = {}
    for index, dpos in enumerate(depth_positions):
        if dpos is not None:
            plan.setdefault(dpos, []).append(index)
    return plan


def camera_info_to_dict(msg):
    """camera_info のメッセージ（属性を持つもの）を辞書にする。"""
    return {
        "width": int(msg.width),
        "height": int(msg.height),
        "k": [[float(msg.k[r * 3 + c]) for c in range(3)] for r in range(3)],
        "d": [float(x) for x in msg.d],
        "distortion_model": str(msg.distortion_model),
        "frame_id": str(msg.header.frame_id),
    }


def make_frame_row(index, stamp_ns, color, depth, depth_dt_ns,
                   joint_names, joint_positions):
    """frames.csv の 1 行（列の順は CSV_COLUMNS）を作る。値がなければ空文字。"""
    return [
        index,
        stamp_ns,
        color,
        depth if depth else "",
        "" if depth_dt_ns is None or not depth else f"{depth_dt_ns / 1e6:.3f}",
        ";".join(joint_names) if joint_names else "",
        ";".join(repr(float(p)) for p in joint_positions) if joint_positions else "",
    ]


def stamp_to_ns(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def read_bag(bag_dir, topics):
    """bag のメッセージを (topic, 位置, 生データ) の順で返すジェネレータ。"""
    import rosbag2_py

    storage = rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id="sqlite3")
    conv = rosbag2_py.ConverterOptions("", "")
    reader = rosbag2_py.SequentialReader()
    reader.open(storage, conv)
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    from rosidl_runtime_py.utilities import get_message
    msg_types = {t: get_message(types[t]) for t in topics if t in types}
    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic in msg_types:
            yield topic, raw, msg_types[topic]


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("name")
    p.add_argument("--every", type=int, default=1)
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--prefix", default="/camera/camera")
    p.add_argument("--replace", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.every < 1:
        sys.exit("エラー: --every は 1 以上にする")
    if args.max_frames is not None and args.max_frames < 1:
        sys.exit("エラー: --max-frames は 1 以上にする")

    import cv2
    from rclpy.serialization import deserialize_message

    root = CAPTURES / args.name
    bag_dir = root / "bag"
    if not bag_dir.is_dir():
        sys.exit(f"エラー: {bag_dir} がない")

    prefix = args.prefix.rstrip("/")
    t_color = f"{prefix}/color/image_raw"
    t_info = f"{prefix}/color/camera_info"
    t_depth = f"{prefix}/aligned_depth_to_color/image_raw"
    t_joint = "/joint_states"

    out_color, out_depth = root / "color", root / "depth"
    out_info, out_csv = root / "camera_info.json", root / "frames.csv"
    if (out_color.exists() or out_depth.exists()) and not args.replace:
        sys.exit(f"エラー: {out_color} か {out_depth} が既にある（作り直すなら --replace）")
    if args.replace:
        for d in (out_color, out_depth):
            if d.exists():
                shutil.rmtree(d)
        for f in (out_info, out_csv):
            if f.exists():
                f.unlink()

    # 1 回目: 時刻と関節角を集める
    color_stamps, depth_stamps, joints, info = [], [], [], None
    for topic, raw, mtype in read_bag(bag_dir, [t_color, t_info, t_depth, t_joint]):
        msg = deserialize_message(raw, mtype)
        if topic == t_color:
            color_stamps.append(stamp_to_ns(msg.header.stamp))
        elif topic == t_depth:
            depth_stamps.append(stamp_to_ns(msg.header.stamp))
        elif topic == t_info and info is None:
            info = camera_info_to_dict(msg)
        elif topic == t_joint:
            joints.append((stamp_to_ns(msg.header.stamp),
                           list(msg.name), list(msg.position)))
    if not color_stamps:
        sys.exit(f"エラー: bag に {t_color} がない")

    joints.sort(key=lambda j: j[0])
    joint_stamps = [j[0] for j in joints]
    depth_order = sorted(range(len(depth_stamps)), key=lambda i: depth_stamps[i])
    depth_sorted = [depth_stamps[i] for i in depth_order]

    # どの位置のメッセージを取り出すかを決める
    selected = list(range(0, len(color_stamps), args.every))
    if args.max_frames is not None:
        selected = selected[:args.max_frames]
    plan = {}  # color の位置 -> index
    rows = {}
    n_no_joint = 0
    matches = []
    for index, pos in enumerate(selected):
        t = color_stamps[pos]
        plan[pos] = index
        k, dt = nearest_index(depth_sorted, t, DEPTH_MAX_DT_NS)
        dpos = depth_order[k] if k is not None else None
        matches.append((dpos, dt))
        j, _ = nearest_index(joint_stamps, t)
        if j is None:
            n_no_joint += 1
            names, positions = [], []
        else:
            names, positions = joints[j][1], joints[j][2]
        rows[index] = (t, dpos, dt, names, positions)

    depth_plan = build_depth_plan([m[0] for m in matches])
    n_no_depth = sum(1 for m in matches if m[0] is None)

    out_color.mkdir(parents=True, exist_ok=True)
    out_depth.mkdir(parents=True, exist_ok=True)

    # 2 回目: 画像を書き出す
    ci = di = -1
    for topic, raw, mtype in read_bag(bag_dir, [t_color, t_depth]):
        if topic == t_color:
            ci += 1
            if ci not in plan:
                continue
            msg = deserialize_message(raw, mtype)
            img = decode_color(msg.height, msg.width, msg.encoding, msg.step, msg.data)
            path = out_color / f"frame_{plan[ci]:06d}.jpg"
            if not cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]):
                sys.exit(f"エラー: {path} を書けない")
        else:
            di += 1
            if di not in depth_plan:
                continue
            msg = deserialize_message(raw, mtype)
            img = decode_depth(msg.height, msg.width, msg.encoding, msg.step, msg.data)
            for index in depth_plan[di]:
                path = out_depth / f"frame_{index:06d}.png"
                if not cv2.imwrite(str(path), img):
                    sys.exit(f"エラー: {path} を書けない")

    if info is not None:
        out_info.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for index in sorted(rows):
            t, dpos, dt, names, positions = rows[index]
            depth_name = f"depth/frame_{index:06d}.png" if dpos is not None else ""
            w.writerow(make_frame_row(index, t, f"color/frame_{index:06d}.jpg",
                                      depth_name, dt, names, positions))

    print(f"取り出し {len(selected)} 枚、深度なし {n_no_depth} 枚、関節角なし {n_no_joint} 枚")


if __name__ == "__main__":
    main()
