using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.UnityLinker;
using UnityEngine;

// Fixture-only input observer. Never included in the game project/player.
public sealed class ContentFixtureLinkerCapture : IUnityLinkerProcessor
{
    [Serializable] public sealed class Row { public string name; public string sha256; public long bytes; }
    [Serializable] public sealed class Receipt
    {
        public string unity;
        public string source_commit;
        public string build_report_guid;
        public string input_directory;
        public Row[] files;
    }

    public int callbackOrder { get { return Int32.MaxValue; } }

    static string Hash(string path)
    {
        using (var algorithm = SHA256.Create())
        using (var stream = File.OpenRead(path))
            return BitConverter.ToString(algorithm.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    static string Relative(string root, string path)
    {
        string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string full = Path.GetFullPath(path);
        if (!full.StartsWith(prefix, StringComparison.Ordinal)) throw new Exception("Fixture linker path escapes its root");
        string current = full;
        while (current.Length >= prefix.Length)
        {
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) throw new Exception("Fixture linker path contains a link");
            current = Path.GetDirectoryName(current);
        }
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0) throw new Exception("Fixture linker root is a link");
        return full.Substring(prefix.Length).Replace(Path.DirectorySeparatorChar, '/');
    }

    public string GenerateAdditionalLinkXmlFile(BuildReport report, UnityLinkerBuildPipelineData data)
    {
        if (Application.unityVersion != "2021.3.45f2" || report == null || data == null || data.target != UnityEditor.BuildTarget.Android)
            throw new Exception("Exact Android fixture linker callback required");
        string project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        string oracle = Environment.GetEnvironmentVariable("ROR2_PHONE_ORACLE_REPORT");
        string commit = Environment.GetEnvironmentVariable("ROR2_PHONE_BUILD_SOURCE");
        if (String.IsNullOrEmpty(oracle) || String.IsNullOrEmpty(commit) || commit.Length != 40 || !commit.All(Uri.IsHexDigit))
            throw new Exception("Explicit fixture build identity required");
        string output = Path.GetDirectoryName(Path.GetFullPath(oracle));
        if (Path.GetDirectoryName(output) != Path.GetDirectoryName(project) || !Directory.Exists(output))
            throw new Exception("Fixture linker output must be the owned build attempt");
        Relative(Path.GetDirectoryName(project), output);
        string input = Path.GetFullPath(data.inputDirectory);
        string relativeInput = Relative(project, input);
        string capture = Path.Combine(output, "linker-capture");
        if (Directory.Exists(capture)) throw new Exception("Refusing ambiguous repeated fixture linker capture");
        Directory.CreateDirectory(capture);
        string[] files = Directory.GetFiles(input, "*", SearchOption.AllDirectories).OrderBy(path => path, StringComparer.Ordinal).ToArray();
        Row[] rows = files.Select(path =>
        {
            string name = Relative(input, path);
            string before = Hash(path);
            string destination = Path.Combine(capture, "inputs", name);
            Directory.CreateDirectory(Path.GetDirectoryName(destination));
            File.Copy(path, destination, false);
            if (Hash(path) != before || Hash(destination) != before) throw new Exception("Fixture linker input changed during capture");
            return new Row { name = name, sha256 = before, bytes = new FileInfo(destination).Length };
        }).ToArray();
        var receipt = new Receipt { unity = Application.unityVersion, source_commit = commit, build_report_guid = report.summary.guid.ToString(), input_directory = relativeInput, files = rows };
        File.WriteAllText(Path.Combine(capture, "receipt.json"), JsonUtility.ToJson(receipt, true));
        string empty = Path.Combine(capture, "empty-linker.xml");
        File.WriteAllText(empty, "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<linker />\n");
        return empty;
    }
}
