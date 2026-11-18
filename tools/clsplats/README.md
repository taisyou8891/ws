# CL-Splats（V0）

CL-Splats（ICCV 2025、arXiv 2506.21117）を Docker で動かし、公開データの物体移動（`move`）で論文の結果を再現できるかを確かめる。
CL-Splats は、変化した領域を見つけ、その領域のガウシアンだけを少数の新しい画像で最適化し直す。
コードは jan-ackermann/cl-splats のコミット `587fffc207f9c7cbb348f35e6d1d223d007eab69` に固定している。

RTX 5070 Ti（compute capability 12.0）は CUDA 12.8 以上が必要だが、ホストの nvcc は 12.6 なので Docker（CUDA 12.8 の開発用イメージ）で動かす。

## 作り方・動かし方

```bash
bash tools/clsplats/build.sh          # イメージ clsplats:local を作る
bash tools/clsplats/download_v0.sh    # data/clsplats/Blender-Levels/Level-1 に move 用のデータを落とす
bash tools/clsplats/run.sh python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_capability())"
bash tools/clsplats/run.sh sh -c "cd /data && cl-splats-train --data-path /data/Blender-Levels/Level-1 --change-type move --eval --white-background"
```

- `run.sh` は `data/clsplats/` をコンテナの `/data` に、`data/clsplats/.cache/` を `/root/.cache` にマウントする。
  gsplat の CUDA カーネルは初回に JIT でコンパイルされる（約 47 秒。イメージの作成時は GPU がないのでコンパイルしない）。
  コンパイル結果や DINOv2 などの重みは `.cache` に残り、2 回目から省ける。
- ファイルの所有者は、`docker run --user "$(id -u):$(id -g)"` でホストのユーザにしている。
  非 root で `/root/.cache` を使えるよう、Dockerfile で `chmod 755 /root` と `HOME=/root/.cache/home` を設定している。
- 学習の出力は、コンテナの作業ディレクトリの `outputs/` に出る。上のコマンドは `/data` に移ってから実行するので、`data/clsplats/outputs/` になる。
- `data/clsplats/` は `.gitignore` に入れている（データ・出力・キャッシュはコミットしない）。

## V0 の結果

### 環境

- CUDA 12.8.1（`nvidia/cuda:12.8.1-devel-ubuntu24.04`）、PyTorch 2.7.1+cu128、torchvision 0.22.1+cu128、gsplat 1.5.3
- GPU: NVIDIA GeForce RTX 5070 Ti（16 GB）
- `torch` の確認の出力: `2.7.1+cu128 True (12, 0)`

### 評価の数値（Level-1、`move`、テスト 25 視点の平均）

| 実行 | PSNR | SSIM | 時間 |
| --- | --- | --- | --- |
| A: Issue のコマンドのまま（`train.iters_per_timestep` は既定の 100） | 14.69 dB | 0.8841 | 全体 212 秒（変化の更新 t=1 は約 15 秒。重みの取得と JIT を含む） |
| B: 参考。A に `train.iters_per_timestep=30000` を加えた | 33.15 dB | 0.9900 | 全体 973 秒（t=0 の再構成 約 392 秒、t=1 の更新 約 567 秒） |

- CL-Splats が出す評価は PSNR と SSIM（LPIPS は出ない）。
- 既定の設定では、t=0 の再構成が 100 反復しかなく、ベースのシーンが再構成されていない。そのため A の PSNR は低い。
  データセットにはベースのシーンのチェックポイントがあるが、Issue の指示どおり落としていない。
  B は t=0 も t=1 も 30000 反復にした実行で、論文の設定そのものとは限らない（論文の反復数は確認していない）。
- A の t=1 では、深度の整合に 21/50 視点で失敗した警告が出た（B は 5/50）。

### 論文の数値との差

論文（arXiv 2506.21117）の Table 8（Reconstruction Quality on Level-1 of the Synthetic Data from the CL-Splats Dataset）の、CL-Splats の Move は PSNR 37.481、LPIPS 0.007、SSIM 0.994。

| 実行 | PSNR の差（今回 - 論文） | SSIM の差 |
| --- | --- | --- |
| A | -22.79 dB | -0.110 |
| B | -4.33 dB | -0.004 |

A・B とも PSNR が論文より 3 dB 以上低い。A は設定（反復数）、B は残りの差の理由が未確認。

### その他

- 変化の検出のマスクは、既定ではファイルに出力されない（`outputs/` には `eval/t0001/` の描画画像だけが出た）。
- GPU のメモリの最大の使用量は、B の実行中に `nvidia-smi` で見て 9724 MiB（A では測っていない）。
