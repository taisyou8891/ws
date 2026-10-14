# data/maps

InstantSplat で作った 3DGS 地図を、名前を付けて置く場所。

## 置き場所

- `data/maps/maps.json`：登録簿（追跡する）
- `data/maps/<名前>/raw/`：地図の実体（追跡しない。大きく、画像に撮影時の情報が含まれうるため）
- `data/maps/<名前>/raw_prev/`：`--replace` で置き換える前の版（追跡しない）

## maps.json の項目

`maps` の配列に、地図ごとに次の項目がある。

- `name`：地図の名前
- `source`：取り込んだ InstantSplat の出力ディレクトリ（リポジトリのルートからの相対パス）
- `n_views`：入力画像の枚数
- `iteration`：反復数
- `files`：コピーした各ファイルの `raw/` からの相対パスと、`sha256sum` と同じ値の sha256
- `frame`：位置合わせの状態。取り込んだ直後は常に `"unaligned"`

## map

名前 `map` は、InstantSplat に 6 枚の画像を入力し、反復 1000 回で作った地図である。
まだ位置合わせをしていないので、`frame` は `"unaligned"` である。

## 既存の InstantSplat の出力を取り込む

リポジトリのルートで実行する。

```
python3 tools/maps/import_instantsplat.py \
  --output_dir <InstantSplat の出力> \
  --images_dir <入力画像> \
  --name <地図の名前>
```

`--iteration <反復数>` で反復数を指定する（既定 1000）。
コピーするのは、`point_cloud/iteration_<反復数>/point_cloud.ply`・`cameras.json`・`cfg_args`・
`pose/ours_<反復数>/pose_optimized.npy`・入力画像（`raw/images/` 以下）である。

同じ名前がすでに登録されている場合、`--replace` がなければ何も変えずに終了コード 1 で止まる。
`--replace` を付けると、前の `raw/` を `raw_prev/` に移し（すでにある `raw_prev/` は消す）、
取り込み直して登録を置き換える。このとき `frame` は `"unaligned"` に戻る。
