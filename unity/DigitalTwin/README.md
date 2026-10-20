# DigitalTwin（Unity プロジェクト）

ROS 2 の `/joint_states` を受け取り、xArm6（xArm Gripper 付き）のモデルを同じ姿勢に動かす。

## 開く

Unity Hub で `unity/DigitalTwin/` を開く。URDF Importer は `Packages/manifest.json` に書いてあるので、自動で入る。

## URDF の取り込み

1. `Assets/Robot/xarm6/xarm6.urdf` を選ぶ。
2. 右クリックして「Import Robot from Selected URDF file」を選ぶ。
3. Axis Type は既定の Y Axis のままで取り込む（Z Axis にすると、各リンクの形が回ってばらばらに表示される）。

取り込むと、Hierarchy に `UF_ROBOT` のような名前でロボットが出る。

## ロボットとシーンの設定

### 1. ロボットの根元を固定し、重力を切る

1. Hierarchy でロボット（`UF_ROBOT`）を開き、その下の根元のリンク（`link_base` Articulation Body が付いている）を選ぶ。
2. Inspector の **Articulation Body** で **Immovable** にチェックを入れる。根元が落ちたり倒れたりしなくなる。
3. 同じところの **Use Gravity** のチェックを外す。関節が重力で垂れ下がらないようにするため。子のリンクにも Articulation Body が付いているので、垂れ下がるようならそれらの Use Gravity も外す。

### 2. 受信用の空のオブジェクトを作る

1. Hierarchy の何もないところを右クリックし、**Create Empty** を選ぶ。名前は何でもよい（例：`RosBridge`）。
2. そのオブジェクトを選び、Inspector の **Add Component** で `ROS2UnityComponent` を追加し、続けて `JointStateSubscriber` も追加する。2 つとも同じオブジェクトに付ける。

### 3. 動かすロボットを指定する

`RosBridge` を選んだまま、Inspector の JointStateSubscriber の欄にある **Robot Root** の枠に、Hierarchy のロボット（`UF_ROBOT`）をドラッグして入れる。

### 4. Inspector で変えられる項目

どれも通常は変えなくてよい。

- **Topic Name**：受け取るトピックの名前。既定は `/joint_states`。実機のドライバが別の名前で出しているときだけ合わせる。
- **Node Name**：Unity 側の ROS 2 ノードの名前。既定のままでよい。
- **Mimic Joints**：グリッパの `drive_joint` と同じ動きをさせる関節の名前の一覧。既定で 5 つ入っている。

## 動作の確かめ方

Unity の再生ボタンを押した状態で、別の端末で次を実行する。

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 launch xarm_description xarm6_rviz_display.launch.py add_gripper:=true
```

出てきた GUI のスライダーを動かすと、Unity のロボットも同じように動く。

## 実機を使うとき

xarm_ros2 のドライバが出す関節の状態のトピック名に、**Topic Name** を合わせる。
