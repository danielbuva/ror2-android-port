// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup AwaitOfflineRunStart (OfflineApplicationSession); teardown — (Dispose is a no-op).
using System;
using System.Collections;
using System.IO;
using System.Linq;
using RoR2;
using UnityEngine;

// Owned Android application flow around the original composed simulation.
// This screen is not the stock menu and creates no platform user or stock profile.
public sealed partial class PortSession
{
    // Shared with survivor/loadout UI, recovered HUD, settings and session restart.
    bool offlineStartVisible, offlineStartSelected, returnToOfflineMenu;
    Vector2 offlineRosterScroll;
    SurvivorDef[] offlineMenuRoster, offlineMenuChoices;
    DifficultyIndex offlineDifficulty = DifficultyIndex.Easy;
    public bool skipOfflineMenu;
    OfflineApplicationSession offlineApplicationSession;
    OfflineApplicationSession GetOfflineApplicationSession()
    {
        if (offlineApplicationSession == null)
            offlineApplicationSession = new OfflineApplicationSession(this);
        return offlineApplicationSession;
    }
    DifficultyIndex SelectedOfflineDifficulty()
    {
        return GetOfflineApplicationSession().SelectedOfflineDifficulty();
    }
    string OfflineDifficultyName()
    {
        return GetOfflineApplicationSession().OfflineDifficultyName();
    }
    void CycleOfflineDifficulty(int direction = 1)
    {
        GetOfflineApplicationSession().CycleOfflineDifficulty(direction);
    }
    bool OfflineUiControllerPresent()
    {
        return GetOfflineApplicationSession().OfflineUiControllerPresent();
    }
    void OnApplicationFocus(bool focused)
    {
        GetOfflineApplicationSession().OnApplicationFocus(focused);
    }
    void OnApplicationPause(bool paused)
    {
        GetOfflineApplicationSession().OnApplicationPause(paused);
    }
    static bool AllowsOfflineSessionMenu(SessionReport session)
    {
        return OfflineApplicationSession.AllowsOfflineSessionMenu(session);
    }
    IEnumerator AwaitOfflineRunStart(SessionConfig cfg)
    {
        return GetOfflineApplicationSession().AwaitOfflineRunStart(cfg);
    }
    void ObserveOfflineApplicationInput()
    {
        GetOfflineApplicationSession().ObserveOfflineApplicationInput();
    }
    bool DrawOfflineStart()
    {
        return GetOfflineApplicationSession().DrawOfflineStart();
    }
    void RequestResultsMenu()
    {
        GetOfflineApplicationSession().RequestResultsMenu();
    }
    bool CompletedResultsReturn()
    {
        return GetOfflineApplicationSession().CompletedResultsReturn();
    }
    bool CanAbandonOfflineRun()
    {
        return GetOfflineApplicationSession().CanAbandonOfflineRun();
    }
    void RequestAbandonOfflineRun()
    {
        GetOfflineApplicationSession().RequestAbandonOfflineRun();
    }
    bool CompletedOfflineAbandon()
    {
        return GetOfflineApplicationSession().CompletedOfflineAbandon();
    }

    // Retain the owner for menu input, focus/pause callbacks and result/restart
    // queries. Menu cleanup stays in the iterator; Dispose does not reset flow state.
    sealed class OfflineApplicationSession : IDisposable
    {
        readonly PortSession coordinator;
        bool offlineSurvivorStickLatched, offlineDifficultyStickLatched;
        string pendingOfflineSurvivor = "Commando";
        NovaInputBridge.Mapping offlineMenuMapping;
        NovaInputBridge.ControllerPresence offlineUiPresence;
        public OfflineApplicationSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public DifficultyIndex SelectedOfflineDifficulty()
        {
            coordinator.Check(coordinator.offlineDifficulty >= DifficultyIndex.Easy &&
                                  coordinator.offlineDifficulty <= DifficultyIndex.Hard,
                              "Unsupported original offline difficulty");
            return coordinator.offlineDifficulty;
        }
        public string OfflineDifficultyName()
        {
            switch (SelectedOfflineDifficulty())
            {
            case DifficultyIndex.Easy:
                return "Drizzle";
            case DifficultyIndex.Normal:
                return "Rainstorm";
            default:
                return "Monsoon";
            }
        }
        public void CycleOfflineDifficulty(int direction = 1)
        {
            coordinator.offlineDifficulty =
                direction < 0
                    ? (coordinator.offlineDifficulty == DifficultyIndex.Easy ? DifficultyIndex.Hard : coordinator.offlineDifficulty - 1)
                    : (coordinator.offlineDifficulty == DifficultyIndex.Hard ? DifficultyIndex.Easy : coordinator.offlineDifficulty + 1);
            if (coordinator.offlineSettings != null)
            {
                coordinator.offlineSettings.values.offlineDifficulty = (int)coordinator.offlineDifficulty;
                coordinator.offlineSettings.Save();
            }
            if (coordinator.r.hud != null)
                coordinator.r.hud.menuDifficulty = coordinator.offlineDifficulty.ToString();
            coordinator.Save();
        }
        public bool OfflineUiControllerPresent()
        {
            var map = offlineMenuMapping ?? (coordinator.r != null && coordinator.r.nova != null ? coordinator.r.nova.mapping : null);
            if (map == null)
            {
                offlineUiPresence?.Suspend();
                return false;
            }
            var names = UnityEngine.Input.GetJoystickNames();
            if (names.Length == 0 || string.IsNullOrEmpty(names[0]) || names.Skip(1).Any(name => !string.IsNullOrEmpty(name)))
            {
                offlineUiPresence?.Suspend();
                return false;
            }
            if (offlineUiPresence == null)
                offlineUiPresence = new NovaInputBridge.ControllerPresence(names[0]);
            var raw = NovaInputBridge.ReadRaw();
            bool neutral = raw.buttons.All(down => !down) &&
                           new[] { map.moveX, map.moveY, map.aimX, map.aimY }.All(axis => Mathf.Abs(raw.axes[axis]) <=
                                                                                          AndroidOfflineSettings.current.deadzone);
            return offlineUiPresence.Observe(names, neutral, Time.realtimeSinceStartup);
        }
        public void OnApplicationFocus(bool focused)
        {
            if (!focused)
                offlineUiPresence?.Suspend();
        }
        public void OnApplicationPause(bool paused)
        {
            if (paused)
                offlineUiPresence?.Suspend();
        }
        public static bool AllowsOfflineSessionMenu(SessionReport session)
        {
            return session != null && (session.freePlay || session.recoveredHudEnabled && session.id != null &&
                                                               session.id.EndsWith("-bringup", System.StringComparison.Ordinal));
        }
        public IEnumerator AwaitOfflineRunStart(SessionConfig cfg)
        {
            if (cfg.integratedWorld && cfg.integratedResults)
                coordinator.PrepareOfflineSettings();
            if (string.IsNullOrEmpty(coordinator.r.selectedSurvivor))
                coordinator.r.selectedSurvivor = pendingOfflineSurvivor;
            // A developer-only survivor override is never shown as an earned menu choice.
            if (!AllowsOfflineSessionMenu(coordinator.r) || !cfg.integratedWorld || !cfg.integratedResults || coordinator.skipOfflineMenu ||
                coordinator.r.developerSurvivorOverride)
                yield break;
            coordinator.offlineUnlockPreview = null;
            var choices = coordinator.OrdinarySurvivorChoices();
            var roster = coordinator.VisibleSurvivorRoster();
            coordinator.Check(choices.All(roster.Contains), "Selectable survivor absent from original visible roster");
            coordinator.offlineMenuRoster = roster;
            coordinator.offlineMenuChoices = choices;
            coordinator.offlineRosterScroll = Vector2.zero;
            coordinator.offlineLoadoutScroll = Vector2.zero;
            offlineSurvivorStickLatched = false;
            offlineDifficultyStickLatched = false;
            coordinator.offlinePendingLoadout =
                AndroidOfflineProfile.PreviewLoadout(System.IO.Path.Combine(Application.persistentDataPath, "android-profile-v1"));
            coordinator.offlineLoadoutEdited = false;
            coordinator.offlineLoadoutVisible = false;
            if (coordinator.r.hud != null)
            {
                coordinator.r.hud.survivorRosterCount = roster.Length;
                coordinator.r.hud.survivorSelectableCount = choices.Length;
                coordinator.r.hud.menuDifficulty = coordinator.offlineDifficulty.ToString();
            }
            if (!choices.Any(value => value.cachedName == coordinator.r.selectedSurvivor))
                coordinator.r.selectedSurvivor = choices[0].cachedName;
            if (coordinator.IsNovaInput())
            {
                var mode = InputSessionPolicy.Resolve(PortSession.CurrentDeviceModel(),
                                                     coordinator.r.id != null && coordinator.r.id.EndsWith("-bringup", StringComparison.Ordinal));
                coordinator.Check(mode != InputSessionPolicy.Mode.RefuseUnmeasuredPhysicalInput,
                                  "Unmeasured physical input is unavailable outside Nova or an explicit Thor bringup diagnostic");
            }
            if (coordinator.UsesDiagnosticWithoutPhysicalInput())
                offlineMenuMapping = null;
            else
            {
                offlineMenuMapping = JsonUtility.FromJson<NovaInputBridge.Mapping>(
                    File.ReadAllText(System.IO.Path.Combine(Application.persistentDataPath, "nova-input-mapping.json")));
                offlineMenuMapping.Validate(coordinator.r.attempt);
            }
            coordinator.PrepareRecoveredMenu();
            coordinator.offlineStartVisible = true;
            coordinator.r.phase = "offline-start-menu";
            coordinator.Save();
            while (!coordinator.offlineStartSelected)
                yield return null;
            coordinator.offlineStartVisible = false;
            coordinator.CleanupRecoveredMenu();
            coordinator.offlineMenuRoster = null;
            coordinator.offlineMenuChoices = null;
            coordinator.offlineLoadoutVisible = false;
            pendingOfflineSurvivor = coordinator.r.selectedSurvivor;
            coordinator.SelectedPlayerPrefab(cfg);
            coordinator.r.phase = "started";
            coordinator.Save();
        }
        public void ObserveOfflineApplicationInput()
        {
            // Settings owns this frame even if its Back action closes the screen.
            // Hidden start-menu controls must not consume the same A/stick input.
            if (coordinator.offlineSettingsVisible)
            {
                coordinator.ObserveOfflineSettingsControllerInput();
                return;
            }
            if (coordinator.offlineStartVisible)
            {
                if (offlineMenuMapping != null && OfflineUiControllerPresent())
                {
                    var raw = NovaInputBridge.ReadRaw();
                    var horizontal = raw.axes[offlineMenuMapping.moveX];
                    if (Mathf.Abs(horizontal) < .3f)
                        offlineSurvivorStickLatched = false;
                    else if (!offlineSurvivorStickLatched && Mathf.Abs(horizontal) > .65f)
                    {
                        coordinator.CycleOrdinarySurvivor(horizontal > 0 ? 1 : -1);
                        offlineSurvivorStickLatched = true;
                    }
                    var difficulty = raw.axes[offlineMenuMapping.aimX];
                    if (Mathf.Abs(difficulty) < .3f)
                        offlineDifficultyStickLatched = false;
                    else if (!offlineDifficultyStickLatched && Mathf.Abs(difficulty) > .65f)
                    {
                        CycleOfflineDifficulty(difficulty > 0 ? 1 : -1);
                        offlineDifficultyStickLatched = true;
                    }
                    if (UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0 + offlineMenuMapping.jump)))
                        coordinator.offlineStartSelected = true;
                }
                else
                {
                    offlineSurvivorStickLatched = false;
                    offlineDifficultyStickLatched = false;
                }
                return;
            }
            coordinator.ObserveOfflineSettingsControllerInput();
            if (coordinator.r != null && coordinator.r.phase != "commando-defeated" && coordinator.r.freePlay &&
                coordinator.r.results != null && coordinator.r.results.persisted && coordinator.r.nova != null &&
                coordinator.r.nova.mapping != null && coordinator.r.nova.physicalInputAvailable &&
                !coordinator.offlineSettingsVisible && OfflineUiControllerPresent() &&
                UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0 + coordinator.r.nova.mapping.jump)))
                RequestResultsMenu();
        }
        public bool DrawOfflineStart()
        {
            if (!coordinator.offlineStartVisible)
                return false;
            var selected = string.IsNullOrEmpty(coordinator.r.selectedSurvivor) ? "Commando" : coordinator.r.selectedSurvivor;
            if (coordinator.recoveredMenu)
            {
                if (!coordinator.offlineLoadoutVisible)
                    coordinator.DrawOfflineSurvivorRoster(coordinator.offlineMenuRoster, coordinator.offlineMenuChoices);
                GUI.Box(new Rect(20, Screen.height - 156, 470, 88), "Selected survivor · Android profile");
                if (GUI.Button(new Rect(40, Screen.height - 127, 430, 48), selected + "  ◀  ▶"))
                    coordinator.CycleOrdinarySurvivor(1);
                GUI.Box(new Rect(500, Screen.height - 156, 270, 88), "Original difficulty rule");
                if (GUI.Button(new Rect(520, Screen.height - 127, 230, 48), OfflineDifficultyName() + "  ◀  ▶"))
                    CycleOfflineDifficulty();
                if (GUI.Button(new Rect(Screen.width - 205, Screen.height - 127, 185, 48),
                               coordinator.offlineLoadoutVisible ? "Close loadout" : "Loadout"))
                    coordinator.offlineLoadoutVisible = !coordinator.offlineLoadoutVisible;
                if (coordinator.offlineLoadoutVisible)
                    coordinator.DrawOfflineLoadout();
                GUI.Label(
                    new Rect(20, Screen.height - 58, Screen.width - 40, 55),
                    coordinator.UsesDiagnosticWithoutPhysicalInput()
                        ? "Touch controls: survivor, difficulty, and start · physical input unavailable · roster/UI rendering approximation"
                        : "Left stick: survivor · Right stick: difficulty · A: start · audio/Steam profiles unavailable · roster/UI rendering approximation");
                return true;
            }
            var style = new GUIStyle(GUI.skin.label) { fontSize = 30, wordWrap = true };
            GUI.Box(new Rect(20, 60, 860, 400), "Offline RoR2 composition");
            GUI.Label(
                new Rect(45, 100, 800, 220),
                selected + " · " + OfflineDifficultyName() +
                    (coordinator.UsesDiagnosticWithoutPhysicalInput()
                         ? "\nExplore, earn items, defeat each teleporter boss, then reach the Moon.\nUse the touch controls below; physical input is unavailable.\nOriginal profile data and results stay on this Android device. Audio and Steam/cloud profiles are unavailable."
                         : "\nExplore, earn items, defeat each teleporter boss, then reach the Moon.\nLeft stick: survivor · Right stick: difficulty · A: start.\nOriginal profile data and results stay on this Android device. Audio and Steam/cloud profiles are unavailable."),
                style);
            if (GUI.Button(new Rect(45, 270, 370, 55), "Survivor: " + selected + "  ◀  ▶"))
                coordinator.CycleOrdinarySurvivor(1);
            if (GUI.Button(new Rect(440, 270, 370, 55), "Difficulty: " + OfflineDifficultyName() + "  ◀  ▶"))
                CycleOfflineDifficulty();
            if (GUI.Button(new Rect(45, 340, 370, 65), coordinator.UsesDiagnosticWithoutPhysicalInput() ? "Start run" : "Start run (A)"))
                coordinator.offlineStartSelected = true;
            if (GUI.Button(new Rect(440, 340, 370, 65), "Quit"))
                Application.Quit();
            if (GUI.Button(new Rect(45, 415, 370, 45), coordinator.offlineLoadoutVisible ? "Close loadout" : "Loadout"))
                coordinator.offlineLoadoutVisible = !coordinator.offlineLoadoutVisible;
            if (coordinator.offlineLoadoutVisible)
                coordinator.DrawOfflineLoadout();
            return true;
        }
        public void RequestResultsMenu()
        {
            if (coordinator.r == null || !coordinator.r.freePlay || coordinator.r.results == null || !coordinator.r.results.persisted)
                return;
            coordinator.Check(coordinator.r.results.serverEnding && coordinator.r.results.clientEnding &&
                                  coordinator.r.results.reportReloaded,
                              "Return requested before original ending/report persistence");
            coordinator.returnToOfflineMenu = true;
            coordinator.restartRequested = true;
            coordinator.r.phase = "returning-to-offline-menu";
            coordinator.Save();
        }
        public bool CompletedResultsReturn()
        {
            return coordinator.returnToOfflineMenu && coordinator.r.results != null && coordinator.r.results.persisted &&
                   coordinator.r.results.clientEnding;
        }
        public bool CanAbandonOfflineRun()
        {
            return AllowsOfflineSessionMenu(coordinator.r) && coordinator.r.integratedWorld && coordinator.r.world != null &&
                   coordinator.r.world.ready && coordinator.worldPlayer && coordinator.worldPlayer.healthComponent.alive &&
                   coordinator.r.results != null && coordinator.r.results.ready && !coordinator.r.results.serverEnding &&
                   !coordinator.r.results.reportGenerated && !coordinator.r.results.persisted && !coordinator.restartRequested;
        }
        public void RequestAbandonOfflineRun()
        {
            if (!CanAbandonOfflineRun())
                return;
            // Leaving a local session is not an original game ending or a saved result.
            coordinator.Check(UnityEngine.Networking.NetworkServer.active && Run.instance, "Live offline session ownership absent");
            coordinator.ShowOfflineSettings(false);
            coordinator.r.settings.sessionAbandoned = true;
            coordinator.returnToOfflineMenu = true;
            coordinator.restartRequested = true;
            coordinator.r.phase = "abandoning-offline-session";
            coordinator.Save();
        }
        public bool CompletedOfflineAbandon()
        {
            return coordinator.returnToOfflineMenu && coordinator.r.settings != null && coordinator.r.settings.sessionAbandoned &&
                   coordinator.r.results != null && !coordinator.r.results.serverEnding && !coordinator.r.results.reportGenerated &&
                   !coordinator.r.results.persisted;
        }
        public void Dispose()
        {
        }
    }
}
