# data/maps

InstantSplat で作った 3DGS 地図を、名前を付けて置く場所。

## 置き場所

- `data/maps/maps.json`：登録簿（追跡する）
- `data/maps/<名前>/raw/`：地図の実体（追跡しない。大きく、画像に撮影時の情報が含まれうるため）
- `data/maps/<名前>/raw_prev/`：`--replace` で置き換える前の版（追跡しない）
- `data/input_data/`：地図を作り直すときの入力画像（追跡しない）

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
- 写真は `data/input_data/` に置く（追跡しない）。`build_map.py` は既定でここを読み、`data/maps/<名前>/work/scene/images/` にコピーする。
- `data/input_data/` の直下にある写真はすべて使われる。初期環境を変えるときは、前の写真を `data/input_data/` から別の場所に移してから、新しい写真を置く。
- `data/input_data/` の中のサブディレクトリと、写真以外のファイル（zip など）は数えない。

写真の枚数は次のコマンドで数える。この値が `n_views` になる。

```
find data/input_data -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | wc -l
```

### 3. dry-run で実行内容を確かめる

```
python3 tools/maps/build_map.py --replace --dry-run
```

次の 2 点を確かめる。この段階では何も作られない。

- 1 行目の `n_views=` が、手順 2 で数えた枚数と同じか
- `docker run` の 3 行（init_geo・train・render）と、取り込みの 1 行（末尾に `--replace` が付いている）が出ているか

### 4. 地図を作り直す

```
python3 tools/maps/build_map.py --replace
```

- 写真は既定で `data/input_data/` から読む。別の場所の写真を使うときは `--images_dir <ディレクトリ>` を付ける（手順 2・3 も同じディレクトリで行う）。
- 同じ名前の地図がある場合は `--replace` が要る。付け忘れると、InstantSplat を最後まで実行した後、取り込みの段階で終了コード 1 で止まる。
- `--name <名前>`（既定 `map`）、`--iterations <反復数>`（既定 1000）、`--docker_image <イメージ>`（既定 `instantsplat:local`）を指定できる。
- 実行には GPU と、手元の Docker イメージ `instantsplat:local` が要る。
- イメージの PyTorch（2.6 以降）は `torch.load` の既定が `weights_only=True` で、そのままでは MASt3R の重みを読めない。`build_map.py` はコンテナに `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` を渡して、これを避ける。
- 描画（render）の段階は、学習に使った視点の画像だけを `data/maps/<名前>/work/output/train/ours_<反復数>/renders/` に描く。動画は作らない。
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
ls data/maps/map/work/output/train/ours_1000/renders/
```

### 6. 作り直した後にすること

- `data/maps/maps.json` はリポジトリで追跡しているので、作り直すと差分が出る。この変更は Issue と PR の流れで反映する。
- 作り直した地図は `frame` が `"unaligned"` に戻る。位置合わせ（E1）をやり直す必要がある。
- 前の版に戻すときは、`data/maps/<名前>/raw_prev/` を `raw/` に戻し、`maps.json` を `git checkout data/maps/maps.json` で戻す。

## タイルに分ける（軽くする）

登録済みの地図から、作業空間の外と不要なガウシアンを除き、空間の格子（タイル）ごとの PLY に分ける。リポジトリのルートで実行する。

```
python3 tools/maps/tile_map.py --name map
```

引数：

- `--name`：地図の名前（必須）
- `--replace`：既存の `tiles/` と `tiles.json` を作り直す（付けないと、出力が既にあるときは終了コード 1 で止まる）
- `--params`：タイル分割の値のファイル（既定は `data/maps/<名前>/tile_params.json`）
- `--min_opacity`：不透明度の下限（既定 0.05）
- `--min_views`：写るカメラ数の下限（既定 4。0 なら除かない）
- `--scale_quantile`：大きさの分位点。これより大きいものを除く（既定 0.999）
- `--bbox XMIN YMIN ZMIN XMAX YMAX ZMAX`：指定した箱の外を除く（既定は指定なし）
- `--tiles_per_axis`：軸ごとのタイル数（既定 4）

値の優先順位は、コマンドラインの引数、`tile_params.json`、既定値の順（引数が最優先）。`tile_params.json` がなければ、引数と既定値だけを使う。

除く順は、不透明度、写る枚数、大きさ、箱。次のときは、終了コード 2 で何も作らずに止まる。

- 入力の sha256 が `maps.json` の登録と違う
- PLY のヘッダが想定の形でない
- `tile_params.json` が読めない、`source_sha256` がない、知らない項目がある、値の型が正しくない
- `tile_params.json` の `source_sha256` が入力の `point_cloud.ply` の sha256 と違う（地図が変わったときに、古い値のまま実行しないため）

出力（`data/maps/<名前>/` の下）：

- `tiles/tile_<i>_<j>_<k>.ply`：タイルごとの PLY（`.gitignore` で追跡しない）
- `tiles/preview_xy.png`・`preview_xz.png`・`preview_zy.png`：確認用の図（追跡しない）
- `tiles.json`：実行の結果の一覧（追跡する）

`tiles.json` の項目：

- `name`・`source`：地図の名前と入力の PLY のパス
- `source_sha256`・`cameras_sha256`：入力の PLY と `cameras.json` の sha256
- `params_file`：使った `tile_params.json` のパス（リポジトリのルートからの相対。使わなければ `null`）
- `params`：実際に使った値（優先順位を適用した後。`bbox` は指定がなければ `null`）
- `counts`：入力の数 `input`、除いた数 `removed_opacity`・`removed_views`・`removed_scale`・`removed_bbox`、残った数 `kept`
- `origin`・`tile_size`：タイルの原点と一辺の長さ
- `tiles`：タイルごとの `file`・`index`・`count`・`min`・`max`・`sha256`（`index` の辞書順）

確認用の図の見方：残ったガウシアンの中心を 2 軸の平面に打った散布図で、色は元の色に近い。`preview_xy.png` は x と y、`preview_xz.png` は x と z、`preview_zy.png` は z（横）と y（縦）。作業台の周りに点が集まっているか、外に浮遊物が残っていないかを見て、残したい範囲を決め、`--bbox` に指定して `--replace` で作り直す。`--bbox` を指定すると、図に箱の範囲が赤い枠で描かれる。

### tile_params.json

タイル分割の値は、地図ごとのファイル `data/maps/<名前>/tile_params.json` に置く（人が手で直すファイルで、ツールは書き換えない）。

```
{
  "source_sha256": "<値を決めた地図の point_cloud.ply の sha256>",
  "min_opacity": 0.05,
  "min_views": 4,
  "scale_quantile": 0.999,
  "bbox": [-0.45, -0.35, 0.15, 0.4, 0.4, 0.9],
  "tiles_per_axis": 4
}
```

- `source_sha256` は必須。そのほかの項目は省略でき、省略した項目は既定値を使う。
- `bbox` は `null` か 6 個の数の配列。
- 上の 6 個以外の項目があると、エラーにする。

## 入力画像を変えたとき（値の直し方）

値の置き場所は `data/maps/<名前>/tile_params.json`。直すのはこのファイルだけで、コードは直さない。

各値の意味と、直す目安：

- `bbox`：地図を作り直すと InstantSplat の座標が変わり、前の箱は意味を持たなくなる。毎回決め直す。
- `min_views`：写真の枚数（`maps.json` の `n_views`）が変わったら見直す。目安は枚数の 3 分の 2 程度（6 枚なら 4）。
- `min_opacity`・`scale_quantile`：通常は変えない。
- `tiles_per_axis`：タイルが大きすぎる、または細かすぎるときに変える。

手順（リポジトリのルートで、コマンドを 1 つずつ実行する）：

1. 地図を作り直す（「地図を作り直す」の節の手順）。`maps.json` の `files["point_cloud.ply"]` が変わる。
2. `python3 tools/maps/tile_map.py --name <名前> --replace` を実行する。`source_sha256` が一致しないので、終了コード 2 で止まる（古い箱のまま実行しないため）。
3. `tile_params.json` の `source_sha256` を、`maps.json` の `files["point_cloud.ply"]` の新しい値にし、`bbox` を `null` にする。
4. `python3 tools/maps/tile_map.py --name <名前> --replace` を実行し、`tiles/preview_*.png` を見て箱を決める。
5. 決めた箱を `tile_params.json` の `bbox` に書き、もう一度 `--replace` で実行する。図に赤い枠が描かれるので、範囲を確かめる。
6. `tile_params.json` と `tiles.json` の変更を、Issue と PR の流れで反映する。

試しに別の値で実行したいときは、ファイルを直さずに引数で上書きできる（例：`--bbox ...`）。その場合も、`tiles.json` の `params` には実際に使った値が残る。
