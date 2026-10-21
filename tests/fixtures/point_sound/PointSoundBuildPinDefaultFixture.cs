using System;

internal static class PointSoundBuildPinDefaultFixture
{
    private static int Main()
    {
        if (GameAudioOriginalOwner.PointSoundDiagnosticBuildRefusal(false) != null ||
            GameAudioOriginalOwner.PointSoundDiagnosticBuildRefusal(true) == null)
            throw new InvalidOperationException("ordinary build must refuse an explicitly selected instrumented diagnostic");
        Console.WriteLine("ordinary build pin refuses point-sound selector");
        return 0;
    }
}
