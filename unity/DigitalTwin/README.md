# DigitalTwin（Unity プロジェクト）

ROS 2 の `/joint_states` を受け取り、xArm6（xArm Gripper 付き）のモデルを同じ姿勢に動かす。

## 開く

Unity Hub で `unity/DigitalTwin/` を開く。URDF Importer は `Packages/manifest.json` に書いてあるので、自動で入る。

## URDF の取り込み

1. `Assets/Robot/xarm6/xarm6.urdf` を選ぶ。
2. 右クリックして「Import Robot from Selected URDF file」を選ぶ。
3. Axis Type は既定の Y Axis のままで取り込む。

取り込むと、Hierarchy に `UF_ROBOT` のような名前でロボットが出る。

## ロボットとシーンの設定

### 1. ロボットの根元を固定し、重力を切る

1. Hierarchy でロボット（`UF_ROBOT`）を開き、その下の根元のリンク（`link_base` Articulation Body が付いている）を選ぶ。
2. Inspector の **Articulation Body** で **Immovable** にチェックを入れる。根元が落ちたり倒れたりしなくなる。Immovable にするのは `link_base` だけにする。
3. グリッパを含むすべてのリンクで **Use Gravity** のチェックを外す。関節が重力で垂れ下がらないようにするため。まとめて外すには、Hierarchy の検索欄に `t:ArticulationBody` と入力し、出てきたものを全部選んでから、Inspector の Use Gravity のチェックを外す。

### 2. 受信用の空のオブジェクトを作る

1. Hierarchy の何もないところを右クリックし、**Create Empty** を選ぶ。名前は何でもよい（例：`RosBridge`）。
2. そのオブジェクトを選び、Inspector の **Add Component** で `RosDomainSettings`・`ROS2UnityComponent`・`JointStateSubscriber` の 3 つを追加する。3 つとも同じオブジェクトに付ける。

### 3. 動かすロボットを指定する

`RosBridge` を選んだまま、Inspector の JointStateSubscriber の欄にある **Robot Root** の枠に、Hierarchy のロボット（`UF_ROBOT`）をドラッグして入れる。

### 4. ROS_DOMAIN_ID を合わせる

Unity と ROS 2 の端末は、同じ ROS_DOMAIN_ID でないと通信できない。違うと、同じネットワークの別のロボットのデータを受け取ってしまうことがある。

1. 端末で `echo $ROS_DOMAIN_ID` を実行し、値を確かめる（例：`44`）。
2. `RosBridge` の Inspector の RosDomainSettings の欄にある **Domain Id** に、その値を入れる。
3. **Domain Id** を `-1` にすると、Unity を起動したときの環境変数 `ROS_DOMAIN_ID` をそのまま使う（デスクトップのアイコンから起動した Unity では、設定されていないことが多い）。

値を変えたときは、再生をいったん止めてから、もう一度再生する。

### 5. Inspector で変えられるそのほかの項目

どれも通常は変えなくてよい。

- **Topic Name**：受け取るトピックの名前。既定は `/joint_states`。実機のドライバが別の名前で出しているときだけ合わせる。
- **Node Name**：Unity 側の ROS 2 ノードの名前。既定は `unity_joint_state_subscriber`。
- **Mimic Joints**：グリッパの `drive_joint` と同じ動きをさせる関節の名前の一覧。既定で 5 つ入っている。

設定が終わったら、Ctrl+S でシーンを保存する。

## カメラ位置の操作

メニューの GameObject → Align With View（Ctrl+Shift+F）を選ぶ。Main Camera が今の Scene ビューと同じ位置・向きに移り、再生中もその視点で見える。

## 動作の確かめ方

1. Unity の ▶（再生）ボタンを押す。
2. 端末で、リポジトリのルートから次を実行する。関節のスライダーが並んだウィンドウが開く。

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run joint_state_publisher_gui joint_state_publisher_gui unity/DigitalTwin/Assets/Robot/xarm6/xarm6.urdf
   ```

3. 別の端末で `ros2 node list` を実行し、`/unity_joint_state_subscriber` が出ることを確かめる。出なければ、Unity が再生中か、ROS_DOMAIN_ID が合っているかを確かめる。
4. スライダーを動かすと、Unity のロボットも同じように動く。`drive_joint` を動かすと、グリッパが開閉する。

`xarm_description` の `xarm6_rviz_display.launch.py` はスライダーの GUI を出さない（実機のドライバの関節の状態を中継するためのもの）ので、この確認には使わない。

