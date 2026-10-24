// Subsystem: settings/feedback (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Lifetime: AndroidFeedbackScreen opens an in-memory draft; Close clears text and consent.
using System;

// Tokenless, fixed-field report. This type never reads files, logs, accounts or devices.
public sealed class AndroidFeedbackDraft
{
    public const int MaxNotesLength = 600;
    public const string IssueEndpoint = "https://github.com/danielbuva/ror2-android-port/issues/new";
    public const string IssueTitle = "Android alpha feedback";
    public string Notes { get; private set; } = "";
    public string Preview { get; private set; } = "";
    public bool Consented { get; private set; }
    public bool CanShare => Preview.Length != 0 && Consented;

    public void Edit(string notes)
    {
        notes = notes ?? "";
        if (notes.Length > MaxNotesLength)
            notes = notes.Substring(0, MaxNotesLength);
        if (Notes == notes)
            return;
        Notes = notes;
        Preview = "";
        Consented = false;
    }

    public bool Review(string version, string unityVersion, string buildGuid, string graphicsApi)
    {
        Consented = false;
        Preview = "";
        var notes = PlainText(Notes).Trim();
        if (string.IsNullOrWhiteSpace(notes))
            return false;
        Preview = "## What happened / steps / expected result\n" + notes +
                  "\n\n## Build facts\n" +
                  "App version: " + SafeTag(version) + "\n" +
                  "Unity version: " + SafeTag(unityVersion) + "\n" +
                  "Build GUID (not APK hash): " + SafeGuid(buildGuid) + "\n" +
                  "Graphics API: " + SafeTag(graphicsApi) + "\n" +
                  "Game runtime: IL2CPP ARM64\n" +
                  "Laboratory build; gameplay assists may be enabled.\n" +
                  "No logs or attachments collected automatically.\n" +
                  "Build facts contain no device, storage or account identifiers.\n" +
                  "Manual notes are not automatically redacted; review any attachments separately.\n";
        return true;
    }

    public void BeginEdit()
    {
        Preview = "";
        Consented = false;
    }

    public void Consent(bool consent)
    {
        Consented = consent && Preview.Length != 0;
    }

    public string IssueUrl()
    {
        if (!CanShare)
            throw new InvalidOperationException("Review and consent are required before sharing.");
        return IssueEndpoint + "?title=" + Uri.EscapeDataString(IssueTitle) + "&body=" + Uri.EscapeDataString(Preview);
    }

    public string SharedText()
    {
        if (!CanShare)
            throw new InvalidOperationException("Review and consent are required before sharing.");
        return Preview;
    }

    public void Clear()
    {
        Notes = "";
        Preview = "";
        Consented = false;
    }

    static string SafeTag(string value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 64)
            return "unknown";
        foreach (var c in value)
            if (!(c >= 'a' && c <= 'z') && !(c >= 'A' && c <= 'Z') && !(c >= '0' && c <= '9') &&
                c != '.' && c != '-' && c != '+')
                return "unknown";
        return value;
    }

    static string SafeGuid(string value)
    {
        if (value == null || value.Length != 32)
            return "unknown";
        foreach (var c in value)
            if (!(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'f') && !(c >= 'A' && c <= 'F'))
                return "unknown";
        return value;
    }

    // Encode manual text as literal Markdown and replace invalid Unicode/control
    // characters. User-authored text still requires review; it is not a log scrubber.
    static string PlainText(string value)
    {
        var result = new System.Text.StringBuilder();
        for (var i = 0; i < value.Length; i++)
        {
            var c = value[i];
            if (c == '\r')
            {
                result.Append('\n');
                if (i + 1 < value.Length && value[i + 1] == '\n')
                    i++;
                continue;
            }
            if (char.IsHighSurrogate(c) && i + 1 < value.Length && char.IsLowSurrogate(value[i + 1]))
            {
                result.Append(c).Append(value[++i]);
                continue;
            }
            if (char.IsSurrogate(c) || (char.IsControl(c) && c != '\n' && c != '\t'))
                continue;
            if ("\\`*_{}[]<>()#+-.!|>".IndexOf(c) >= 0)
                result.Append('\\');
            result.Append(c);
        }
        return result.ToString();
    }
}
