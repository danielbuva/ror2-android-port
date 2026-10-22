// Existing editor owner: optional Bee post-strip capture for the exact opted-in ARM64 lab build.
using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;
using Process = System.Diagnostics.Process;

public sealed class Il2CppInvocationCapture : IPreprocessBuildWithReport, IPostprocessBuildWithReport
{
    const string EditorPin = "2021.3.45f2 (88f88f591b2e)";
    static string requestId, sourceCommit, inputId, guid, project, work, logPath, prePath;
    static long logOffset;
    static string preHash;
    public int callbackOrder { get { return int.MaxValue; } }

#pragma warning disable 0649
    [Serializable] sealed class Request { public string request_id, sourceCommit, inputId; public bool captureIl2CppInvocation; }
    [Serializable] sealed class Identity { public string input_id; }
    [Serializable] sealed class EditorProcess { public string log; public int pid; }
    [Serializable] sealed class FileRow { public string path, sha256; public long size; }
    [Serializable] sealed class PreReceipt
    {
        public string schema = "ror2lab-bee-prebuild-v2";
        public string request_id, source_commit, input_id, build_report_guid, target, editor_version;
        public string editor_log_path;
        public int editor_pid;
        public string scan_root = "Library/Bee";
        public string scan_started_utc, scan_completed_utc, baseline_sha256;
        public int baseline_file_count;
        public long log_byte_offset;
        public string editor_log_prefix_sha256;
        public FileRow[] baseline_files;
    }
    [Serializable] sealed class PostReceipt
    {
        public string schema = "ror2lab-bee-postprocess-v2";
        public string request_id, source_commit, input_id, build_report_guid, target;
        public string build_report_result, build_report_output_path;
        public int build_report_errors;
        public string prebuild_sha256, log_slice_path, log_slice_sha256;
        public long log_byte_start, log_byte_end;
    }
#pragma warning restore 0649

    public void OnPreprocessBuild(BuildReport report)
    {
        Reset();
        string activeId = SessionState.GetString("PortingLab.ARM64Running", "");
        if (!Token(activeId)) return;
        try
        {
            project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            work = WorkRoot(project);
            Request request = JsonUtility.FromJson<Request>(File.ReadAllText(Path.Combine(work, "build-request.json")));
            if (request == null || !request.captureIl2CppInvocation) return;
            if (request.request_id != activeId || !Token(request.request_id) || !Hex(request.sourceCommit, 40) || !Hex(request.inputId, 64))
                throw new InvalidOperationException("Bee capture request/source identity is invalid");
            if (UnityEditorInternal.InternalEditorUtility.GetFullUnityVersion() != EditorPin)
                throw new InvalidOperationException("Bee capture editor version differs from its pinned schema");
            if (report == null || report.summary.platform != BuildTarget.Android)
                throw new InvalidOperationException("Bee capture requires the Android BuildReport");
            ValidateInputIdentity(request.inputId);
            EditorProcess process = JsonUtility.FromJson<EditorProcess>(File.ReadAllText(Path.Combine(work, "editor", "lab-process.json")));
            if (process == null || process.pid != Process.GetCurrentProcess().Id || String.IsNullOrEmpty(process.log))
                throw new InvalidOperationException("Editor.log owner does not match the active Unity process");
            logPath = Path.GetFullPath(process.log);
            RejectReparseAncestors(work, logPath);
            if (!File.Exists(logPath)) throw new InvalidOperationException("Active Editor.log is missing");
            logOffset = new FileInfo(logPath).Length;
            requestId = request.request_id; sourceCommit = request.sourceCommit; inputId = request.inputId;
            guid = report.summary.guid.ToString();
            string scanStarted = DateTime.UtcNow.ToString("o");
            FileRow[] rows = InventoryBeeFiles(project);
            string scanCompleted = DateTime.UtcNow.ToString("o");
            var pre = new PreReceipt {
                request_id = requestId, source_commit = sourceCommit, input_id = inputId,
                build_report_guid = guid, target = report.summary.platform.ToString(),
                editor_version = UnityEditorInternal.InternalEditorUtility.GetFullUnityVersion(),
                editor_log_path = logPath, editor_pid = Process.GetCurrentProcess().Id,
                scan_started_utc = scanStarted, scan_completed_utc = scanCompleted,
                baseline_file_count = rows.Length, baseline_sha256 = HashInventory(rows),
                log_byte_offset = logOffset,
                editor_log_prefix_sha256 = HashRange(logPath, 0, logOffset), baseline_files = rows
            };
            prePath = Path.Combine(work, "lab-build", "player-linker-inputs", requestId + ".bee-pre.json");
            WriteNew(prePath, JsonUtility.ToJson(pre, true));
            preHash = HashFile(prePath);
        }
        catch (Exception exception)
        {
            // The player build remains authoritative; the host refuses a missing receipt.
            Debug.LogWarning("Bee IL2CPP capture pre-build witness unavailable: " + exception.GetType().Name);
            Reset();
        }
    }

    public void OnPostprocessBuild(BuildReport report)
    {
        // Unity may invoke this callback before BuildPipeline.BuildPlayer returns,
        // while its summary still reports Unknown. LabBuild owns finalization from
        // the BuildReport returned by BuildPlayer. Keep the pre-build witness alive.
    }

    public static void CompleteAfterBuild(BuildReport report)
    {
        if (String.IsNullOrEmpty(requestId)) return;
        try
        {
            string reportFailure = BuildReportFailure(report, guid);
            if (reportFailure != null)
            {
                Debug.LogWarning("Bee IL2CPP capture post-build witness unavailable: " + reportFailure);
                return;
            }
            if (HashFile(prePath) != preHash) throw new InvalidOperationException("Bee pre-build receipt changed");
            if (new FileInfo(logPath).Length < logOffset) throw new InvalidOperationException("Editor.log shortened after pre-build boundary");
            if (HashRange(logPath, 0, logOffset) != ReadPrePrefixHash(prePath))
                throw new InvalidOperationException("Editor.log prefix changed after pre-build boundary");
            long end = new FileInfo(logPath).Length;
            byte[] slice = ReadRange(logPath, logOffset, end - logOffset);
            string slicePath = Path.Combine(work, "lab-build", "player-linker-inputs", requestId + ".bee-log-slice");
            WriteNewBytes(slicePath, slice);
            var post = new PostReceipt {
                request_id = requestId, source_commit = sourceCommit, input_id = inputId,
                build_report_guid = guid, target = report.summary.platform.ToString(),
                build_report_result = report.summary.result.ToString(),
                build_report_output_path = Path.GetFullPath(report.summary.outputPath),
                build_report_errors = (int)report.summary.totalErrors, prebuild_sha256 = preHash,
                log_byte_start = logOffset, log_byte_end = end,
                log_slice_path = Relative(work, slicePath), log_slice_sha256 = Hash(slice)
            };
            WriteNew(Path.Combine(work, "lab-build", "player-linker-inputs", requestId + ".bee-post.json"), JsonUtility.ToJson(post, true));
        }
        catch (Exception exception)
        {
            Debug.LogWarning("Bee IL2CPP capture post-build witness unavailable: " + exception.GetType().Name);
        }
        finally { Reset(); }
    }

    static string BuildReportFailure(BuildReport report, string expectedGuid)
    {
        const string expected = "expectedTarget=Android expectedResult=Succeeded expectedErrors=0";
        if (report == null) return "reason=report-null " + expected + " expectedGuid=" + expectedGuid;
        string actualGuid = Convert.ToString(report.summary.guid);
        string identity = "actualTarget=" + report.summary.platform +
            " actualResult=" + report.summary.result +
            " actualErrors=" + report.summary.totalErrors +
            " actualGuid=" + actualGuid + " " + expected + " expectedGuid=" + expectedGuid;
        if (report.summary.platform != BuildTarget.Android) return "reason=target-mismatch " + identity;
        if (actualGuid != expectedGuid) return "reason=build-report-guid-mismatch " + identity;
        if (report.summary.result != BuildResult.Succeeded) return "reason=build-report-result-mismatch " + identity;
        if (report.summary.totalErrors != 0) return "reason=build-report-errors-nonzero " + identity;
        return null;
    }

    static FileRow[] InventoryBeeFiles(string root)
    {
        string bee = Path.Combine(root, "Library", "Bee");
        string artifacts = Path.Combine(bee, "artifacts");
        if (!Directory.Exists(bee) || !Directory.Exists(artifacts)) throw new InvalidOperationException("Bee inventory roots are missing");
        RejectReparseAncestors(root, bee); RejectReparseAncestors(root, artifacts);
        string[] files = Directory.GetFiles(bee, "Player*.dag", SearchOption.TopDirectoryOnly)
            .Concat(Directory.GetFiles(bee, "Player*.dag.json", SearchOption.TopDirectoryOnly))
            .Concat(Directory.GetFiles(artifacts, "il2cpp_conv_*.traceevents", SearchOption.TopDirectoryOnly))
            .Distinct(StringComparer.Ordinal).OrderBy(path => path, StringComparer.Ordinal).ToArray();
        return files.Select(path => DescribeStableFile(root, path)).ToArray();
    }
    static FileRow DescribeStableFile(string root, string path)
    {
        RejectReparseAncestors(root, path);
        long before = new FileInfo(path).Length; string first = HashFile(path);
        long after = new FileInfo(path).Length; string second = HashFile(path);
        if (before != after || first != second) throw new InvalidOperationException("Bee baseline file changed during inventory");
        return new FileRow { path = Relative(root, path).Replace(Path.DirectorySeparatorChar, '/'), size = after, sha256 = second };
    }
    static void ValidateInputIdentity(string expected)
    {
        string markerPath = Path.Combine(project, ".port-input.json");
        string inventoryPath = Path.Combine(work, "inventory", "files.json");
        if (!File.Exists(markerPath) || !File.Exists(inventoryPath)) throw new InvalidOperationException("Accepted input identity files are missing");
        Identity marker = JsonUtility.FromJson<Identity>(File.ReadAllText(markerPath));
        Identity inventory = JsonUtility.FromJson<Identity>(File.ReadAllText(inventoryPath));
        if (marker == null || inventory == null || marker.input_id != expected || inventory.input_id != expected)
            throw new InvalidOperationException("Accepted input identity changed");
    }
    static string ReadPrePrefixHash(string path) { return JsonUtility.FromJson<PreReceipt>(File.ReadAllText(path)).editor_log_prefix_sha256; }
    static byte[] ReadRange(string path, long offset, long count)
    {
        if (count < 0 || count > 128L * 1024 * 1024) throw new InvalidOperationException("Editor.log slice exceeds capture bound");
        byte[] data = new byte[(int)count];
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) {
            if (offset + count > stream.Length) throw new InvalidOperationException("Editor.log changed during slice capture");
            stream.Seek(offset, SeekOrigin.Begin); int read = 0;
            while (read < data.Length) { int next = stream.Read(data, read, data.Length - read); if (next == 0) throw new EndOfStreamException(); read += next; }
        }
        return data;
    }
    static string HashRange(string path, long offset, long count)
    {
        if (count < 0) throw new InvalidOperationException("Editor.log hash range is negative");
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var sha = SHA256.Create()) { stream.Seek(offset, SeekOrigin.Begin); byte[] buffer = new byte[1024 * 1024]; while (count > 0) { int read = stream.Read(buffer, 0, (int)Math.Min(buffer.Length, count)); if (read == 0) throw new EndOfStreamException(); sha.TransformBlock(buffer, 0, read, buffer, 0); count -= read; } sha.TransformFinalBlock(new byte[0], 0, 0); return String.Concat(sha.Hash.Select(x => x.ToString("x2"))); }
    }
    static string HashFile(string path) { using (var stream = File.OpenRead(path)) using (var sha = SHA256.Create()) return String.Concat(sha.ComputeHash(stream).Select(x => x.ToString("x2"))); }
    static string Hash(byte[] bytes) { using (var sha = SHA256.Create()) return String.Concat(sha.ComputeHash(bytes).Select(x => x.ToString("x2"))); }
    static string HashInventory(FileRow[] rows) { string body=String.Join("\n",rows.Select(row=>row.path+"\t"+row.size+"\t"+row.sha256));return Hash(new UTF8Encoding(false).GetBytes(body)); }
    static string Relative(string root, string path) { string a=Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,b=Path.GetFullPath(path); if(!b.StartsWith(a,StringComparison.Ordinal))throw new InvalidOperationException("Capture path escaped root");return b.Substring(a.Length); }
    static string WorkRoot(string p) { string[] a=Environment.GetCommandLineArgs();int i=Array.IndexOf(a,"-labWorkRoot");if(i<0)return Path.GetFullPath(Path.Combine(p,".."));if(i+1>=a.Length||Array.LastIndexOf(a,"-labWorkRoot")!=i)throw new InvalidOperationException("Invalid isolated work root");string root=Path.GetFullPath(a[i+1]),allowed=Path.GetFullPath(Path.Combine(p,".rebuild","unity"))+Path.DirectorySeparatorChar;if(!root.StartsWith(allowed,StringComparison.Ordinal))throw new InvalidOperationException("Work root is outside the destination contract");return root; }
    static void RejectReparseAncestors(string root,string path) { string current=Path.GetFullPath(path),stop=Path.GetFullPath(root);while(current!=null){if((File.Exists(current)||Directory.Exists(current))&&(File.GetAttributes(current)&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("Capture path contains a reparse point");if(current==stop)return;current=Path.GetDirectoryName(current);}throw new InvalidOperationException("Capture path escaped designated root"); }
    static void WriteNew(string path,string text) { WriteNewBytes(path,new UTF8Encoding(false).GetBytes(text)); }
    static void WriteNewBytes(string path,byte[] bytes) { Relative(work,path);RejectReparseAncestors(work,path);Directory.CreateDirectory(Path.GetDirectoryName(path));RejectReparseAncestors(work,path);using(var stream=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))stream.Write(bytes,0,bytes.Length); }
    static bool Token(string value) { return !String.IsNullOrEmpty(value)&&value.Length<=80&&value.All(x=>Char.IsLetterOrDigit(x)||x=='.'||x=='_'||x=='-'); }
    static bool Hex(string value,int length) { return value!=null&&value.Length==length&&value.All(x=>x>='0'&&x<='9'||x>='a'&&x<='f'); }
    static void Reset() { requestId=sourceCommit=inputId=guid=project=work=logPath=prePath=preHash=null;logOffset=0; }
}
