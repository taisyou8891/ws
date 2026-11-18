#!/usr/bin/env bash
# CL-Splats のイメージ clsplats:local を作る。
set -euo pipefail
cd "$(dirname "$0")"
docker build -t clsplats:local .
