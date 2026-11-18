# 手先の D435i の撮影（D0）

手先の D435i で撮った画像を、変化の検出と部分更新の検証（V1 以降）や、COLMAP・CL-Splats に渡せる形で保存する。
撮影は ROS 2 の bag に記録し、後でカラー画像・深度・カメラの内部の値・関節角を取り出す。
bag を残しておけば、取り出し方を変えてやり直せる。

## 1. カメラを起動する

カメラのドライバは、サブモジュール `realsense-ros2-docker` の Docker（`network_mode: "host"`）で動かす。トピックはホストから見える。

```bash
cd realsense-ros2-docker/docker
docker compose up -d
docker compose exec -e ROS_DOMAIN_ID=44 realsense_ros2 bash
```

コンテナの中で次を実行する。

```bash
source /opt/ros/humble/setup.bash
ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
```

止めるときは、`realsense-ros2-docker/docker` で `docker compose down` を実行する。

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
