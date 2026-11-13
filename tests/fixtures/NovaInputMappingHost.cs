// Authored host samples only. No recorded hardware mappings or game implementation.
using System;
using System.IO;
using System.Runtime.Serialization.Json;
using System.Text;
using UnityEngine;

public static class NovaInputMappingHost
{
    static void Need(bool value, string reason)
    {
        if (!value) throw new Exception(reason);
    }
    static void Near(float value, float expected, string reason)
    {
        Need(Math.Abs(value - expected) < .00001f, reason);
    }
    static NovaInputBridge.Mapping Candidate()
    {
        return new NovaInputBridge.Mapping {
            attempt = "host-fixture", observation = "authored-fixture",
            moveX = 4, moveY = 5, aimX = 6, aimY = 7,
            jump = 10, primary = 11, secondary = 12, utility = 13, special = 14,
            moveYSign = -1, aimYSign = 1, interact = 15
        };
    }
    static void Reject(Action<NovaInputBridge.Mapping> mutate)
    {
        var value = Candidate();
        mutate(value);
        bool rejected = false;
        try { value.Validate("host-fixture"); }
        catch (Exception) { rejected = true; }
        Need(rejected, "invalid mapping accepted");
    }
    static void Provenance()
    {
        Candidate().Validate("host-fixture");
        Reject(m => m.attempt = "previous-fixture");
        Reject(m => m.attempt = null);
        Reject(m => m.observation = null);
        Reject(m => m.observation = "");
        bool rejected = false;
        try { new NovaInputBridge.Mapping().Validate("host-fixture"); }
        catch (Exception) { rejected = true; }
        Need(rejected, "missing serialized fields cannot become a default mapping");
    }
    static void BindingRanges()
    {
        foreach (int bad in new[] { -1, 16, int.MaxValue })
        {
            Reject(m => m.moveX = bad); Reject(m => m.moveY = bad);
            Reject(m => m.aimX = bad); Reject(m => m.aimY = bad);
        }
        Reject(m => m.moveY = m.moveX);
        Reject(m => m.aimX = m.moveY);
        Reject(m => m.aimY = m.moveX);
        foreach (int bad in new[] { -1, 20, int.MaxValue })
        {
            Reject(m => m.jump = bad); Reject(m => m.primary = bad);
            Reject(m => m.secondary = bad); Reject(m => m.utility = bad); Reject(m => m.special = bad);
        }
        Reject(m => m.primary = m.jump); Reject(m => m.secondary = m.primary);
        Reject(m => m.utility = m.secondary); Reject(m => m.special = m.utility);
        foreach (float bad in new[] { 0f, .5f, -2f, float.NaN, float.PositiveInfinity, float.NegativeInfinity })
        {
            Reject(m => m.moveYSign = bad); Reject(m => m.aimYSign = bad);
        }
        var limits = Candidate();
        limits.moveX = 0; limits.moveY = 15; limits.jump = 0; limits.special = 19;
        limits.moveYSign = 1; limits.aimYSign = -1;
        limits.Validate("host-fixture");
    }
    static void Interaction()
    {
        var disabled = Candidate();
        disabled.interact = -1;
        disabled.Validate("host-fixture");
        var enabled = Candidate();
        enabled.enableInteraction = true;
        enabled.Validate("host-fixture");
        foreach (int bad in new[] { -1, 20, 10, 11, 12, 13, 14 })
            Reject(m => { m.enableInteraction = true; m.interact = bad; });
        // Shape validation alone is not permission to enable native skill delivery.
        enabled.enableSkills = true;
        enabled.Validate("host-fixture");
    }
    static string Snapshot(NovaInputBridge.Mapping m)
    {
        return string.Join("|", m.attempt, m.observation, m.moveX, m.moveY, m.aimX, m.aimY,
            m.jump, m.primary, m.secondary, m.utility, m.special, m.interact,
            m.moveYSign, m.aimYSign, m.enableSkills, m.enableInteraction);
    }
    static void NonmutatingValidation()
    {
        var active = Candidate();
        var candidate = Candidate();
        candidate.primary = candidate.jump;
        string beforeActive = Snapshot(active), beforeCandidate = Snapshot(candidate);
        try { candidate.Validate("host-fixture"); } catch (Exception) { }
        Need(Snapshot(active) == beforeActive && Snapshot(candidate) == beforeCandidate,
            "failed candidate changed bindings");
        candidate.primary = 19;
        beforeCandidate = Snapshot(candidate);
        candidate.Validate("host-fixture");
        Need(Snapshot(active) == beforeActive && Snapshot(candidate) == beforeCandidate,
            "validation applied or rewrote bindings");
    }
    static void Stick()
    {
        foreach (float deadzone in new[] { .05f, .18f, .4f })
        {
            AndroidOfflineSettings.current.deadzone = deadzone;
            var raw = new NovaInputBridge.Raw();
            raw.axes[4] = deadzone;
            Near(NovaInputBridge.SampleStick(raw, 4, 5, -1).sqrMagnitude, 0, "deadzone boundary");
            raw.axes[4] = deadzone + (1 - deadzone) * .5f;
            Near(NovaInputBridge.SampleStick(raw, 4, 5, -1).x, .5f, "rescaled travel");
            raw.axes[4] = 1; raw.axes[5] = 1;
            var stick = NovaInputBridge.SampleStick(raw, 4, 5, -1);
            Near(stick.magnitude, 1, "diagonal clamped");
            Need(stick.x > 0 && stick.y < 0, "vertical sign");
            raw.axes[4] = -1; raw.axes[5] = 0;
            Near(NovaInputBridge.SampleStick(raw, 4, 5, 1).x, -1, "negative axis");
            raw.axes[4] = 0; raw.axes[5] = 0;
            raw.axes[0] = 1; raw.axes[1] = 1;
            Near(NovaInputBridge.SampleStick(raw, 4, 5, 1).sqrMagnitude, 0, "unmapped axes ignored");
        }
    }
    static void NeutralReacquisition()
    {
        AndroidOfflineSettings.current.deadzone = .18f;
        var map = Candidate();
        var raw = new NovaInputBridge.Raw();
        var presence = new NovaInputBridge.ControllerPresence("Authored controller");
        var names = new[] { "Authored controller" };
        Need(NovaInputBridge.SampleNeutral(raw, map), "centered sample");
        Need(!presence.Observe(names, true, 0), "stable window required");
        for (int button = 0; button < raw.buttons.Length; button++)
        {
            raw.buttons[button] = true;
            Need(!NovaInputBridge.SampleNeutral(raw, map), "any held button blocks attach");
            raw.buttons[button] = false;
        }
        foreach (int axis in new[] { map.moveX, map.moveY, map.aimX, map.aimY })
        {
            foreach (float value in new[] { -.5f, .5f })
            {
                raw.axes[axis] = value;
                Need(!NovaInputBridge.SampleNeutral(raw, map), "mapped axis blocks attach");
            }
            raw.axes[axis] = 0;
        }
        raw.buttons[19] = true;
        Need(!presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), .24f), "held resets window");
        raw.buttons[19] = false;
        Need(!presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), .5f), "release starts window");
        Need(presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), .75f), "neutral attaches");
        presence.Suspend();
        Need(!presence.connected, "suspend clears connected state");
        Need(!presence.Observe(new[] { "Other controller" }, true, 1), "different name rejected");
        Need(!presence.Observe(new[] { "Authored controller", "Extra" }, true, 1), "extra controller rejected");
    }
    static void RadialNeutral()
    {
        var map = Candidate();
        foreach (bool aim in new[] { false, true })
        {
            int x = aim ? map.aimX : map.moveX, y = aim ? map.aimY : map.moveY;
            float sign = aim ? map.aimYSign : map.moveYSign;
            var raw = new NovaInputBridge.Raw();
            AndroidOfflineSettings.current.deadzone = .25f;
            Need(NovaInputBridge.SampleNeutral(raw, map), "center is neutral");
            raw.axes[x] = raw.axes[y] = .2f;
            Need(NovaInputBridge.SampleStick(raw, x, y, sign).sqrMagnitude > 0, "diagonal produces input");
            Need(!NovaInputBridge.SampleNeutral(raw, map), "diagonal movement cannot count as neutral");
            var presence = new NovaInputBridge.ControllerPresence("Authored controller");
            var names = new[] { "Authored controller" };
            Need(!presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), 0), "diagonal blocks attach");
            Need(!presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), .3f), "held diagonal never attaches");
            raw.axes[x] = .15f; raw.axes[y] = .2f;
            Near(NovaInputBridge.SampleStick(raw, x, y, sign).sqrMagnitude, 0, "radial edge produces no input");
            Need(NovaInputBridge.SampleNeutral(raw, map), "radial edge is neutral");
            Need(!presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), .5f), "edge starts stable window");
            Need(presence.Observe(names, NovaInputBridge.SampleNeutral(raw, map), .75f), "neutral edge attaches");
            raw.axes[x] = .25f; raw.axes[y] = 0;
            Need(NovaInputBridge.SampleNeutral(raw, map), "cardinal edge is neutral");
            raw.axes[x] = .2501f;
            Need(!NovaInputBridge.SampleNeutral(raw, map), "just outside edge is not neutral");
            raw.axes[x] = -.2f; raw.axes[y] = -.2f;
            Need(!NovaInputBridge.SampleNeutral(raw, map), "negative diagonal blocks attach");
        }
    }
    static NovaInputBridge.ButtonRebind Capture(NovaInputBridge.Mapping live, out NovaInputBridge.Raw raw)
    {
        var capture = new NovaInputBridge.ButtonRebind(live, "jump", "Authored controller");
        raw = new NovaInputBridge.Raw();
        return capture;
    }
    static void Sample(NovaInputBridge.ButtonRebind c, NovaInputBridge.Raw r, float t)
    {
        c.Observe(new[] { "Authored controller" }, r, t);
    }
    static void Arm(NovaInputBridge.ButtonRebind c, NovaInputBridge.Raw r, float t)
    {
        Sample(c, r, t); Sample(c, r, t + .25f);
    }
    static void RebindCapture()
    {
        var live = Candidate();
        var c = Capture(live, out var raw);
        raw.buttons[19] = true;
        Sample(c, raw, 0); Sample(c, raw, 1);
        Need(c.candidate == -1 && !c.ready, "opening held press excluded");
        raw.buttons[19] = false;
        Arm(c, raw, 2);
        raw.buttons[18] = true; Sample(c, raw, 3);
        Need(!c.ready, "release required");
        raw.buttons[18] = false; Sample(c, raw, 4);
        Need(c.ready && c.candidate == 18 && c.draft.jump == 18, "capture after release");
        Need(live.jump == 10, "live map mutated");
        Need(c.draft.moveX == live.moveX && c.draft.enableSkills == live.enableSkills &&
             c.draft.enableInteraction == live.enableInteraction, "unrelated policy changed");
    }
    static void RebindRefusals()
    {
        var live = Candidate();
        var c = Capture(live, out var raw);
        Arm(c, raw, 0);
        raw.buttons[live.primary] = true; Sample(c, raw, 1);
        raw.buttons[live.primary] = false; Sample(c, raw, 2);
        Need(!c.ready && c.error != null && c.draft.jump == live.jump, "collision accepted");
        Need(c.error.Contains("primary"), "collision action missing");
        Arm(c, raw, 2.5f);
        raw.buttons[1] = true; Sample(c, raw, 2.8f);
        raw.buttons[1] = false; Sample(c, raw, 2.9f);
        Need(!c.ready && c.error.Contains("menu / back"), "reserved back button accepted");
        Arm(c, raw, 3);
        raw.buttons[18] = raw.buttons[19] = true; Sample(c, raw, 4);
        Need(c.candidate == -1 && !c.ready, "ambiguous chord accepted");
        raw.buttons[18] = raw.buttons[19] = false;
        Arm(c, raw, 5);
        raw.buttons[18] = true; Sample(c, raw, 6);
        raw.buttons[18] = false; Sample(c, raw, 7);
        c.Observe(new[] { "Other controller" }, raw, 8);
        Need(!c.ready && c.candidate == -1 && c.draft.jump == live.jump, "disconnect kept candidate");
        bool rejected = false;
        try { new NovaInputBridge.ButtonRebind(live, "interact", "Authored controller"); }
        catch (ArgumentException) { rejected = true; }
        Need(rejected, "disabled interaction exposed");
    }
    static void MappingDisk(string mode, string directory)
    {
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, "mapping.json");
        var live = Candidate();
        live.observation_sha256 = new string('a', 64);
        live.accepted_mapping_attempt = "original-exposure";
        File.WriteAllText(path, JsonUtility.ToJson(live, false));
        string original = File.ReadAllText(path);
        var draft = live.Copy(); draft.jump = 18;
        if (mode == "mapping-save-failure")
        {
            Directory.CreateDirectory(path + ".pending");
            Need(!NovaInputBridge.MappingStore.TrySave(path, draft, live.attempt), "blocked write accepted");
            Need(File.ReadAllText(path) == original && live.jump == 10, "failed write changed primary/live");
            Directory.Delete(path + ".pending");
        }
        Need(NovaInputBridge.MappingStore.TrySave(path, draft, live.attempt), "save/retry");
        Need(live.jump == 10, "save replaced live session map");
        var loaded = NovaInputBridge.MappingStore.Load(path, live.attempt);
        Need(loaded.jump == 18 && loaded.observation_sha256 == live.observation_sha256 &&
             loaded.accepted_mapping_attempt == live.accepted_mapping_attempt, "reload/provenance");
        Need(File.ReadAllText(path + ".backup") == original, "backup lost");
        if (mode == "mapping-roundtrip")
        {
            var second = new NovaInputBridge.ButtonRebind(loaded, "secondary", "Authored controller");
            var raw = new NovaInputBridge.Raw(); Arm(second, raw, 0);
            raw.buttons[19] = true; Sample(second, raw, 1);
            raw.buttons[19] = false; Sample(second, raw, 2);
            Need(second.ready && second.draft.jump == 18, "second edit discarded first saved binding");
            Need(NovaInputBridge.MappingStore.TrySave(path, second.draft, live.attempt), "second save");
            var next = NovaInputBridge.MappingStore.Load(path, live.attempt);
            Need(next.jump == 18 && next.secondary == 19 && live.jump == 10 && live.secondary == 12, "composed next-session bindings");
        }
        if (mode != "mapping-recovery") return;
        File.WriteAllText(path + ".pending", "{partial");
        Need(NovaInputBridge.MappingStore.Load(path, live.attempt).jump == 18, "pending promoted");
        File.WriteAllText(path, "{corrupt");
        Need(NovaInputBridge.MappingStore.Load(path, live.attempt).jump == 10, "backup not restored");
        Need(Directory.GetFiles(directory, "*.rejected-*").Length == 1, "corrupt original not retained");
        File.Delete(path);
        Need(!NovaInputBridge.MappingStore.TryLoad(path, "next-attempt", out _), "stale backup admitted");
        Need(NovaInputBridge.MappingStore.Load(path, live.attempt).jump == 10, "missing primary backup recovery");
    }
    public static void Main(string[] args)
    {
        switch (args[0])
        {
            case "rebind-capture": RebindCapture(); break;
            case "rebind-refusals": RebindRefusals(); break;
            case "mapping-roundtrip":
            case "mapping-recovery":
            case "mapping-save-failure": MappingDisk(args[0], args[1]); break;
            case "provenance": Provenance(); break;
            case "binding-ranges": BindingRanges(); break;
            case "interaction": Interaction(); break;
            case "nonmutating-validation": NonmutatingValidation(); break;
            case "stick": Stick(); break;
            case "neutral-reacquisition": NeutralReacquisition(); break;
            case "radial-neutral": RadialNeutral(); break;
            default: throw new Exception("unknown host case");
        }
        Console.WriteLine(args[0] + ": PASS");
    }
}

namespace UnityEngine
{
    public static class JsonUtility
    {
        public static string ToJson(object value, bool pretty)
        {
            using (var stream = new MemoryStream())
            {
                new DataContractJsonSerializer(value.GetType()).WriteObject(stream, value);
                return Encoding.UTF8.GetString(stream.ToArray());
            }
        }
        public static void FromJsonOverwrite(string json, object value)
        {
            try
            {
                using (var stream = new MemoryStream(Encoding.UTF8.GetBytes(json)))
                {
                    var restored = new DataContractJsonSerializer(value.GetType()).ReadObject(stream);
                    foreach (var field in value.GetType().GetFields())
                        field.SetValue(value, field.GetValue(restored));
                }
            }
            catch (System.Runtime.Serialization.SerializationException e) { throw new ArgumentException("invalid JSON", e); }
        }
    }
}
