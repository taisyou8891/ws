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

## 地図を作り直す（初期環境を変える）

作業の初期環境を変えたいとき（別の写真、別の枚数）は、写真のディレクトリを渡して地図を作り直す。

### 写真の用意

- 枚数の目安は 6 枚前後（`map` は 6 枚）。
- 隣り合う写真が重なるように撮る。
- ロボットと作業台が写るように撮る。
- 拡張子は `.jpg`・`.jpeg`・`.png`（大文字と小文字は区別しない）。

### 実行

リポジトリのルートで実行する。

```
python3 tools/maps/build_map.py --images_dir <写真のディレクトリ> --name map --replace
```

- 同じ名前の地図がある場合は `--replace` が要る。前の版は `raw_prev/` に残る。
- `--iterations <反復数>`（既定 1000）、`--docker_image <イメージ>`（既定 `instantsplat:local`）を指定できる。
- `--dry-run` を付けると、実行する予定のコマンドを表示するだけで、何も作らない。
- 実行には GPU と、手元の Docker イメージ `instantsplat:local` が要る。
- 作業用のファイルは `data/maps/<名前>/work/` に作られる（追跡しない。実行のたびに作り直す）。

### 結果の確かめ方

- `data/maps/<名前>/work/output/` の描画結果とログ（`01_init_geo.log`・`02_train.log`・`03_render.log`）を見る。
- 取り込みに成功すると、`maps.json` と `raw/` が更新される。

### 位置合わせ

作り直した地図は `frame` が `"unaligned"` に戻る。位置合わせ（E1）をやり直す必要がある。
