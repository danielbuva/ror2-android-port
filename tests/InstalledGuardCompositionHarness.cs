using System;
using System.Reflection;

internal static class InstalledGuardCompositionHarness
{
    private static int assertions;
    private static void Check(bool condition, string message)
    {
        assertions++;
        if (!condition) throw new InvalidOperationException(message);
    }

    public static int Main()
    {
        var lease = new NativeWwiseMonitorLease { CaptureRegisterAttempted = true, CaptureRegistered = true };
        var window = new PassivePcmCaptureWindow(lease, true,
            InstalledApiCoreFields.Install, InstalledApiCoreFields.Read, error => { });
        typeof(PassivePcmCaptureWindow).GetField("registrationOwned", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(window, true);
        typeof(PassivePcmCaptureWindow).GetField("baseline", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(window, new NativeWwiseDiagSnapshot());
        var closed = typeof(PassivePcmCaptureWindow).GetField("closed", BindingFlags.Instance | BindingFlags.NonPublic);
        bool participantSawPcmGuardComplete = false;
        window.RegisterBeforeEngineTermParticipant(() =>
        {
            participantSawPcmGuardComplete = (bool)closed.GetValue(window) &&
                lease.UnregisterCalls == 1 && lease.CaptureUnregisterCallSucceeded && !lease.CaptureRegistered;
        });
        var installed = InstalledApiCoreFields.Read();
        Check(installed != null && Object.ReferenceEquals(installed, InstalledApiCoreFields.ApiBeforeEngineTerm),
            "window did not install the exact API/Core callback");
        InstalledApiCoreFields.InvokeApiTermGuard();
        Check(participantSawPcmGuardComplete, "music did not run after the passive PCM callback was removed");
        Check(Object.ReferenceEquals(installed, InstalledApiCoreFields.Read()), "music registration replaced the installed guard");

        InstalledApiCoreFields.ApiBeforeEngineTerm = null;
        InstalledApiCoreFields.CoreBeforeEngineTerm = null;
        var refusingWindow = new PassivePcmCaptureWindow(new NativeWwiseMonitorLease(), true,
            InstalledApiCoreFields.Install, InstalledApiCoreFields.Read, error => { });
        refusingWindow.RegisterBeforeEngineTermParticipant(() => throw new InvalidOperationException("music refusal"));
        var refusingGuard = InstalledApiCoreFields.Read();
        bool refused = false;
        bool termContinued = false;
        try
        {
            InstalledApiCoreFields.InvokeApiTermGuard();
            termContinued = true;
        }
        catch (InvalidOperationException error) { refused = error.Message == "music refusal"; }
        Check(refused, "music refusal did not propagate through the API/Core-installed guard");
        Check(!termContinued, "Term continuation occurred after music refused cleanup");
        Check(Object.ReferenceEquals(refusingGuard, InstalledApiCoreFields.Read()), "refusal changed API/Core delegate ownership");
        Console.WriteLine("PASS: " + assertions + " assertions against the actual passive window callback");
        return 0;
    }
}
