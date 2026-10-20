// Review candidate. Captures only the active UnityLinker inputDirectory for an
// explicitly opted-in player request. Always returns an inert linker file
// because Unity's callback contract requires a path on every build.
using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.UnityLinker;
using UnityEngine;

public sealed class PlayerLinkerInputCapture : IUnityLinkerProcessor
{
#pragma warning disable 0649
    [Serializable] sealed class Request
    {
        public string request_id;
        public bool capturePlayerLinkerInputs;
        public string sourceCommit;
        public string inputId;
    }
    [Serializable] sealed class InputIdentity { public string input_id; }
    [Serializable] sealed class Row { public string role; public string path; public string sha256; public long size; public string snapshot_path; }
    [Serializable] sealed class Capture
    {
        public string schema = "ror2lab-unitylinker-input-v1";
        public string request_id;
        public string source_commit;
        public string input_id;
        public string build_report_guid;
        public string target;
        public string input_directory;
        public Row[] files;
    }
#pragma warning restore 0649

    const string EmptyLinkerXml = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<linker />\n";
    public int callbackOrder { get { return 0; } }

    public string GenerateAdditionalLinkXmlFile(BuildReport report, UnityLinkerBuildPipelineData data)
    {
        string project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        string work = WorkRoot(project);
        string emptyXml = PrepareOutput(work);
        string output = Path.GetDirectoryName(emptyXml);

        string requestPath = Path.Combine(work, "build-request.json");
        if (!File.Exists(requestPath))
            return emptyXml; // Manual/default builds remain capture-disabled.
        Request request = JsonUtility.FromJson<Request>(File.ReadAllText(requestPath));
        if (request == null || !request.capturePlayerLinkerInputs) return emptyXml;
        if (!Token(request.request_id))
            throw new InvalidOperationException("Opted-in Unity linker request identity is malformed");
        if (!String.Equals(request.request_id, SessionState.GetString("PortingLab.ARM64Running", ""), StringComparison.Ordinal))
            throw new InvalidOperationException("Opted-in linker request is not the active lab build");

        if (!Hex(request.sourceCommit, 40) || !Hex(request.inputId, 64))
            throw new InvalidOperationException("Opted-in linker capture lacks source or input identity");
        string markerPath = Path.Combine(project, ".port-input.json");
        string inventoryPath = Path.Combine(work, "inventory", "files.json");
        if (!File.Exists(markerPath) || !File.Exists(inventoryPath))
            throw new InvalidOperationException("Opted-in linker capture cannot verify accepted input identity");
        InputIdentity marker = JsonUtility.FromJson<InputIdentity>(File.ReadAllText(markerPath));
        InputIdentity inventory = JsonUtility.FromJson<InputIdentity>(File.ReadAllText(inventoryPath));
        if (marker == null || inventory == null || marker.input_id != request.inputId || inventory.input_id != request.inputId)
            throw new InvalidOperationException("Opted-in linker capture input identity drifted");
        if (report == null || data == null || data.target != BuildTarget.Android)
            throw new InvalidOperationException("Opted-in linker capture is not an Android player link step");

        string inputDirectory = Path.GetFullPath(data.inputDirectory);
        string relativeDirectory = Relative(project, inputDirectory);
        if (!Directory.Exists(inputDirectory))
            throw new InvalidOperationException("UnityLinker input directory is missing");
        RejectReparseAncestors(project, inputDirectory);
        string[] dllPaths = Directory.GetFiles(inputDirectory, "*", SearchOption.AllDirectories)
            .Where(path => String.Equals(Path.GetExtension(path), ".dll", StringComparison.OrdinalIgnoreCase))
            .OrderBy(path => path, StringComparer.Ordinal).ToArray();
        if (dllPaths.Length == 0)
            throw new InvalidOperationException("UnityLinker input directory contains no DLLs");

        string requestSnapshot = Path.Combine(output, request.request_id, "assemblies");
        RejectExistingReparseAncestors(work, requestSnapshot);
        Directory.CreateDirectory(requestSnapshot);
        RejectReparseAncestors(work, requestSnapshot);
        Row[] rows = dllPaths.Select(path => Describe(inputDirectory, path, requestSnapshot, work, request.request_id)).ToArray();
        if (rows.Select(row => row.path).Distinct(StringComparer.Ordinal).Count() != rows.Length)
            throw new InvalidOperationException("UnityLinker input inventory has duplicate relative paths");
        Capture capture = new Capture
        {
            request_id = request.request_id,
            source_commit = request.sourceCommit,
            input_id = request.inputId,
            build_report_guid = report.summary.guid.ToString(),
            target = data.target.ToString(),
            input_directory = relativeDirectory,
            files = rows
        };
        string capturePath = Path.Combine(output, request.request_id + ".json");
        RejectExistingReparseAncestors(work, capturePath);
        WriteStable(capturePath, JsonUtility.ToJson(capture, true));
        RejectReparseAncestors(work, capturePath);
        return emptyXml;
    }

    static string PrepareOutput(string workRoot)
    {
        string work = Path.GetFullPath(workRoot);
        string output = Path.Combine(work, "lab-build", "player-linker-inputs");
        string emptyXml = Path.Combine(output, "empty-linker.xml");
        Relative(work, output);
        Relative(work, emptyXml);
        RejectExistingReparseAncestors(work, output);
        RejectExistingReparseAncestors(work, emptyXml);
        Directory.CreateDirectory(output);
        RejectReparseAncestors(work, output);
        WriteStable(emptyXml, EmptyLinkerXml);
        RejectReparseAncestors(work, emptyXml);
        return emptyXml;
    }

    static Row Describe(string root, string path, string snapshotRoot, string workRoot, string requestId)
    {
        string full = Path.GetFullPath(path);
        string relative = Relative(root, full);
        RejectReparseAncestors(root, full);
        var info = new FileInfo(full);
        if (!info.Exists || info.Length <= 0)
            throw new InvalidOperationException("UnityLinker reported an empty or missing managed DLL");
        string beforeHash = HashFile(full);
        long beforeSize = info.Length;
        string snapshot = Path.GetFullPath(Path.Combine(snapshotRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
        Relative(snapshotRoot, snapshot);
        string snapshotDirectory = Path.GetDirectoryName(snapshot);
        RejectExistingReparseAncestors(workRoot, snapshotDirectory);
        Directory.CreateDirectory(snapshotDirectory);
        RejectReparseAncestors(workRoot, snapshotDirectory);
        if (File.Exists(snapshot)) RejectReparseAncestors(workRoot, snapshot);
        else File.Copy(full, snapshot, false);
        RejectReparseAncestors(workRoot, snapshot);
        string copiedHash = HashFile(snapshot);
        string afterHash = HashFile(full);
        long afterSize = new FileInfo(full).Length;
        if (beforeSize != afterSize || beforeHash != copiedHash || beforeHash != afterHash)
            throw new InvalidOperationException("UnityLinker input changed while its immutable request snapshot was copied");
        return new Row
        {
            role = "UnityLinkerInput",
            path = relative,
            size = beforeSize,
            sha256 = beforeHash,
            snapshot_path = "lab-build/player-linker-inputs/" + requestId + "/assemblies/" + relative
        };
    }

    static string HashFile(string path)
    {
        using (SHA256 hash = SHA256.Create())
        using (FileStream stream = File.OpenRead(path)) return Digest(hash.ComputeHash(stream));
    }

    static void RejectExistingReparseAncestors(string root, string path)
    {
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string current = Path.GetFullPath(path);
        while (!String.Equals(current, fullRoot, StringComparison.Ordinal) && !Directory.Exists(current) && !File.Exists(current))
        {
            current = Path.GetDirectoryName(current);
            if (String.IsNullOrEmpty(current))
                throw new InvalidOperationException("UnityLinker snapshot path escaped its work root");
        }
        RejectReparseAncestors(fullRoot, current);
    }

    static void RejectReparseAncestors(string root, string path)
    {
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string current = Path.GetFullPath(path);
        while (true)
        {
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("UnityLinker input path contains a symbolic link or reparse point");
            if (String.Equals(current, fullRoot, StringComparison.Ordinal)) return;
            current = Path.GetDirectoryName(current);
            if (String.IsNullOrEmpty(current))
                throw new InvalidOperationException("UnityLinker input path escaped its directory");
        }
    }

    static string Relative(string root, string path)
    {
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string full = Path.GetFullPath(path);
        string prefix = fullRoot + Path.DirectorySeparatorChar;
        if (!full.StartsWith(prefix, StringComparison.Ordinal))
            throw new InvalidOperationException("UnityLinker input path is outside the generated project");
        return full.Substring(prefix.Length).Replace(Path.DirectorySeparatorChar, '/');
    }

    static void WriteStable(string path, string contents)
    {
        byte[] bytes = new UTF8Encoding(false).GetBytes(contents);
        if (File.Exists(path))
        {
            if (!File.ReadAllBytes(path).SequenceEqual(bytes))
                throw new InvalidOperationException("Request-bound linker capture already exists with different bytes");
            return;
        }
        using (FileStream stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            stream.Write(bytes, 0, bytes.Length);
    }

    static string Digest(byte[] bytes) { return String.Concat(bytes.Select(value => value.ToString("x2"))); }
    static string WorkRoot(string project)
    {
        string[] args = Environment.GetCommandLineArgs();
        int index = Array.IndexOf(args, "-labWorkRoot");
        if (index < 0) return Path.GetFullPath(Path.Combine(project, ".."));
        if (index + 1 >= args.Length) throw new InvalidOperationException("Missing isolated lab work root");
        string root = Path.GetFullPath(args[index + 1]);
        string allowed = Path.GetFullPath(Path.Combine(Application.dataPath, "../.rebuild/unity")) + Path.DirectorySeparatorChar;
        if (!root.StartsWith(allowed, StringComparison.Ordinal))
            throw new InvalidOperationException("Isolated lab work root is outside the configured destination");
        return root;
    }
    static bool Hex(string value, int length)
    {
        return value != null && value.Length == length && value.All(ch => (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'));
    }
    static bool Token(string value)
    {
        return !String.IsNullOrEmpty(value) && value.Length <= 80 && value.All(ch =>
            (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '.' || ch == '_' || ch == '-');
    }
}
