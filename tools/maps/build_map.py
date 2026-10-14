#!/usr/bin/env python3
"""写真のディレクトリから InstantSplat で 3DGS 地図を作り直し、名前を付けて登録する。"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--images_dir",
        default=None,
        help="写真のディレクトリ（省略すると <--root の値>/my_data/ を使う）",
    )
    p.add_argument("--name", default="map", help="地図の名前（既定 map）")
    p.add_argument("--iterations", type=int, default=1000, help="反復数（既定 1000）")
    p.add_argument("--docker_image", default="instantsplat:local", help="Docker イメージ")
    p.add_argument("--replace", action="store_true", help="同じ名前の登録を置き換える")
    p.add_argument("--dry-run", action="store_true", help="実行予定のコマンドを表示するだけ")
    p.add_argument("--root", default=str(DEFAULT_ROOT), help="リポジトリのルート（テスト用）")
    return p.parse_args(argv)


def list_images(images_dir):
    return sorted(
        p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def stage_commands(n_views, iterations):
    n = str(n_views)
    it = str(iterations)
    return [
        (
            "01_init_geo.log",
            ["python", "-W", "ignore", "./init_geo.py", "-s", "/work/scene", "-m", "/work/output",
             "--n_views", n, "--focal_avg", "--co_vis_dsp", "--conf_aware_ranking", "--infer_video"],
        ),
        (
            "02_train.log",
            ["python", "./train.py", "-s", "/work/scene", "-m", "/work/output", "-r", "1",
             "--n_views", n, "--iterations", it, "--pp_optimizer", "--optim_pose"],
        ),
        (
            "03_render.log",
            ["python", "./render.py", "-s", "/work/scene", "-m", "/work/output", "-r", "4",
             "--n_views", n, "--iterations", it, "--infer_video"],
        ),
    ]


def docker_command(args, work, stage):
    return [
        "docker", "run", "--rm", "--gpus", "all",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-e", "HOME=/tmp",
        "-v", f"{work}:/work",
        "-w", "/InstantSplat",
        args.docker_image,
    ] + stage


def import_command(args, root, work):
    cmd = [
        sys.executable, str(Path(__file__).resolve().parent / "import_instantsplat.py"),
        "--output_dir", str(work / "output"),
        "--images_dir", str(work / "scene" / "images"),
        "--name", args.name,
        "--iteration", str(args.iterations),
        "--root", str(root),
    ]
    if args.replace:
        cmd.append("--replace")
    return cmd


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root).resolve()
    if args.images_dir is None:
        images_dir = (root / "my_data").resolve()
    else:
        images_dir = Path(args.images_dir).resolve()
    if not images_dir.is_dir():
        print(f"error: 写真のディレクトリが見つからない: {images_dir}", file=sys.stderr)
        return 1
    images = list_images(images_dir)
    n_views = len(images)
    if n_views == 0:
        print(f"error: 写真が見つからない: {images_dir}", file=sys.stderr)
        return 1

    work = root / "data" / "maps" / args.name / "work"
    stages = stage_commands(n_views, args.iterations)

    if args.dry_run:
        print(f"n_views={n_views}")
        for _, stage in stages:
            print(shlex.join(docker_command(args, work, stage)))
        print(shlex.join(import_command(args, root, work)))
        return 0

    if work.exists():
        shutil.rmtree(work)
    (work / "scene" / "images").mkdir(parents=True)
    (work / "output").mkdir()
    for img in images:
        shutil.copy2(img, work / "scene" / "images" / img.name)

    for log_name, stage in stages:
        cmd = docker_command(args, work, stage)
        print(shlex.join(cmd), flush=True)
        with open(work / "output" / log_name, "wb") as log:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        if rc != 0:
            print(f"error: 段階 {log_name} が終了コード {rc} で終了", file=sys.stderr)
            return rc

    return subprocess.run(import_command(args, root, work)).returncode


if __name__ == "__main__":
    sys.exit(main())
