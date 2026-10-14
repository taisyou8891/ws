#!/usr/bin/env bash
# xArm6（xArm Gripper 付き）の URDF とメッシュを Unity プロジェクトに書き出す。
# リポジトリのルートで `bash tools/robot/export_xarm6.sh` と実行する。
set -eo pipefail

# ROS の setup は未定義の変数を参照するため -u は付けない
source /opt/ros/humble/setup.bash

colcon build \
  --base-paths ros2_ws/src \
  --build-base ros2_ws/build \
  --install-base ros2_ws/install \
  --packages-select xarm_description

source ros2_ws/install/setup.bash

tmp_urdf="$(mktemp)"
trap 'rm -f "$tmp_urdf"' EXIT

xacro ros2_ws/src/xarm_ros2/xarm_description/urdf/xarm_device.urdf.xacro \
  dof:=6 robot_type:=xarm add_gripper:=true > "$tmp_urdf"

python3 tools/robot/export_urdf_assets.py \
  --urdf "$tmp_urdf" \
  --package_name xarm_description \
  --package_dir ros2_ws/src/xarm_ros2/xarm_description \
  --out_dir unity/DigitalTwin/Assets/Robot/xarm6 \
  --out_name xarm6.urdf
