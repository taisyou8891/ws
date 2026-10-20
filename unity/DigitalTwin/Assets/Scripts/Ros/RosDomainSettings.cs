using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace DigitalTwin
{

/// <summary>
/// ROS_DOMAIN_ID を Inspector で指定する。ROS2UnityComponent より前に環境変数を設定する。
/// domainId が -1 のときは何もせず、環境変数をそのまま使う。
/// </summary>
[DefaultExecutionOrder(-1000)]
public class RosDomainSettings : MonoBehaviour
{
    private const string EnvName = "ROS_DOMAIN_ID";
    private const int MaxDomainId = 232;

    [SerializeField] private int domainId = -1;

    [DllImport("libc", EntryPoint = "setenv")]
    private static extern int setenv(string name, string value, int overwrite);

    private void Awake()
    {
        if (domainId == -1)
        {
            return;
        }

        if (domainId < 0 || domainId > MaxDomainId)
        {
            Debug.LogError($"domainId must be between 0 and {MaxDomainId} (or -1 to use the environment variable): {domainId}");
            return;
        }

        string value = domainId.ToString();
        Environment.SetEnvironmentVariable(EnvName, value);

        if (Application.platform == RuntimePlatform.LinuxEditor
            || Application.platform == RuntimePlatform.LinuxPlayer)
        {
            setenv(EnvName, value, 1);
        }

        Debug.Log($"{EnvName} set to {value}");
    }
}

}
