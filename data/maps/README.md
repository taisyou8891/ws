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
コマンドはすべてリポジトリのルートで、1 つずつ実行する。
InstantSplat は `tools/maps/build_map.py` が Docker で起動するので、`docker run` を自分で実行するのは手順 1 の確認だけでよい。

### 0. 最新の main にする

```
git switch main
git pull
```

### 1. 前提を確かめる（初回と、環境を変えたとき）

```
# イメージがあるか
docker image inspect instantsplat:local --format '{{.Id}}'
# コンテナから GPU が見えるか
docker run --rm --gpus all instantsplat:local nvidia-smi
# コンテナの中に InstantSplat と MASt3R の重みがあるか
docker run --rm instantsplat:local ls /InstantSplat/init_geo.py /InstantSplat/mast3r/checkpoints
```

`nvidia-smi` の結果で、ほかの処理が GPU のメモリを大きく使っていないことも確かめる。

### 2. 写真を用意する

- 枚数の目安は 6 枚前後（`map` は 6 枚）。
- 隣り合う写真が重なるように撮る。
- ロボットと作業台が写るように撮る。
- 拡張子は `.jpg`・`.jpeg`・`.png`（大文字と小文字は区別しない）。
- 写真は 1 つのディレクトリにまとめる。リポジトリの外に置いてよい（`build_map.py` が `data/maps/<名前>/work/scene/images/` にコピーする）。

写真の枚数は次のコマンドで数える。この値が `n_views` になる。

```
find <写真のディレクトリ> -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | wc -l
```

### 3. dry-run で実行内容を確かめる

```
python3 tools/maps/build_map.py --images_dir <写真のディレクトリ> --replace --dry-run
```

次の 2 点を確かめる。この段階では何も作られない。

- 1 行目の `n_views=` が、手順 2 で数えた枚数と同じか
- `docker run` の 3 行（init_geo・train・render）と、取り込みの 1 行（末尾に `--replace` が付いている）が出ているか

### 4. 地図を作り直す

```
python3 tools/maps/build_map.py --images_dir <写真のディレクトリ> --replace
```

- 同じ名前の地図がある場合は `--replace` が要る。付け忘れると、InstantSplat を最後まで実行した後、取り込みの段階で終了コード 1 で止まる。
- `--name <名前>`（既定 `map`）、`--iterations <反復数>`（既定 1000）、`--docker_image <イメージ>`（既定 `instantsplat:local`）を指定できる。
- 実行には GPU と、手元の Docker イメージ `instantsplat:local` が要る。
- 作業用のファイルは `data/maps/<名前>/work/` に作られる（追跡しない。実行のたびに作り直す）。
- 各段階の出力は画面ではなく `data/maps/<名前>/work/output/` の `01_init_geo.log`・`02_train.log`・`03_render.log` に入る。進み具合は、別の端末で `tail -f data/maps/map/work/output/02_train.log` などで見る。
- どこかの段階が失敗すると、そこで止まり、取り込みはしない。このとき今の地図（`raw/` と `maps.json`）は変わらない。
- 最後に `registered 'map': ... n_views=<枚数>` と出れば成功。前の版は `data/maps/<名前>/raw_prev/` に残る。

### 5. 結果を確かめる

```
# 生成された地図
ls -l data/maps/map/raw/point_cloud.ply
# 登録簿の変化（n_views と sha256 が変わり、frame は unaligned）
git diff data/maps/maps.json
# 描画結果（見た目の確認）
ls data/maps/map/work/output/interp/ours_1000/
```

### 6. 作り直した後にすること

- `data/maps/maps.json` はリポジトリで追跡しているので、作り直すと差分が出る。この変更は Issue と PR の流れで反映する。
- 作り直した地図は `frame` が `"unaligned"` に戻る。位置合わせ（E1）をやり直す必要がある。
- 前の版に戻すときは、`data/maps/<名前>/raw_prev/` を `raw/` に戻し、`maps.json` を `git checkout data/maps/maps.json` で戻す。
