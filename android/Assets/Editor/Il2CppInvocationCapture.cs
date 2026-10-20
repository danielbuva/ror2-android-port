// Application.logMessageReceived delivery of UnityLogWriter's native
// internalcall remains unverified.
using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

public sealed class Il2CppInvocationCapture : IPreprocessBuildWithReport, IPostprocessBuildWithReport
{
    const string Prefix = "Invoking il2cpp with arguments: ";
    static BuildReport activeReport;
    static string requestId, sourceCommit, inputId, projectRoot, workRoot;
    static string line, projectRelativeInput, reportGuid, failure;
    static Row[] inventory;
    static bool invalid, listening, updateListening;
    static double preprocessTime;
    public int callbackOrder { get { return int.MaxValue; } }

    [Serializable] sealed class Row
    {
        public string path;
        public string snapshot_path;
        public long size;
        public string sha256;
    }
    [Serializable] sealed class Receipt
    {
        public string schema = "ror2lab-il2cpp-invocation-capture-candidate-v1";
        public string capture_flag = "captureIl2CppInvocation";
        public string request_id, source_commit, input_id, build_report_guid;
        public string target, output_path, build_report_result, il2cpp_command_line_log, il2cpp_input_directory;
        public string evidence_kind = "UnityLogWriter pre-launch rendered command line; not argv[]";
        public Row[] files;
    }
    [Serializable] sealed class FailureWitness
    {
        public string schema = "ror2lab-il2cpp-invocation-incomplete-v1";
        public string capture_flag = "captureIl2CppInvocation";
        public string request_id, source_commit, input_id, build_report_guid, reason;
        public string[] partial_snapshot_paths;
    }
    [Serializable] sealed class Request { public string request_id; public bool captureIl2CppInvocation; public string sourceCommit, inputId; }
    [Serializable] sealed class InputIdentity { public string input_id; }

    public void OnPreprocessBuild(BuildReport report)
    {
        Reset();
        // Ordinary editor builds exit before path resolution or file access.
        string activeRequestId = SessionState.GetString("PortingLab.ARM64Running", "");
        if (!Token(activeRequestId)) return;
        projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        if (!TryWorkRoot(projectRoot, out workRoot))
            throw new InvalidOperationException("Active lab build has an invalid work-root contract");
        string requestPath = Path.Combine(workRoot, "build-request.json");
        if (!File.Exists(requestPath))
            throw new InvalidOperationException("Active lab build request is missing");
        Request request = JsonUtility.FromJson<Request>(File.ReadAllText(requestPath));
        if (request == null) throw new InvalidOperationException("Active lab build request is invalid");
        if (!request.captureIl2CppInvocation) return;
        if (!Token(request.request_id) || request.request_id != activeRequestId)
            throw new InvalidOperationException("Opted-in invocation capture is not the active build request");

        if (report == null || report.summary.platform != BuildTarget.Android || String.IsNullOrEmpty(report.summary.guid.ToString()))
            throw new InvalidOperationException("Opted-in invocation capture has no Android BuildReport identity");
        if (!Hex(request.sourceCommit, 40) || !Hex(request.inputId, 64))
            throw new InvalidOperationException("Opted-in invocation capture lacks source/input identity");
        string markerPath = Path.Combine(projectRoot, ".port-input.json");
        string inventoryPath = Path.Combine(workRoot, "inventory", "files.json");
        if (!File.Exists(markerPath) || !File.Exists(inventoryPath))
            throw new InvalidOperationException("Opted-in invocation capture cannot verify accepted input identity");
        InputIdentity marker = JsonUtility.FromJson<InputIdentity>(File.ReadAllText(markerPath));
        InputIdentity accepted = JsonUtility.FromJson<InputIdentity>(File.ReadAllText(inventoryPath));
        if (marker == null || accepted == null || marker.input_id != request.inputId || accepted.input_id != request.inputId)
            throw new InvalidOperationException("Opted-in invocation capture input identity drifted");

        activeReport = report;
        reportGuid = report.summary.guid.ToString();
        requestId = request.request_id;
        sourceCommit = request.sourceCommit;
        inputId = request.inputId;
        preprocessTime = EditorApplication.timeSinceStartup;
        Application.logMessageReceived += OnLog;
        listening = true;
        EditorApplication.update += WatchBuildEnd;
        updateListening = true;
    }

    public void OnPostprocessBuild(BuildReport report)
    {
        try
        {
            if (activeReport == null) return;
            if (report == null || report.summary.guid.ToString() != reportGuid || report.summary.guid.ToString() != activeReport.summary.guid.ToString())
            {
                MarkInvalid("postprocess_report_guid_mismatch");
                WriteFailureWitness();
                return;
            }
            if (invalid || String.IsNullOrEmpty(line) || inventory == null || inventory.Length == 0 || String.IsNullOrEmpty(projectRelativeInput))
            {
                if (String.IsNullOrEmpty(failure)) failure = "same_build_invocation_or_snapshot_incomplete";
                WriteFailureWitness();
                return;
            }
            if (report.summary.platform != BuildTarget.Android)
            {
                MarkInvalid("postprocess_report_not_android");
                WriteFailureWitness();
                return;
            }
            Receipt receipt = new Receipt {
                request_id = requestId, source_commit = sourceCommit, input_id = inputId,
                build_report_guid = report.summary.guid.ToString(), target = report.summary.platform.ToString(),
                output_path = report.summary.outputPath, build_report_result = report.summary.result.ToString(),
                il2cpp_command_line_log = line, il2cpp_input_directory = projectRelativeInput,
                files = inventory.Select(ToRow).ToArray()
            };
            WriteNew(ReceiptPath(), JsonUtility.ToJson(receipt, true));
        }
        catch (Exception)
        {
            // Capture is an optional receipt. Do not turn an otherwise valid
            // Unity player build into a failure; the outer host verifier rejects
            // the absent/partial receipt.
            MarkInvalid("postprocess_receipt_write_failed");
            WriteFailureWitness();
        }
        finally { StopListening(); }
    }

    static void OnLog(string condition, string stackTrace, LogType type)
    {
        if (activeReport == null || condition == null || !condition.StartsWith(Prefix, StringComparison.Ordinal)) return;
        if (!String.IsNullOrEmpty(line)) { MarkInvalid("multiple_il2cpp_invocation_lines"); return; }
        try
        {
            string rendered = condition.Substring(Prefix.Length);
            string[] directoryArguments = rendered.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries)
                .Where(token => token == "--directory" || token.StartsWith("--directory=", StringComparison.Ordinal)).ToArray();
            if (directoryArguments.Length != 1 || !directoryArguments[0].StartsWith("--directory=", StringComparison.Ordinal))
                throw new InvalidOperationException("IL2CPP command line must contain exactly one directory argument");
            string argument = directoryArguments[0].Substring("--directory=".Length);
            if (argument.IndexOfAny(new[] { '"', '\'', '\t', '\r', '\n' }) >= 0)
                throw new InvalidOperationException("IL2CPP directory argument has ambiguous quoting or whitespace");
            string directory = Path.GetFullPath(argument);
            projectRelativeInput = Relative(projectRoot, directory).Replace(Path.DirectorySeparatorChar, '/');
            RejectReparseAncestors(projectRoot, directory);
            if (!Directory.Exists(directory)) throw new InvalidOperationException("IL2CPP input directory is absent at invocation");
            string[] files = Directory.GetFiles(directory, "*", SearchOption.AllDirectories)
                .OrderBy(path => path, StringComparer.Ordinal).ToArray();
            if (files.Length == 0) throw new InvalidOperationException("IL2CPP input directory is empty");
            string snapshotRoot = Path.Combine(workRoot, "lab-build", "player-linker-inputs", requestId, "poststrip");
            Relative(workRoot, snapshotRoot);
            RejectReparseAncestors(workRoot, snapshotRoot);
            Directory.CreateDirectory(snapshotRoot);
            RejectReparseAncestors(workRoot, snapshotRoot);
            inventory = new Row[files.Length];
            for (int i = 0; i < files.Length; i++) inventory[i] = SnapshotStable(directory, files[i], snapshotRoot);
            line = condition;
        }
        catch (Exception ex) { MarkInvalid("invocation_capture_failed:" + ex.GetType().Name); }
    }

    static Row SnapshotStable(string inputRoot, string source, string snapshotRoot)
    {
        string relative = Relative(inputRoot, source);
        RejectReparseAncestors(inputRoot, source);
        byte[] before = File.ReadAllBytes(source);
        string destination = Path.Combine(snapshotRoot, relative);
        try
        {
            Relative(workRoot, destination);
            Directory.CreateDirectory(Path.GetDirectoryName(destination));
            RejectReparseAncestors(workRoot, destination);
            using (var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None)) output.Write(before, 0, before.Length);
            byte[] copied = File.ReadAllBytes(destination), after = File.ReadAllBytes(source);
            if (!before.SequenceEqual(copied) || !before.SequenceEqual(after)) throw new InvalidOperationException("IL2CPP input changed during snapshot");
            RejectReparseAncestors(workRoot, destination);
            return new Row { path = relative.Replace(Path.DirectorySeparatorChar, '/'), snapshot_path = Relative(workRoot, destination).Replace(Path.DirectorySeparatorChar, '/'), size = copied.LongLength, sha256 = Hash(copied) };
        }
        catch
        {
            try { RejectReparseAncestors(workRoot, destination); if (File.Exists(destination)) File.Delete(destination); }
            catch { /* Failure witness records completed copies; an unsafe partial path is never followed. */ }
            throw;
        }
    }

    static Row ToRow(Row row)
    {
        string snapshot = Path.Combine(workRoot, row.snapshot_path.Replace('/', Path.DirectorySeparatorChar));
        RejectReparseAncestors(workRoot, snapshot);
        byte[] bytes = File.ReadAllBytes(snapshot);
        if (bytes.LongLength != row.size || Hash(bytes) != row.sha256) throw new InvalidOperationException("Post-strip snapshot changed before finalization");
        return row;
    }
    static string Hash(byte[] bytes) { using (var sha = SHA256.Create()) return String.Concat(sha.ComputeHash(bytes).Select(value => value.ToString("x2"))); }
    static string Relative(string root, string path)
    {
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string full = Path.GetFullPath(path);
        string prefix = fullRoot + Path.DirectorySeparatorChar;
        if (!full.StartsWith(prefix, StringComparison.Ordinal)) throw new InvalidOperationException("Capture path is outside its designated root");
        return full.Substring(prefix.Length);
    }
    static void WriteNew(string path, string text)
    {
        Relative(workRoot, path);
        RejectReparseAncestors(workRoot, path);
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        RejectReparseAncestors(workRoot, path);
        using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        { byte[] bytes = new UTF8Encoding(false).GetBytes(text); stream.Write(bytes, 0, bytes.Length); }
    }
    static void WriteFailureWitness()
    {
        try
        {
            if (String.IsNullOrEmpty(workRoot) || String.IsNullOrEmpty(requestId)) return;
            var witness = new FailureWitness {
                request_id = requestId, source_commit = sourceCommit, input_id = inputId,
                build_report_guid = reportGuid, reason = failure ?? "capture_incomplete",
                partial_snapshot_paths = (inventory ?? new Row[0]).Where(row => row != null).Select(row => row.snapshot_path).ToArray()
            };
            string path = Path.Combine(workRoot, "lab-build", "player-linker-inputs", requestId + ".il2cpp-incomplete.json");
            WriteNew(path, JsonUtility.ToJson(witness, true));
        }
        catch (Exception) { /* Missing witness is still a host-side refusal. */ }
    }
    static string ReceiptPath() { return Path.Combine(workRoot, "lab-build", "player-linker-inputs", requestId + ".il2cpp.json"); }
    static void MarkInvalid(string reason) { invalid = true; if (String.IsNullOrEmpty(failure)) failure = reason; }
    static void WatchBuildEnd()
    {
        if (activeReport == null || BuildPipeline.isBuildingPlayer || EditorApplication.timeSinceStartup - preprocessTime < 5.0) return;
        MarkInvalid("build_ended_without_postprocess_callback");
        WriteFailureWitness();
        StopListening();
    }
    static void StopListening()
    {
        if (listening) Application.logMessageReceived -= OnLog;
        listening = false;
        if (updateListening) EditorApplication.update -= WatchBuildEnd;
        updateListening = false;
    }
    static void Reset()
    {
        StopListening(); activeReport = null; requestId = sourceCommit = inputId = projectRoot = workRoot = line = projectRelativeInput = reportGuid = failure = null;
        inventory = null; invalid = false; preprocessTime = 0;
    }
    static bool TryWorkRoot(string project, out string root)
    {
        root = null;
        string[] args = Environment.GetCommandLineArgs();
        int index = Array.IndexOf(args, "-labWorkRoot");
        if (index < 0)
        {
            // Match PlayerLinkerInputCapture.WorkRoot and LabBuild.BuildRoot
            // for the normal work/lab-project editor project.
            root = Path.GetFullPath(Path.Combine(project, ".."));
            return true;
        }
        if (index + 1 >= args.Length || Array.LastIndexOf(args, "-labWorkRoot") != index) return false;
        string candidate = Path.GetFullPath(args[index + 1]);
        string allowed = Path.GetFullPath(Path.Combine(project, ".rebuild", "unity"));
        string prefix = allowed.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!candidate.StartsWith(prefix, StringComparison.Ordinal)) return false;
        root = candidate;
        return true;
    }
    static void RejectReparseAncestors(string root, string path)
    {
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string current = Path.GetFullPath(path);
        while (current != null)
        {
            if ((File.Exists(current) || Directory.Exists(current)) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("Capture path contains a symbolic link or reparse point");
            if (String.Equals(current, fullRoot, StringComparison.Ordinal)) return;
            current = Path.GetDirectoryName(current);
        }
        throw new InvalidOperationException("Capture path escaped designated root");
    }
    static bool Hex(string value, int length) { return value != null && value.Length == length && value.All(ch => ch >= '0' && ch <= '9' || ch >= 'a' && ch <= 'f'); }
    static bool Token(string value) { return !String.IsNullOrEmpty(value) && value.Length <= 80 && value.All(ch => Char.IsLetterOrDigit(ch) || ch == '.' || ch == '_' || ch == '-'); }
}
