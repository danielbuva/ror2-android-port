using System;
using System.IO;
using System.Reflection;
using UnityEngine;

// Adapter only: it loads the one packaged native library, selects the existing
// Android platform settings and owns monitor observation. The original game
// AkInitializer/engine remains the only Init, service and Term owner.
internal sealed class GameAudioOriginalAndroidNativeBootstrap : IGameAudioOriginalNativeBootstrap
{
    private readonly NativeWwiseMonitorLease monitor;
    private AkBasePathGetter.CustomPlatformNameGetter priorPlatformName;
    private AkBasePathGetter.CustomPlatformNameGetter ownedPlatformName;
    private bool loadAttempted;
    private bool loaded;
    private bool resolverAttempted;
    private bool resolverInstalled;
    private bool originalInitAttemptCommitted;
    private bool preInitAbandonAttempted;

    internal GameAudioOriginalAndroidNativeBootstrap(NativeWwiseMonitorLease lease)
    {
        monitor = lease ?? throw new ArgumentNullException(nameof(lease));
    }

    public bool EnsureNativeLibraryLoaded
    {
        get
        {
            if (loaded) return true;
            if (loadAttempted) return false;
            loadAttempted = true;
#if UNITY_ANDROID && !UNITY_EDITOR
            using (var javaSystem = new AndroidJavaClass("java.lang.System"))
                javaSystem.CallStatic("loadLibrary", "AkSoundEngine");
            // This is only a truthful native-query safety gate. It is deliberately
            // independent of readiness so the original engine can observe an
            // initialization failure and execute its own Term path.
            GameAudioOriginalOwner.RecordNativeLibraryLoaded();
            loaded = true;
            return true;
#else
            return false;
#endif
        }
    }

    public bool InstallAndroidResolver
    {
        get
        {
            if (resolverInstalled) return true;
            if (resolverAttempted) return false;
            resolverAttempted = true;
            RequireUncachedSettings();
            var settingsProvider = GameAudioOriginalRequestBootstrap.OriginalSettingsProvider;
            if (settingsProvider == null)
                throw new InvalidOperationException("Original whole-catalog settings provider was not installed by PortSession.");
            // Load the original GUID-bound object from the already-active content
            // bundle. Resources.Load would duplicate the asset that WholeCatalog
            // also bundles and WwiseGlobal references.
            AkWwiseInitializationSettings settings = settingsProvider();
            if (settings == null || !object.ReferenceEquals(AkWwiseInitializationSettings.Instance, settings))
                throw new InvalidOperationException("The staged original settings resource did not establish the Wwise singleton.");
            if (settings == null || !settings.IsValid || settings.PlatformSettingsNameList == null ||
                settings.PlatformSettingsList == null || settings.PlatformSettingsNameList.Count != settings.PlatformSettingsList.Count)
                throw new InvalidOperationException("Original Wwise platform settings asset is absent or invalid.");

            int androidEntries = 0;
            for (int i = 0; i < settings.PlatformSettingsNameList.Count; i++)
            {
                if (String.Equals(settings.PlatformSettingsNameList[i], "Android", StringComparison.OrdinalIgnoreCase))
                {
                    androidEntries++;
                    if (settings.PlatformSettingsList[i] == null)
                        throw new InvalidOperationException("The original Android platform settings entry has no settings object.");
                }
            }
            if (androidEntries > 1)
                throw new InvalidOperationException("The original Wwise settings contain duplicate Android platform entries.");

            priorPlatformName = AkBasePathGetter.GetCustomPlatformName;
            if (priorPlatformName != null)
            {
                string selected = String.Empty;
                priorPlatformName(ref selected);
                if (!String.IsNullOrEmpty(selected) &&
                    !String.Equals(selected, "Android", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("An existing Wwise resolver selects a non-Android platform.");
            }
            ownedPlatformName = (ref string name) =>
            {
                priorPlatformName?.Invoke(ref name);
                if (!String.IsNullOrEmpty(name) &&
                    !String.Equals(name, "Android", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("The original Wwise resolver selected a non-Android platform.");
                name = "Android";
            };
            try
            {
                AkBasePathGetter.GetCustomPlatformName = ownedPlatformName;
                if (!String.Equals(AkBasePathGetter.GetPlatformName(), "Android", StringComparison.Ordinal))
                    throw new InvalidOperationException("Wwise did not select Android or its documented global-settings fallback.");
                if (String.IsNullOrWhiteSpace(Application.persistentDataPath) ||
                    !System.IO.Path.IsPathRooted(Application.persistentDataPath))
                    throw new InvalidOperationException("Unity app-private persistent bank search root is unavailable.");
                resolverInstalled = true;
                return true;
            }
            catch
            {
                AbandonBeforeOriginalInit();
                throw;
            }
        }
    }

    public void ArmNativeMonitorBeforeExistingInit()
    {
        if (!loaded || !resolverInstalled)
            throw new InvalidOperationException("Native library and Android resolver must be ready before monitor arm.");
        monitor.ArmBeforeInit();
    }

    public void MarkNativeEngineInitAttempted()
    {
        if (!loaded || !resolverInstalled || !monitor.Armed)
            throw new InvalidOperationException("Native monitor must be armed before the original Init marker.");
        monitor.MarkEngineInitAttempted();
        originalInitAttemptCommitted = true;
    }

    public void AbandonBeforeOriginalInit()
    {
        if (originalInitAttemptCommitted || preInitAbandonAttempted) return;
        preInitAbandonAttempted = true;
        Exception disarmFailure = null;
        try
        {
            if (monitor.Armed) monitor.DisarmBeforeInit();
        }
        catch (Exception error) { disarmFailure = error; }
        try
        {
            if (ownedPlatformName != null &&
                object.ReferenceEquals(AkBasePathGetter.GetCustomPlatformName, ownedPlatformName))
                AkBasePathGetter.GetCustomPlatformName = priorPlatformName;
            else if (ownedPlatformName != null && resolverInstalled)
                throw new InvalidOperationException("The installed Wwise platform resolver changed before original Init; refusing to overwrite another owner.");
            ownedPlatformName = null;
            resolverInstalled = false;
        }
        catch (Exception restoreError)
        {
            if (disarmFailure != null)
                throw new AggregateException("Pre-Init monitor disarm and resolver restore both failed.", disarmFailure, restoreError);
            throw;
        }
        if (disarmFailure != null)
            throw new InvalidOperationException("Pre-Init native monitor disarm failed; resolver was restored.", disarmFailure);
    }

    public void PostExactControlMarker()
    {
        monitor.BeginPostInitControlObservation();
    }

    public bool ExactControlMarkerObserved
    {
        get
        {
            if (!monitor.PostInitControlAttempted) return false;
            monitor.PollPostInitControl();
            return monitor.PostInitControlObserved;
        }
    }

    public bool NativeControlObservationFailed { get { return monitor.OutcomeUnknown; } }

    public string PersistentBankRoot
    {
        get
        {
            if (!resolverInstalled) throw new InvalidOperationException("Android Wwise settings must be selected before reading the bank path.");
            return ResolvePersistentBankRoot(Application.persistentDataPath,
                AkWwiseInitializationSettings.ActivePlatformSettings.SoundBankPersistentDataPath);
        }
    }

    internal static string ResolvePersistentBankRoot(string persistentDataPath, string subfolder)
    {
        if (String.IsNullOrWhiteSpace(persistentDataPath))
            throw new InvalidOperationException("Unity app-private persistent bank search root is unavailable.");
        string persistent = Path.GetFullPath(persistentDataPath);
        string relative = (subfolder ?? String.Empty).Replace('\\', '/');
        if (Path.IsPathRooted(relative) || relative.IndexOf(':') >= 0)
            throw new InvalidOperationException("Original Android SoundBankPersistentDataPath must be a relative path.");
        foreach (string segment in relative.Split('/'))
            if (segment == "." || segment == "..")
                throw new InvalidOperationException("Original Android SoundBankPersistentDataPath escapes app-private storage.");
        string combined = Path.GetFullPath(Path.Combine(persistent, relative.Replace('/', Path.DirectorySeparatorChar)));
        string prefix = persistent.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!String.Equals(combined, persistent, StringComparison.Ordinal) &&
            !combined.StartsWith(prefix, StringComparison.Ordinal))
            throw new InvalidOperationException("Original Android bank path escapes app-private storage.");
        return combined;
    }

    public void ObserveEngineTermReturned()
    {
        if (!monitor.EngineInitAttempted || monitor.EngineTermReturnedState) return;
        monitor.RecordEngineTermReturned();
    }

    public void ObserveCallbackManagerTermReturned()
    {
        if (!monitor.EngineTermReturnedState || monitor.CallbackManagerTermReturnedState) return;
        monitor.RecordCallbackManagerTermReturned();
        monitor.DisarmAfterReturnedTerms();
    }

    private static void RequireUncachedSettings()
    {
        FieldInfo active = typeof(AkWwiseInitializationSettings).GetField("m_ActivePlatformSettings",
            BindingFlags.Static | BindingFlags.NonPublic);
        FieldInfo basePath = typeof(AkBasePathGetter).GetField("Instance",
            BindingFlags.Static | BindingFlags.NonPublic);
        if (active == null || basePath == null || active.GetValue(null) != null || basePath.GetValue(null) != null)
            throw new InvalidOperationException("Wwise platform or base-path settings were cached before Android selection.");
    }
}
