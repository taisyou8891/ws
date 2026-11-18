#!/usr/bin/env bash
# 使い方: bash tools/gsicp/run.sh <コンテナの中で実行するコマンド>
# data/gsicp/ を /data に、data/captures/ を /captures に（読み取り専用で）マウントする。
# --user でホストのユーザとして動かすので、出力ファイルの所有者はホストのユーザになる。
# 作業ディレクトリは /opt/gs_icp_slam（上流のコード）。
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$root/data/gsicp"
# --ipc=host: 上流は torch.multiprocessing の共有メモリを大量に使う。既定の /dev/shm（64 MB）では SIGBUS で落ちる。
exec docker run --rm --gpus all --ipc=host \
    --user "$(id -u):$(id -g)" \
    -v "$root/data/gsicp:/data" \
    -e TORCH_HOME=/data/.cache/torch \
    -v "$root/data/captures:/captures:ro" \
    gsicp:local "$@"
