# DigitalTwin（Unity プロジェクト）

ROS 2 の `/joint_states` を受け取り、xArm6（xArm Gripper 付き）のモデルを同じ姿勢に動かす。

## 開く

Unity Hub で `unity/DigitalTwin/` を開く。URDF Importer は `Packages/manifest.json` に書いてあるので、自動で入る。

## URDF の取り込み

1. `Assets/Robot/xarm6/xarm6.urdf` を選ぶ。
2. 右クリックして「Import Robot from Selected URDF file」を選ぶ。
3. Axis Type を Z Axis にして取り込む。

## ロボットとシーンの設定

1. 取り込んだロボットのルートの `ArticulationBody` を Immovable にし、重力を切る。
2. シーンに空の GameObject を作り、`ROS2UnityComponent` と `JointStateSubscriber` を付ける。
3. `JointStateSubscriber` の `robotRoot` に、取り込んだロボットを設定する。

`topicName`（既定 `/joint_states`）・`nodeName`・`mimicJoints`（`drive_joint` に追従する関節の名前）は Inspector で変えられる。

## 動作の確かめ方

Unity でシーンを再生した状態で、別の端末で次を実行する。

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 launch xarm_description xarm6_rviz_display.launch.py add_gripper:=true
```

GUI のスライダーを動かすと、Unity のモデルも同じように動く。

## 実機を使うとき

xarm_ros2 のドライバが出す関節の状態のトピック名に、`topicName` を合わせる。
