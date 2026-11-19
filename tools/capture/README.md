# 手先の D435i の撮影（D0）

手先の D435i で撮った画像を、変化の検出と部分更新の検証（V1 以降）や、COLMAP・CL-Splats に渡せる形で保存する。
撮影は ROS 2 の bag に記録し、後でカラー画像・深度・カメラの内部の値・関節角を取り出す。
bag を残しておけば、取り出し方を変えてやり直せる。

## 1. カメラを起動する

カメラのドライバは、サブモジュール `realsense-ros2-docker` の Docker（`docker-compose-gui-nvidia.yml`）で動かす。
起動は前景で行う。止めるときは Ctrl+C。

```bash
cd realsense-ros2-docker/docker
docker compose -f docker-compose-gui-nvidia.yml up
```

片付けは、同じ場所で次を実行する。

```bash
docker compose -f docker-compose-gui-nvidia.yml down
```

起動の後、別の端末のホストで、カラー画像が約 30 Hz で届くことを確かめる。

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=44
ros2 topic hz /camera/camera/color/image_raw
```

### サブモジュールに必要な手元の変更

記録できるのは、サブモジュールの中に、コミットされていない次の手元の変更があるときだけである。変更があるかは、`git -C realsense-ros2-docker diff --stat` で確かめられる。

- `docker/docker-compose-gui-nvidia.yml` の `realsense_ros2` に加えるもの：
  - `network_mode: host`・`ipc: host`・`pid: host`
  - `environment` に `ROS_DOMAIN_ID=44`
  - 次の `command`

    ```
    /bin/bash -c "source /opt/ros/humble/setup.bash && ros2 launch realsense2_camera rs_launch.py depth_module.depth_profile:=640x480x30 rgb_camera.color_profile:=640x480x30 align_depth.enable:=true enable_gyro:=false enable_accel:=false enable_motion_module:=false depth_module.depth_format:=Z16"
    ```
- `docker/docker-compose.yml` の `realsense_ros2` に加えるもの：`network_mode: "host"`

`ipc: host`・`pid: host` がないと、ホストで記録した bag が 0 件になる。
コンテナ（root）とホスト（一般のユーザ）の間で、Fast DDS の共有メモリ（`/dev/shm`）が使えず、
データがホストに届かないためである。

## 2. 記録する

ホスト側で、リポジトリのルートから実行する（コンテナと同じ `ROS_DOMAIN_ID=44` にそろえる）。

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=44
bash tools/capture/record.sh <名前> [--prefix /camera/camera]
```

- 記録するトピック：`<prefix>/color/image_raw`、`<prefix>/color/camera_info`、`<prefix>/aligned_depth_to_color/image_raw`、`/joint_states`。
- `data/captures/<名前>/bag/` が既にあれば、エラーで止める（上書きしない）。
- カラー画像のトピックがなければ止める。`/joint_states` がなければ警告だけ出して続ける。
- Ctrl+C で止める。

## 3. 取り出す

```bash
source /opt/ros/humble/setup.bash
python3 tools/capture/extract_bag.py <名前> [--every N] [--max-frames M] [--prefix /camera/camera] [--replace]
```

- `--every N`：N 枚に 1 枚だけ取り出す（既定は 1）。`--max-frames M`：最大 M 枚。
- 出力の `color/` か `depth/` が既にあれば、`--replace` がない限りエラーで止める。`--replace` のときは `color/`・`depth/`・`camera_info.json`・`frames.csv` だけを消して作り直す（`bag/` は消さない）。

## 出力の形

`data/captures/<名前>/`（`.gitignore` 済み）の下に作る。

```
bag/                      記録した bag
color/frame_000000.jpg    カラー画像（JPEG 品質 95）
depth/frame_000000.png    深度（16 ビットの png、単位 mm）
camera_info.json          width, height, k（3x3）, d, distortion_model, frame_id
frames.csv                index, stamp_ns, color, depth, depth_dt_ms, joint_names, joint_positions
```

- 深度は、カラーと時刻が最も近いものを選ぶ。差が 20 ms を超える場合は `depth` を空にする。
- 関節角は、時刻が最も近い `/joint_states` を選ぶ（なければ空）。`joint_names`・`joint_positions` は `;` で区切る。
- カラーは `rgb8`・`bgr8`、深度は `16UC1` だけに対応する。

## 撮り方のコツ

- カメラをゆっくり動かす（ぶれと、カラーと深度の時刻のずれを減らす）。
- t0 と t1 で、照明と露出をそろえる。

## CL-Splats・COLMAP に渡すとき

`color/` を使う。
