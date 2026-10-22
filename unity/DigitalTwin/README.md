# DigitalTwin（Unity プロジェクト）

ROS 2 の `/joint_states` を受け取り、xArm6（xArm Gripper 付き）のモデルを同じ姿勢に動かす。

Unity と ROS 2 は **ROS-TCP-Connector** でつなぐ。ROS 2 側で中継ノード（ROS-TCP-Endpoint、`ros2_ws/src/ROS-TCP-Endpoint`）を動かし、Unity はそのノードと TCP（既定はポート 10000）で通信する。ROS 2 の通信（DDS・ROS_DOMAIN_ID）は中継ノードの側で決まるので、Unity の側では設定しない。

## 開く

Unity Hub で `unity/DigitalTwin/` を開く。URDF Importer と ROS-TCP-Connector は `Packages/manifest.json` に書いてあるので、自動で入る。

## ROS-TCP-Connector の設定（初回だけ）

1. メニューの **Robotics → ROS Settings** を開く。
2. **Protocol** を **ROS2** にする（ROS 2 用のメッセージの型に切り替わる）。
3. **ROS IP Address** を `127.0.0.1`、**ROS Port** を `10000` にする（同じ PC で中継ノードを動かす場合）。

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
2. そのオブジェクトを選び、Inspector の **Add Component** で `JointStateSubscriber` を追加する。

### 3. 動かすロボットを指定する

`RosBridge` を選んだまま、Inspector の JointStateSubscriber の欄にある **Robot Root** の枠に、Hierarchy のロボット（`UF_ROBOT`）をドラッグして入れる。

### 4. Inspector で変えられるそのほかの項目

どれも通常は変えなくてよい。

- **Topic Name**：受け取るトピックの名前。既定は `/joint_states`。実機のドライバが別の名前で出しているときだけ合わせる。
- **Mimic Joints**：グリッパの `drive_joint` と同じ動きをさせる関節の名前の一覧。既定で 5 つ入っている。

設定が終わったら、Ctrl+S でシーンを保存する。

## カメラ位置の操作

メニューの GameObject → Align With View（Ctrl+Shift+F）を選ぶ。Main Camera が今の Scene ビューと同じ位置・向きに移り、再生中もその視点で見える。

## 中継ノードのビルド（初回と、更新したとき）

リポジトリのルートで実行する。

```bash
source /opt/ros/humble/setup.bash
colcon build --base-paths ros2_ws/src --build-base ros2_ws/build --install-base ros2_ws/install --packages-select ros_tcp_endpoint
```

## 動作の確かめ方

1. 端末 A で、中継ノードを起動する（リポジトリのルートから）。

   ```bash
   source /opt/ros/humble/setup.bash
   source ros2_ws/install/setup.bash
   ros2 launch ros_tcp_endpoint endpoint.py
   ```

2. Unity の ▶（再生）ボタンを押す。端末 A に、Unity からつながったことと、`/joint_states` を購読したことが表示される。Unity の Game ビューの左上には、接続の状態を示す矢印が出る（青：接続中、赤：つながらない）。
3. 端末 B で、関節のスライダーの GUI を起動する（リポジトリのルートから）。

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run joint_state_publisher_gui joint_state_publisher_gui unity/DigitalTwin/Assets/Robot/xarm6/xarm6.urdf
   ```

4. スライダーを動かすと、Unity のロボットも同じように動く。`drive_joint` を動かすと、グリッパが開閉する。

端末 A と B は、同じ ROS_DOMAIN_ID にしておく。`xarm_description` の `xarm6_rviz_display.launch.py` はスライダーの GUI を出さないので、この確認には使わない。
