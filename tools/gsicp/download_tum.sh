#!/usr/bin/env bash
# TUM RGB-D の fr1/desk を data/gsicp/TUM/ に落とす（上流の download_tum.sh と同じ場所から）。
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$root/data/gsicp/TUM"
cd "$root/data/gsicp/TUM"
wget -nc https://vision.in.tum.de/rgbd/dataset/freiburg1/rgbd_dataset_freiburg1_desk.tgz
tar -xzf rgbd_dataset_freiburg1_desk.tgz
