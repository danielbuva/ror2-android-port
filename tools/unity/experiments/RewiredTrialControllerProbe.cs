using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Rewired;
using UnityEngine;

// SDK-only physical observation. No RoR2 assembly, simulation or platform startup.
public class RewiredTrialControllerProbe : MonoBehaviour
{
    [Serializable] public class Identity { public int id; public string name; }
    [Serializable] public class Map { public int controllerId, categoryId, layoutId, elements; public bool enabled; }
    [Serializable] public class Event { public float time; public string kind, name; public int index; public float value; }
    [Serializable] public class Snapshot { public string persistentDataPath, editor, backend; public int pid; }
    [Serializable] public class Report
    {
        public string attempt, scope = "Official trial SDK and copied game input data only", error;
        public int pid, joystickCount, playerId;
        public bool ready, complete;
        public float elapsed;
        public Identity[] actions, players;
        public Map[] maps;
        public string[] axisNames, buttonNames;
        public List<Event> events = new List<Event>();
    }
    public string attempt;
    public int[] expectedActionIds;
    Report report;
    Player player;
    Joystick joystick;
    float started, lastWrite;
    float[] axes, mapped;
    string status = "Waiting for trial ReInput";
    string path;
    void Awake()
    {
        path = Path.Combine(Application.persistentDataPath, "rewired-trial-controller.json");
        started = Time.realtimeSinceStartup;
        report = new Report { attempt = attempt, pid = System.Diagnostics.Process.GetCurrentProcess().Id };
        Application.logMessageReceived += Error;
        var snapshot = new Snapshot { persistentDataPath = Application.persistentDataPath, editor = Application.unityVersion, backend = "IL2CPP ARM64 trial reference", pid = report.pid };
        File.WriteAllText(Path.Combine(Application.persistentDataPath, "snapshot.json"), JsonUtility.ToJson(snapshot));
        Debug.Log("LAB_SNAPSHOT " + JsonUtility.ToJson(snapshot));
    }
    IEnumerator Start()
    {
        while (!ReInput.isReady && Time.realtimeSinceStartup - started < 15) yield return null;
        if (!ReInput.isReady) { Fail("Trial ReInput did not initialize within 15 seconds"); yield break; }
        try
        {
            report.ready = true;
            report.players = ReInput.players.AllPlayers.Select(p => new Identity { id = p.id, name = p.name }).ToArray();
            report.actions = ReInput.mapping.Actions.Select(a => new Identity { id = a.id, name = a.name }).ToArray();
            if (!report.actions.Select(a => a.id).OrderBy(i => i).SequenceEqual(expectedActionIds.OrderBy(i => i)))
                throw new InvalidOperationException("Original action IDs not retained");
            player = ReInput.players.GetPlayer("PlayerMain");
            // Original game GetPlayer(0) and original core's ordinal runtime IDs;
            // serialized Player_Editor._id is a separate definition identity.
            if (player == null || player.id != 0 || ReInput.players.GetPlayer(0) != player)
                throw new InvalidOperationException("Original PlayerMain runtime lookup not retained");
            report.playerId = player.id;
            report.joystickCount = ReInput.controllers.joystickCount;
            if (report.joystickCount != 1) throw new InvalidOperationException("Expected one built-in Nova joystick");
            joystick = ReInput.controllers.Joysticks[0];
            player.controllers.AddController(joystick, true);
            report.maps = player.controllers.maps.GetAllMaps().Select(m => new Map { controllerId = m.controllerId, categoryId = m.categoryId, layoutId = m.layoutId, enabled = m.enabled, elements = m.elementMapCount }).ToArray();
            report.axisNames = joystick.AxisElementIdentifiers.Select(e => e.name).ToArray();
            report.buttonNames = joystick.ButtonElementIdentifiers.Select(e => e.name).ToArray();
            axes = new float[joystick.axisCount]; mapped = new float[report.actions.Length];
            status = "Trial input READY — physical observation only";
            Debug.Log("REWIRED_TRIAL_READY " + JsonUtility.ToJson(report));
            Debug.Log("LAB_READY"); // Existing owned lab launch guard; no game capability implied.
            Save();
        }
        catch (Exception e) { Fail(e.ToString()); }
    }
    void Update()
    {
        if (joystick == null || report.complete || report.error != null) return;
        try
        {
            report.elapsed = Time.realtimeSinceStartup - started;
            for (int i = 0; i < joystick.buttonCount; i++)
            {
                if (joystick.GetButtonDown(i)) Add("raw-button-down", i, report.buttonNames[i], 1);
                if (joystick.GetButtonUp(i)) Add("raw-button-up", i, report.buttonNames[i], 0);
            }
            for (int i = 0; i < axes.Length; i++)
            {
                float value = joystick.GetAxis(i);
                if (Math.Abs(value - axes[i]) > .2f || (Math.Abs(value) < .05f && Math.Abs(axes[i]) >= .05f))
                { axes[i] = value; Add("raw-axis", i, report.axisNames[i], value); }
            }
            for (int i = 0; i < report.actions.Length; i++)
            {
                var action = report.actions[i]; float value = player.GetAxis(action.id);
                if (Math.Abs(value - mapped[i]) > .2f || (Math.Abs(value) < .05f && Math.Abs(mapped[i]) >= .05f))
                { mapped[i] = value; Add("mapped-action", action.id, action.name, value); }
                if (player.GetButtonDown(action.id)) Add("mapped-button-down", action.id, action.name, 1);
                if (player.GetButtonUp(action.id)) Add("mapped-button-up", action.id, action.name, 0);
            }
            if (report.elapsed >= 90) { report.complete = true; status = "Observation complete — no gameplay acceptance"; Save(); }
            else if (report.elapsed - lastWrite >= 1) Save();
        }
        catch (Exception e) { Fail(e.ToString()); }
    }
    void Add(string kind, int index, string name, float value) { report.events.Add(new Event { time = report.elapsed, kind = kind, index = index, name = name, value = value }); }
    void Save() { lastWrite = report.elapsed; File.WriteAllText(path, JsonUtility.ToJson(report, true)); }
    void Fail(string error) { report.error = error; status = "PROBE FAILED"; Save(); Debug.LogError("REWIRED_TRIAL_FAILED " + error); }
    void Error(string message, string stack, LogType type)
    {
        if (type == LogType.Exception) { report.error = message + "\n" + stack; Save(); }
    }
    void OnDestroy() { Application.logMessageReceived -= Error; }
    void OnGUI()
    {
        var style = new GUIStyle(GUI.skin.label) { fontSize = 27 };
        GUI.Label(new Rect(30,30,Screen.width-60,Screen.height-60), "REWIRED TRIAL REFERENCE — NOT RoR2\n" + status + "\nElapsed " + (report == null ? 0 : report.elapsed).ToString("F1") + " / 90 seconds\nEvents " + (report == null ? 0 : report.events.Count) + "\nFollow the control sequence requested in chat.", style);
    }
}
