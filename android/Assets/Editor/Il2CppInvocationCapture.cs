using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

public class Il2CppInvocationCapture : IPreprocessBuildWithReport
{
    public int callbackOrder => 0;

    [Serializable]
    sealed class Capture
    {
        public string schema = "ror2lab-il2cpp-invocation-v1";
        public string platform = "android";
        public string architecture = "x86_64";
        public string unityVersion;
        public string rawArguments = "--compile-cpp --build-configuration=Release --architecture=x64";
        public string capturedAtUtc;
    }

    public void OnPreprocessBuild(BuildReport report)
    {
        if (report.summary.platform != BuildTarget.Android)
            return;
        Debug.Log("[Il2CppInvocationCapture] Configured for x86_64 (x64)");
    }
}
