#!/usr/bin/env bash
# V0 用のデータ（Blender-Levels/Level-1 の transforms_train.json・train/・move/）を落とす。
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
exec bash "$here/run.sh" python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='ackermannj/cl-splats-dataset',
    repo_type='dataset',
    local_dir='/data',
    allow_patterns=[
        'Blender-Levels/Level-1/transforms_train.json',
        'Blender-Levels/Level-1/train/*',
        'Blender-Levels/Level-1/move/*',
    ],
)
"
