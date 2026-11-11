using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class LabBuild {
    const string PendingBuild="PortingLab.X64Pending",RunningBuild="PortingLab.X64Running";
    static string IterationRequest,IterationOutput;
    static bool IterationCaptured;

    public static bool IsOwnedIterationCancellation(string[] messages,string request){
        string marker="ROR2LAB_ITERATION_EXPORT_COMPLETE "+request;
        return messages!=null&&messages.Any(message=>message.Contains(marker))&&messages.Count(message=>message=="Building Player failed")<=1&&messages.All(message=>message=="Building Player failed"||message.Contains(marker));
    }

    [Serializable] class Request {public string request_id,api,output,androidSymbols,iterationMode,bundleCompression;public bool presentationOnly,stagePresentation,reusePayload,captureIl2CppInvocation;public string[] reflectionTextureGuids;}
    [Serializable] class BuildPhase {public string name;public int depth;public double seconds;}
    [Serializable] class Result {public bool success; public string result,apk,backend,request_id,symbolPackage,build_report_guid,player_build_result;public string[] player_build_error_messages;public double seconds,bundle_seconds,player_seconds,prepare_seconds;public int errors,player_build_errors;public bool iteration_export_complete;public BuildPhase[] build_steps;}

    public static void CaptureIterationExport(string path){
        if(string.IsNullOrEmpty(IterationRequest))return;
        string project=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
        string expected=Path.Combine(project,"Library/Bee/Android/Prj/IL2CPP/Gradle");
        string actual=Path.GetFullPath(path);
        if(actual==Path.Combine(expected,"unityLibrary"))actual=expected;
        if(actual!=expected||!File.Exists(Path.Combine(actual,"unityLibrary/src/main/jniLibs/x86_64/libil2cpp.so"))||!File.Exists(Path.Combine(actual,"unityLibrary/src/main/assets/bin/Data/Managed/Metadata/global-metadata.dat")))throw new InvalidOperationException("Incomplete or unexpected x86_64 iteration export");
        IterationOutput=actual;IterationCaptured=true;
        throw new UnityEditor.Build.BuildFailedException("ROR2LAB_ITERATION_EXPORT_COMPLETE "+IterationRequest);
    }

    [MenuItem("Porting Lab/Record Backend Constraints")]
    public static void Backend(){
        var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
        File.WriteAllText(Path.Combine(root,"backend-evidence.json"),
"{\"editor\":\""+Application.unityVersion+"\",\"selectedBackend\":\""+PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android)+"\",\"architecture\":\""+PlayerSettings.Android.targetArchitectures+"\"}");
    }

    [MenuItem("Porting Lab/Build X86_64")]
    public static void QueueBuild(){
        Build();
    }

    public static void Build(){
        var root=Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));
        var cfg=JsonUtility.FromJson<Request>(File.ReadAllText(Path.Combine(root,"build-request.json")));
        var result=new Result{request_id=cfg.request_id,apk=cfg.output};
        string api=cfg.api??"vulkan";
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android,"dev.ror2lab.x86_64");
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android,ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures=AndroidArchitecture.X86_64;
        result.backend="IL2CPP X86_64 "+api;
        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/Lab.unity"},locationPathName=result.apk,target=BuildTarget.Android,options=BuildOptions.None});
        result.success=report.summary.result==BuildResult.Succeeded;
        File.WriteAllText(Path.Combine(root,"lab-build/result.json"),JsonUtility.ToJson(result,true));
    }
}

public sealed class LabIterationExport : UnityEditor.Android.IPostGenerateGradleAndroidProject {
    public int callbackOrder {get{return int.MaxValue;}}
    public void OnPostGenerateGradleAndroidProject(string path){LabBuild.CaptureIterationExport(path);}
}
