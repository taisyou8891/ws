#!/usr/bin/env bash
# 使い方: bash tools/clsplats/run.sh <コンテナの中で実行するコマンド>
# data/clsplats/ を /data に、data/clsplats/.cache/ を /root/.cache にマウントする。
# --user でホストのユーザとして動かすので、出力ファイルの所有者はホストのユーザになる。
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$root/data/clsplats/.cache/home"
exec docker run --rm --gpus all \
    --user "$(id -u):$(id -g)" \
    -v "$root/data/clsplats:/data" \
    -v "$root/data/clsplats/.cache:/root/.cache" \
    clsplats:local "$@"
