using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.UnityLinker;
using UnityEngine;

public sealed class PlayerLinkerInputCapture : IUnityLinkerProcessor
{
    [Serializable] sealed class Capture
    {
        public string schema = "ror2lab-unitylinker-input-v1";
        public string platform = "android";
        public string architecture = "x86_64";
    }

    public int callbackOrder => 0;

    public string GenerateAdditionalLinkXmlFile(BuildReport report, UnityLinkerBuildPipelineData data)
    {
        string path = Path.Combine(Application.temporaryCachePath, "inert-linker-input.xml");
        File.WriteAllText(path, "<linker/>");
        return path;
    }

    public void OnBeforeRun(BuildReport report, UnityLinkerBuildPipelineData data) { }
    public void OnAfterRun(BuildReport report, UnityLinkerBuildPipelineData data) { }
}
