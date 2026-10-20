using System.Collections.Generic;
using ROS2;
using Unity.Robotics.UrdfImporter;
using UnityEngine;

namespace DigitalTwin
{

/// <summary>
/// /joint_states (sensor_msgs/JointState) を購読し、取り込んだロボットの関節に反映する。
/// 同じ GameObject に ROS2UnityComponent が必要。
/// </summary>
public class JointStateSubscriber : MonoBehaviour
{
    [SerializeField] private string topicName = "/joint_states";
    [SerializeField] private string nodeName = "unity_joint_state_subscriber";
    [SerializeField] private Transform robotRoot;
    [SerializeField] private List<string> mimicJoints = new List<string>
    {
        "left_finger_joint",
        "left_inner_knuckle_joint",
        "right_outer_knuckle_joint",
        "right_finger_joint",
        "right_inner_knuckle_joint",
    };

    private const string DriveJointName = "drive_joint";

    private ROS2UnityComponent ros2Unity;
    private ROS2Node ros2Node;
    private ISubscription<sensor_msgs.msg.JointState> jointSub;

    private readonly Dictionary<string, ArticulationBody> bodies = new Dictionary<string, ArticulationBody>();
    private readonly HashSet<string> warnedNames = new HashSet<string>();

    // コールバック（メインスレッドではない）と Update の間で共有する。lock で守る。
    private readonly object bufferLock = new object();
    private readonly Dictionary<string, double> latest = new Dictionary<string, double>();
    private bool hasNew;

    private readonly Dictionary<string, double> work = new Dictionary<string, double>();

    // 切り分け用ログを 1 回だけ出すためのフラグ（メインスレッドでのみ使う）。
    private bool loggedFirstMessage;
    private bool loggedFirstApply;

    void Start()
    {
        ros2Unity = GetComponent<ROS2UnityComponent>();
        CollectJoints();
        LogStartup();
    }

    private void LogStartup()
    {
        if (robotRoot != null)
        {
            bool inScene = robotRoot.gameObject.scene.IsValid();
            Debug.Log("JointStateSubscriber: robotRoot=" + robotRoot.name + " シーン内=" + inScene);
            if (!inScene)
            {
                Debug.LogWarning("JointStateSubscriber: robotRoot がシーンの中のオブジェクトではありません（プレハブのファイルなどを指している可能性があります）。");
            }
        }
        Debug.Log("JointStateSubscriber: 見つけた関節 " + bodies.Count + " 個: " + string.Join(", ", bodies.Keys));
        if (bodies.Count == 0)
        {
            Debug.LogWarning("JointStateSubscriber: 関節が 0 個です。");
        }
    }

    private void CollectJoints()
    {
        bodies.Clear();
        if (robotRoot == null)
        {
            Debug.LogWarning("JointStateSubscriber: robotRoot が設定されていません。");
            return;
        }
        foreach (UrdfJoint joint in robotRoot.GetComponentsInChildren<UrdfJoint>())
        {
            ArticulationBody body = joint.GetComponent<ArticulationBody>();
            if (body != null && !string.IsNullOrEmpty(joint.jointName))
            {
                bodies[joint.jointName] = body;
            }
        }
    }

    void Update()
    {
        if (ros2Node == null && ros2Unity != null && ros2Unity.Ok())
        {
            ros2Node = ros2Unity.CreateNode(nodeName);
            jointSub = ros2Node.CreateSubscription<sensor_msgs.msg.JointState>(topicName, OnJointState);
        }

        work.Clear();
        lock (bufferLock)
        {
            if (!hasNew)
            {
                return;
            }
            foreach (KeyValuePair<string, double> pair in latest)
            {
                work[pair.Key] = pair.Value;
            }
            hasNew = false;
        }

        if (!loggedFirstMessage)
        {
            loggedFirstMessage = true;
            Debug.Log("JointStateSubscriber: 最初のメッセージの関節 " + work.Count + " 個: " + string.Join(", ", work.Keys));
        }

        int appliedCount = 0;
        string sampleName = null;
        ArticulationBody sampleBody = null;
        double sampleValue = 0;

        foreach (KeyValuePair<string, double> pair in work)
        {
            if (bodies.TryGetValue(pair.Key, out ArticulationBody body))
            {
                Apply(body, pair.Value);
                appliedCount++;
                if (sampleBody == null)
                {
                    sampleName = pair.Key;
                    sampleBody = body;
                    sampleValue = pair.Value;
                }
            }
            else if (!IsMimic(pair.Key) && warnedNames.Add(pair.Key))
            {
                Debug.LogWarning("JointStateSubscriber: モデルにない関節名です: " + pair.Key);
            }
        }

        // drive_joint があり、mimic 関節がメッセージにない場合は、drive_joint の値（倍率 1）を反映する。
        if (work.TryGetValue(DriveJointName, out double driveValue))
        {
            foreach (string mimic in mimicJoints)
            {
                if (!work.ContainsKey(mimic) && bodies.TryGetValue(mimic, out ArticulationBody body))
                {
                    Apply(body, driveValue);
                }
            }
        }

        if (!loggedFirstApply)
        {
            loggedFirstApply = true;
            if (sampleBody == null)
            {
                Debug.Log("JointStateSubscriber: 最初の反映: 反映した関節は " + appliedCount + " 個（メッセージの関節名がモデルと一致しません）");
            }
            else
            {
                Debug.Log("JointStateSubscriber: 最初の反映: " + appliedCount + " 個。例 " + sampleName
                    + " 値(rad)=" + sampleValue
                    + " jointPosition[0]=" + sampleBody.jointPosition[0]
                    + " xDrive.target=" + sampleBody.xDrive.target);
            }
        }
    }

    // 受信スレッドで呼ばれる。Unity の API は呼ばず、バッファに写すだけにする。
    private void OnJointState(sensor_msgs.msg.JointState msg)
    {
        if (msg == null || msg.Name == null || msg.Position == null)
        {
            return;
        }
        int count = Mathf.Min(msg.Name.Length, msg.Position.Length);
        lock (bufferLock)
        {
            for (int i = 0; i < count; i++)
            {
                latest[msg.Name[i]] = msg.Position[i];
            }
            hasNew = true;
        }
    }

    private bool IsMimic(string jointName)
    {
        return mimicJoints.Contains(jointName);
    }

    private static void Apply(ArticulationBody body, double radians)
    {
        if (body.jointType == ArticulationJointType.FixedJoint || body.dofCount < 1)
        {
            return;
        }
        float rad = (float)radians;
        body.jointPosition = new ArticulationReducedSpace(rad);
        ArticulationDrive drive = body.xDrive;
        drive.target = rad * Mathf.Rad2Deg;
        body.xDrive = drive;
    }
}

}  // namespace DigitalTwin
