// Subsystem: input/camera (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup PrepareOfflineSettings (OfflineSettingsSession.Prepare); teardown CleanupOfflineSettingsPause (Dispose).
using System;
using System.IO;
using Path = System.IO.Path;
using RoR2;
using UnityEngine;

// Owned Android settings/pause screen around the composed local session.
public sealed partial class PortSession
{
    [Serializable]
    public class OfflineSettingsReport
    {
        public bool ready, visible, paused, persisted, canEndRun, sessionAbandoned;
        public bool endRunConfirmationVisible;
        public string recovery, error;
        public float deadzone, lookSensitivity, buttonX, buttonY, endRunButtonX, endRunButtonY, timeScale, runSeconds;
        public float confirmEndRunButtonX, confirmEndRunButtonY;
        public int fixedTicks, observations, screenWidth, screenHeight;
        public bool invertY;
        public int saves, pauses, resumes, controllerOpens, controllerCloses, controllerSaves;
    }
    // Shared with menu difficulty, results input and Nova input, respectively.
    AndroidOfflineSettings offlineSettings;
    bool offlineSettingsVisible, offlineSettingsPaused;
    OfflineSettingsSession offlineSettingsSession;
    void PrepareOfflineSettings()
    {
        if (offlineSettingsSession == null)
            offlineSettingsSession = new OfflineSettingsSession(this);
        offlineSettingsSession.Prepare();
    }
    void ShowOfflineSettings(bool show)
    {
        offlineSettingsSession?.Show(show);
    }
    void ObserveOfflineSettingsControllerInput()
    {
        offlineSettingsSession?.ObserveControllerInput();
    }
    bool DrawOfflineSettings()
    {
        return offlineSettingsSession != null && offlineSettingsSession.Draw();
    }
    void CleanupOfflineSettingsPause()
    {
        offlineSettingsSession?.Dispose();
    }
    bool SaveOfflineSettings()
    {
        return offlineSettingsSession != null && offlineSettingsSession.Save();
    }

    // Nested so the owner can use the coordinator's shared state and report without
    // widening their visibility. It retains the same lifetime as the settings store.
    sealed class OfflineSettingsSession : IDisposable
    {
        readonly PortSession coordinator;
        readonly AndroidFeedbackScreen feedback = new AndroidFeedbackScreen();
        bool confirmEndRun;
        float offlineSettingsTimeScale;
        public OfflineSettingsSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }
        public void Prepare()
        {
            if (coordinator.offlineSettings != null)
                return;
            coordinator.offlineSettings = new AndroidOfflineSettings(Path.Combine(Application.persistentDataPath, "offline-settings-v1"));
            AndroidOfflineSettings.current = coordinator.offlineSettings.values;
            coordinator.offlineDifficulty = (DifficultyIndex)coordinator.offlineSettings.values.offlineDifficulty;
            coordinator.r.settings = new OfflineSettingsReport { ready = true, recovery = coordinator.offlineSettings.recovery };
            Observe();
        }
        void Observe()
        {
            if (coordinator.offlineSettings == null)
                return;
            var v = coordinator.offlineSettings.values;
            var button = AndroidTouchInput.PauseGuiRect(Screen.width);
            coordinator.r.settings.buttonX = button.center.x;
            coordinator.r.settings.buttonY = button.center.y;
            coordinator.r.settings.screenWidth = Screen.width;
            coordinator.r.settings.screenHeight = Screen.height;
            coordinator.r.settings.deadzone = v.deadzone;
            coordinator.r.settings.lookSensitivity = v.lookSensitivity;
            coordinator.r.settings.invertY = v.invertY;
            coordinator.r.settings.visible = coordinator.offlineSettingsVisible;
            coordinator.r.settings.paused = coordinator.offlineSettingsPaused;
            coordinator.r.settings.endRunConfirmationVisible = confirmEndRun;
            coordinator.r.settings.confirmEndRunButtonX = Screen.width * .5f - 115;
            coordinator.r.settings.confirmEndRunButtonY = Screen.height * .5f + 42.5f;
            coordinator.r.settings.timeScale = Time.timeScale;
            coordinator.r.settings.runSeconds = Run.instance ? Run.instance.GetRunStopwatch() : 0;
            coordinator.r.settings.fixedTicks = coordinator.r.runClock == null ? 0 : coordinator.r.runClock.fixedTicks;
        }
        public void Show(bool show)
        {
            if (coordinator.offlineSettings == null)
                return;
            if (show == coordinator.offlineSettingsVisible)
                return;
            confirmEndRun = false;
            if (!show)
                feedback.Close();
            if (show && coordinator.worldPause && coordinator.worldPlayer && coordinator.worldPlayer.healthComponent.alive)
            {
                coordinator.Check(PauseStopController.instance && !PauseStopController.instance.isPaused && Time.timeScale > 0,
                                  "Unowned pause state");
                offlineSettingsTimeScale = Time.timeScale;
                PauseStopController.instance.NetworkisPaused = true;
                Time.timeScale = 0;
                coordinator.offlineSettingsPaused = true;
                coordinator.r.settings.pauses++;
                var bridge = coordinator.worldPlayer.GetComponent<NovaInputBridge>();
                if (bridge)
                    bridge.Neutral();
            }
            if (!show && coordinator.offlineSettingsPaused)
            {
                coordinator.Check(PauseStopController.instance && PauseStopController.instance.isPaused && Time.timeScale == 0,
                                  "Owned pause context changed");
                PauseStopController.instance.NetworkisPaused = false;
                Time.timeScale = offlineSettingsTimeScale;
                coordinator.offlineSettingsPaused = false;
                coordinator.r.settings.resumes++;
            }
            coordinator.SetRecoveredMenuObscured(show);
            coordinator.offlineSettingsVisible = show;
            Observe();
            coordinator.Save();
        }
        public bool Save()
        {
            bool saved = coordinator.offlineSettings.TrySave();
            coordinator.r.settings.error = coordinator.offlineSettings.saveError;
            coordinator.r.settings.persisted = saved;
            if (saved)
            {
                AndroidOfflineSettings.current = coordinator.offlineSettings.values;
                coordinator.r.settings.saves++;
            }
            Observe();
            coordinator.Save();
            return saved;
        }
        public void ObserveControllerInput()
        {
            if (coordinator.offlineSettings == null || coordinator.r == null || !coordinator.r.freePlay ||
                !coordinator.OfflineUiControllerPresent())
                return;
            // J151 measured Xbox B as Unity slot-1 button 1. This is only the Nova
            // adapter's menu/back action; it does not alter the original input bank.
            if (UnityEngine.Input.GetKeyDown(KeyCode.Joystick1Button1))
            {
                if (feedback.Visible)
                {
                    feedback.Close();
                    return;
                }
                if (confirmEndRun)
                {
                    confirmEndRun = false;
                    Observe();
                    coordinator.Save();
                    return;
                }
                if (coordinator.offlineSettingsVisible)
                {
                    coordinator.r.settings.controllerCloses++;
                    Show(false);
                }
                else if (coordinator.CanAbandonOfflineRun())
                {
                    coordinator.r.settings.controllerOpens++;
                    Show(true);
                }
            }
            if (!feedback.Visible && !confirmEndRun && coordinator.offlineSettingsVisible && coordinator.r.nova != null && coordinator.r.nova.physicalInputAvailable &&
                coordinator.r.nova.mapping != null &&
                UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Joystick1Button0 + coordinator.r.nova.mapping.jump)))
            {
                if (Save())
                {
                    coordinator.r.settings.controllerSaves++;
                    Show(false);
                }
            }
        }
        public bool Draw()
        {
            if (coordinator.offlineSettings == null)
                return false;
            if (confirmEndRun)
            {
                // The dialog owns the whole event, including the event that
                // cancels it. Gameplay remains paused until settings resumes.
                var left = Screen.width * .5f - 240;
                var top = Screen.height * .5f - 120;
                GUI.Box(new Rect(left, top, 480, 240), "End this run?");
                GUI.Label(new Rect(left + 25, top + 42, 430, 70),
                          "Return to the menu and discard this ongoing run?\nThis does not record a completed run result.");
                var confirm = new Rect(left + 25, top + 135, 200, 55);
                coordinator.r.settings.confirmEndRunButtonX = confirm.center.x;
                coordinator.r.settings.confirmEndRunButtonY = confirm.center.y;
                bool allowed = coordinator.CanAbandonOfflineRun();
                var enabled = GUI.enabled;
                GUI.enabled = enabled && allowed;
                bool accepted = GUI.Button(confirm, "Confirm end run");
                GUI.enabled = enabled;
                bool cancel = GUI.Button(new Rect(left + 255, top + 135, 200, 55), "Keep playing");
                if (cancel || !allowed || accepted)
                {
                    confirmEndRun = false;
                    Observe();
                    coordinator.Save();
                    if (accepted && allowed)
                        coordinator.RequestAbandonOfflineRun();
                }
                return true;
            }
            if (feedback.Visible)
            {
                feedback.Draw();
                // Keep the GUI event owned even when Back closes the feedback.
                return true;
            }
            var button = AndroidTouchInput.PauseGuiRect(Screen.width);
            coordinator.r.settings.buttonX = button.center.x;
            coordinator.r.settings.buttonY = button.center.y;
            if (GUI.Button(button, coordinator.offlineSettingsVisible ? "Close settings" : "Settings / pause"))
            {
                Show(!coordinator.offlineSettingsVisible);
                if (!coordinator.offlineSettingsVisible)
                    return true;
            }
            if (!coordinator.offlineSettingsVisible)
            {
                if (!string.IsNullOrEmpty(coordinator.r.settings.error))
                    GUI.Box(new Rect(Screen.width * .5f - 240, 60, 480, 50), coordinator.r.settings.error);
                return false;
            }
            GUI.Box(new Rect(Screen.width * .5f - 240, Screen.height * .5f - 200, 480, 465),
                    coordinator.UsesTouchUi()
                        ? "Android offline settings · touch controls"
                        : "Android offline input settings · B back · A save");
            var x = Screen.width * .5f - 210;
            var y = Screen.height * .5f - 155;
            GUI.Label(new Rect(x, y, 420, 28), "Stick deadzone: " + coordinator.offlineSettings.values.deadzone.ToString("F2"));
            coordinator.offlineSettings.values.deadzone =
                GUI.HorizontalSlider(new Rect(x, y + 35, 420, 25), coordinator.offlineSettings.values.deadzone, .05f, .4f);
            GUI.Label(new Rect(x, y + 68, 420, 28),
                      "Camera sensitivity: " + coordinator.offlineSettings.values.lookSensitivity.ToString("F2"));
            coordinator.offlineSettings.values.lookSensitivity =
                GUI.HorizontalSlider(new Rect(x, y + 103, 420, 25), coordinator.offlineSettings.values.lookSensitivity, .25f, 3);
            coordinator.offlineSettings.values.invertY =
                GUI.Toggle(new Rect(x, y + 139, 420, 30), coordinator.offlineSettings.values.invertY, "Invert vertical camera");
            if (GUI.Button(new Rect(x, y + 180, 200, 45), "Save and close"))
            {
                if (Save())
                    Show(false);
            }
            if (GUI.Button(new Rect(x + 220, y + 180, 200, 45), "Resume"))
                Show(false);
            coordinator.r.settings.canEndRun = coordinator.CanAbandonOfflineRun();
            var end = new Rect(x, y + 245, 420, 45);
            coordinator.r.settings.endRunButtonX = end.center.x;
            coordinator.r.settings.endRunButtonY = end.center.y;
            if (coordinator.r.settings.canEndRun && GUI.Button(end, "End run and return to menu"))
            {
                confirmEndRun = true;
                Observe();
                coordinator.Save();
                return true;
            }
            if (!string.IsNullOrEmpty(coordinator.r.settings.error))
                GUI.Label(new Rect(x, y + 302, 420, 44), coordinator.r.settings.error);
            else if (coordinator.r.profile != null && coordinator.r.profile.ready)
                GUI.Label(new Rect(x, y + 302, 420, 44), "Android profile · " + coordinator.r.profile.appliedRuns + " genuine results · " +
                                                             coordinator.r.profile.kills +
                                                             " kills\nSteam/cloud and Rewired maps unavailable");
            if (GUI.Button(new Rect(x, y + 356, 420, 45), "Send feedback"))
                feedback.Open();
            Observe();
            if (coordinator.offlineSettingsPaused && Event.current.type == EventType.Repaint && Time.frameCount % 30 == 0)
            {
                coordinator.r.settings.observations++;
                coordinator.Save();
            }
            return true;
        }
        // Cleanup may run between sessions. Only an owned pause is released; the
        // store and an unpaused visible screen keep their existing lifetime.
        public void Dispose()
        {
            feedback.Close();
            confirmEndRun = false;
            if (coordinator.r != null && coordinator.r.settings != null)
                coordinator.r.settings.endRunConfirmationVisible = false;
            if (coordinator.offlineSettingsPaused)
                Show(false);
        }
    }
}
