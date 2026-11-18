#!/usr/bin/env bash
# D435i の画像を ROS 2 の bag に記録する。
# 使い方: bash tools/capture/record.sh <名前> [--prefix /camera/camera]
# 出力: data/captures/<名前>/bag/（既にあればエラーで止める）。Ctrl+C で止める。
set -u

usage() {
  echo "使い方: bash tools/capture/record.sh <名前> [--prefix /camera/camera]" >&2
  exit 2
}

NAME=""
PREFIX="/camera/camera"
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      [ $# -ge 2 ] || usage
      PREFIX="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    -*)
      echo "エラー: 不明なオプション $1" >&2
      usage
      ;;
    *)
      [ -z "$NAME" ] || usage
      NAME="$1"
      shift
      ;;
  esac
done
[ -n "$NAME" ] || usage
PREFIX="${PREFIX%/}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/data/captures/$NAME/bag"

if [ -e "$OUT" ]; then
  echo "エラー: $OUT が既にある（上書きしない）。別の名前にするか、手で消してから行う" >&2
  exit 1
fi

COLOR_TOPIC="$PREFIX/color/image_raw"
TOPICS="$(ros2 topic list)" || { echo "エラー: ros2 topic list が失敗した（ROS 2 の環境を読み込んだか）" >&2; exit 1; }

if ! printf '%s\n' "$TOPICS" | grep -qx "$COLOR_TOPIC"; then
  echo "エラー: $COLOR_TOPIC がない。カメラのノードが動いていない、または prefix が違う" >&2
  exit 1
fi
if ! printf '%s\n' "$TOPICS" | grep -qx "/joint_states"; then
  echo "警告: /joint_states がない。関節角なしで記録を続ける" >&2
fi

mkdir -p "$(dirname "$OUT")"
echo "記録を始める（Ctrl+C で止める）: $OUT"
ros2 bag record -o "$OUT" \
  "$PREFIX/color/image_raw" \
  "$PREFIX/color/camera_info" \
  "$PREFIX/aligned_depth_to_color/image_raw" \
  /joint_states
