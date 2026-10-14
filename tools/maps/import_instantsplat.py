#!/usr/bin/env python3
"""InstantSplat の出力を data/maps/<名前>/raw/ に取り込み、data/maps/maps.json に登録する。"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output_dir", required=True, help="InstantSplat の出力ディレクトリ")
    p.add_argument("--images_dir", required=True, help="入力画像のディレクトリ")
    p.add_argument("--name", required=True, help="地図の名前")
    p.add_argument("--iteration", type=int, default=1000, help="反復数（既定 1000）")
    p.add_argument("--replace", action="store_true", help="同じ名前の登録を置き換える")
    p.add_argument("--root", default=str(DEFAULT_ROOT), help="リポジトリのルート（テスト用）")
    return p.parse_args(argv)


def load_registry(path):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"maps": []}


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root).resolve()
    out = Path(args.output_dir).resolve()
    images_dir = Path(args.images_dir).resolve()
    it = args.iteration

    sources = [
        ("point_cloud.ply", out / "point_cloud" / f"iteration_{it}" / "point_cloud.ply"),
        ("cameras.json", out / "cameras.json"),
        ("cfg_args", out / "cfg_args"),
        ("pose_optimized.npy", out / "pose" / f"ours_{it}" / "pose_optimized.npy"),
    ]
    images = sorted(
        p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    ) if images_dir.is_dir() else []
    for _, src in sources:
        if not src.is_file():
            print(f"error: 入力が見つからない: {src}", file=sys.stderr)
            return 2
    if not images:
        print(f"error: 入力画像が見つからない: {images_dir}", file=sys.stderr)
        return 2

    maps_dir = root / "data" / "maps"
    registry_path = maps_dir / "maps.json"
    registry = load_registry(registry_path)
    exists = any(m["name"] == args.name for m in registry["maps"])
    if exists and not args.replace:
        print(f"error: 地図 '{args.name}' は登録済み（置き換えるには --replace）", file=sys.stderr)
        return 1

    map_dir = maps_dir / args.name
    raw = map_dir / "raw"
    raw_prev = map_dir / "raw_prev"
    if args.replace and raw.exists():
        if raw_prev.exists():
            shutil.rmtree(raw_prev)
        raw.rename(raw_prev)

    (raw / "images").mkdir(parents=True)
    copied = []
    for rel, src in sources:
        shutil.copy2(src, raw / rel)
        copied.append(rel)
    for img in images:
        rel = f"images/{img.name}"
        shutil.copy2(img, raw / rel)
        copied.append(rel)

    try:
        source = out.relative_to(root).as_posix()
    except ValueError:
        try:
            source = out.relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            source = out.as_posix()

    entry = {
        "name": args.name,
        "source": source,
        "n_views": len(images),
        "iteration": it,
        "files": {rel: sha256_of(raw / rel) for rel in copied},
        "frame": "unaligned",
    }
    registry["maps"] = [m for m in registry["maps"] if m["name"] != args.name] + [entry]
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"registered '{args.name}': {len(copied)} files, n_views={len(images)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
