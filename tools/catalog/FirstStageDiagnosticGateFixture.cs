#if UNITY_EDITOR
using System;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine.Networking;

// Exercises only the production pure decision gates. It creates no Unity objects,
// invokes no lifecycle callback, and makes no claim about Stage/network behavior.
public static class FirstStageDiagnosticGateFixture
{
    static Type gateType;

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("First-stage diagnostic gate fixture failed: " + message);
    }

    static bool Gate(string methodName, params object[] arguments)
    {
        if (gateType == null)
        {
            var assembly =
                AppDomain.CurrentDomain.GetAssemblies().SingleOrDefault(candidate => candidate.GetName().Name == "Assembly-CSharp");
            Require(assembly != null, "Authored runtime assembly is not loaded");
            gateType = assembly.GetType("LabPort.SourceStageLifecycle.FirstStageDiagnosticGate", false);
            Require(gateType != null, "Production diagnostic gate type is missing");
        }
        var method = gateType.GetMethod(methodName, BindingFlags.Static | BindingFlags.NonPublic);
        Require(method != null, "Production gate method is missing: " + methodName);
        try
        {
            return (bool)method.Invoke(null, arguments);
        }
        catch (TargetInvocationException exception) when (exception.InnerException != null)
        {
            throw exception.InnerException;
        }
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active,
                "Run the pure contract fixture in an idle editor without a network session");

        Require(!Gate("Requested", true, false), "native diagnostic request must remain default-off");
        Require(!Gate("Enabled", false, true, "golemplains"), "request requires integrated-world path");
        Require(Gate("Enabled", true, true, "golemplains"), "supported Golemplains selection refused");
        Require(Gate("Enabled", true, true, "lakes"), "supported Lakes selection refused");
        Require(!Gate("Enabled", true, true, "blackbeach"), "unsupported stage enabled");
        Require(Gate("RefuseUnsupported", true, true, "blackbeach"), "explicit unsupported stage must refuse rather than fall back");

        Require(Gate("HasExactStageCapture", true, true, true, true, 17u, 17u, true), "exact capture proof was refused");
        Require(!Gate("HasExactStageCapture", false, true, true, true, 17u, 17u, true),
                "failed capture callback passed despite otherwise matching fields");
        Require(!Gate("HasExactStageCapture", true, true, true, true, 17u, 18u, true), "changed network ID passed capture");
        Require(!Gate("HasExactStageCapture", true, true, true, true, 17u, 17u, false), "missing exact server-map proof passed capture");

        Require(Gate("IsAssisted", true, false, false), "native lifecycle attempt must be assisted when all other assists are off");
        Require(!Gate("NormalAcceptanceEligible", true, false, false), "native lifecycle attempt must not qualify for normal acceptance");
        Require(Gate("NormalAcceptanceEligible", false, false, false), "ordinary unassisted attempt lost normal acceptance eligibility");

        Require(Gate("MayDisarmPopulationObserver", false, false, true, true),
                "completed pre-start abort with empty queues should disarm its observer");
        Require(!Gate("MayDisarmPopulationObserver", true, false, true, true), "started incomplete population must remain retained");
        Require(!Gate("MayDisarmPopulationObserver", false, false, false, true), "observer disarmed without completed exact abort");
        Require(!Gate("MayDisarmPopulationObserver", false, false, true, false), "observer disarmed while native queues are nonempty");

        return new { productionGate = "LabPort.SourceStageLifecycle.FirstStageDiagnosticGate",
                     defaultOffAndSceneSelection = true,
                     exactStageCaptureAndMappingRefusals = true,
                     diagnosticAssistedProvenance = true,
                     preStartAbortVersusPartialPopulation = true,
                     unityLifecycleOrStageExecutionClaimed = false };
    }
}
#endif
