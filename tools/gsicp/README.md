# GS-ICP SLAM（B0）

GS-ICP SLAM（ECCV 2024、arXiv 2403.12550、MIT）を Docker で動かし、公開データ TUM RGB-D の `fr1/desk` で論文の速度・画質が出るかを確かめる。
G-ICP で位置を求め、深度から作ったガウシアンを地図に使う RGB-D の 3DGS SLAM。案 B（深度の差で地図の一部を更新する）の土台として使う。

## 作り方

RTX 5070 Ti（compute capability 12.0）は CUDA 12.8 以上が必要なので、`tools/clsplats/` と同じく CUDA 12.8 の開発用イメージで作る。

```bash
bash tools/gsicp/build.sh      # イメージ gsicp:local を作る（初回は 30 分ほどかかる。PCL のインストールが長い）
```

- ベース: `nvidia/cuda:12.8.1-devel-ubuntu24.04`、Python 3.12
- GS-ICP SLAM はコミット `5f996a872a979406b270fe0ee3b0a8f25c5e9ae3` に固定（`git clone --recursive`）
- PyTorch は CUDA 12.8 版の `torch==2.7.1`・`torchvision==0.22.1`、`TORCH_CUDA_ARCH_LIST=12.0`
- CUDA の拡張（`diff-gaussian-rasterization`・`simple-knn`・`fast_gicp`）はイメージの作成時にコンパイルする

確認（コンテナの中）:

```bash
bash tools/gsicp/run.sh python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_capability())"
# 2.7.1+cu128 12.8 True (12, 0)
```

## 動かし方

```bash
bash tools/gsicp/download_tum.sh     # data/gsicp/TUM/ に fr1/desk を落とす（340 MB）
```

`run.sh` は `data/gsicp/` を `/data` に、`data/captures/` を `/captures` に（読み取り専用で）マウントする。作業ディレクトリは `/opt/gs_icp_slam`。
`--ipc=host` を付けている（既定の共有メモリ 64 MB では、上流の `torch.multiprocessing` が SIGBUS で落ちる）。
LPIPS の重み（AlexNet）は初回に自動で落ち、`data/gsicp/.cache/torch/` に残る。

上流の `tum.sh`（速度の上限 30 FPS）・`tum_unlimit.sh`（上限なし）に当たる実行（`fr1/desk` のみ、同じパラメータ）:

```bash
args="--dataset_path /data/TUM/rgbd_dataset_freiburg1_desk --config configs/TUM/rgbd_dataset_freiburg1_desk.txt \
  --keyframe_th 0.81 --knn_maxd 99999.0 --overlapped_th 1e-3 --max_correspondence_distance 0.03 \
  --trackable_opacity_th 0.09 --overlapped_th2 1e-3 --downsample_rate 5 --save_results"
bash tools/gsicp/run.sh python -W ignore gs_icp_slam.py $args --output_path /data/results/desk_limit
bash tools/gsicp/run.sh python -W ignore gs_icp_slam_unlimit.py $args --output_path /data/results/desk_unlimit
```

表示（rerun）は `--rerun_viewer` を付けたときだけ使われるので、付けない。FPS・ATE・PSNR・SSIM・LPIPS は標準出力の末尾に出る。

## 当てた修正

上流は Python 3.9・PyTorch 2.0・CUDA 11.8・numpy 1 向け。新しい環境で通すため、`Dockerfile` の中で次を当てている（上流のコードは変えない）。

1. `rasterizer_impl.h` などに `#include <cstdint>`、`simple_knn.cu` に `<cfloat>`・`<cstdint>` を足す（新しい CUDA・gcc で型が未定義になる）。
2. `fast_gicp` 同梱の pybind11 を v2.13.6 に差し替える（古い版は Python 3.12 で `PyFrameObject` が不完全型になりコンパイルできない）。
3. `matplotlib` を足す（上流の `requirements.txt` に無いが `utils/traj_utils.py` が読む）。
4. `utils/traj_utils.py` の `np.unicode_` を `np.str_` に直す（numpy 2 で無くなった）。
5. `mp_Mapper.py` の `c2w = final_poses[i]` を `np.asarray(...)` 経由にする（numpy 2 では `np.linalg.inv` にテンソルを渡すとテンソルが返り、`.transpose()` が失敗して画質の評価が落ちる）。
6. `mp_Tracker.py`・`mp_Tracker_unlimit.py` の `np.linalg.linalg.svd` を `np.linalg.svd` に直す（numpy 2 で `np.linalg.linalg` が無い。ATE の計算）。

`run.sh` 側: `--ipc=host`（共有メモリ）と `TORCH_HOME=/data/.cache/torch`（LPIPS の重みの保存先）。

## B0 の結果

- 環境: イメージ CUDA 12.8.1、PyTorch 2.7.1+cu128、Python 3.12、numpy 2.5。GPU は NVIDIA GeForce RTX 5070 Ti（(12, 0)）。
- データ: TUM `fr1/desk`（フレーム抽出後 592 枚）。1 回ずつの実行（乱数の幅は見ていない）。
- 時間は起動と評価を含む全体。GPU メモリの最大は `nvidia-smi` を 1 秒ごとに見た値で、実行前から使われていた約 0.5 GB（画面表示など）を含む。

| 実行 | FPS | ATE RMSE [cm] | PSNR [dB] | SSIM | LPIPS | 時間 | GPU メモリの最大 |
|---|---|---|---|---|---|---|---|
| 上限あり（30 FPS） | 29.98 | 2.65 | 17.81 | 0.709 | 0.299 | 46 秒 | 2258 MiB |
| 上限なし | 59.42 | 2.64 | 17.08 | 0.693 | 0.330 | 36 秒 | 2112 MiB |

論文（arXiv 2403.12550）との比較:

| 指標 | 論文 | 今回 | 差 |
|---|---|---|---|
| ATE（表 2、`fr1/desk`、30 FPS 上限） | 2.7 cm | 2.65 cm | -0.05 |
| 上限あり: PSNR / SSIM / LPIPS / FPS（表 4） | 20.72 / 0.768 / 0.218 / 29.99 | 17.81 / 0.709 / 0.299 / 29.98 | -2.91 dB / -0.059 / +0.081 / -0.01 |
| 上限なし: PSNR / SSIM / LPIPS / FPS（表 4） | 19.62 / 0.750 / 0.240 / 73.92 | 17.08 / 0.693 / 0.330 / 59.42 | -2.54 dB / -0.057 / +0.090 / -14.5 |

- 表 4 は TUM の数値で、シーンごとの内訳が載っていない（3 シーンの平均とみられる）ので、`fr1/desk` だけの今回の値とは条件が違う。比較は目安。
- 論文は上限なしで最大 107 FPS と書いている（これは Replica）。TUM の上限なしは表 4 の 73.92 FPS。今回の 59.42 FPS はその 80 %。
- 位置の精度は論文と同じ（2.65 cm）。画質は論文より PSNR で 2.5〜2.9 dB 低い（止める条件の 3 dB にはぎりぎり届かない）。- 実行の途中で `Assignment with new_width equal to 0, ...`（PCL の警告）が大量に出るが、結果には影響していない。

## 自分たちのデータでの動かし方

```bash
python3 tools/capture/extract_bag.py <名前>          # bag から data/captures/<名前>/ に取り出す（#41）
python3 tools/gsicp/captures_to_tum.py <名前>        # data/gsicp/captures/<名前>/ に TUM の形で書く（--depth-trunc で設定の上限を変える）
bash tools/gsicp/run.sh python -W ignore gs_icp_slam.py \
  --dataset_path /data/captures/<名前> --config /data/captures/<名前>/camera.txt \
  --keyframe_th 0.81 --knn_maxd 99999.0 --overlapped_th 1e-3 --max_correspondence_distance 0.03 \
  --trackable_opacity_th 0.09 --overlapped_th2 1e-3 --downsample_rate 5 --save_results \
  --output_path /data/results/<名前>
```

`captures_to_tum.py` がやること:

- `frames.csv` の `depth` が空の行を除く。
- 深度は mm の 16bit png を 5 倍して書く（TUM は 5000 で割ると m）。色は jpg のままコピーする。
- `camera_info.json` から、上流の `configs/TUM/*.txt` と同じ項目の `camera.txt` を作る（`depth_scale` は 5000、`depth_trunc` は 3.0 m）。
- 上流の `TrajManager` は `rgb.txt`・`depth.txt`・`groundtruth.txt` を読む。正解の姿勢がないので `groundtruth.txt` は単位の姿勢のダミー。**ATE の値は意味を持たない**（PSNR・SSIM・LPIPS・FPS は使える）。
- `associations.txt` も書く（上流は読まないが TUM の形として）。

### 参考：自分たちのデータ（t0）

`t0`（640×480、約 30 fps）を変換して上限あり（30 FPS）で 1 回実行した（深度のあるフレーム 1517 枚）。

| FPS | PSNR [dB] | SSIM | LPIPS | 時間 | GPU メモリの最大 |
|---|---|---|---|---|---|
| 29.99 | 21.03 | 0.894 | 0.253 | 99 秒 | 4229 MiB |

エラーなく終わった。ATE（14.55 cm）はダミーの正解なので意味がない。軌跡・地図の見た目は確かめていない。
