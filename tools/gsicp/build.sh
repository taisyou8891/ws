#!/usr/bin/env bash
# GS-ICP SLAM のイメージ gsicp:local を作る。
set -euo pipefail
cd "$(dirname "$0")"
docker build -t gsicp:local .
