using System;
using System.Collections;
using System.Reflection;
using System.Runtime.InteropServices;
using System.IO;
using System.Security.Cryptography;
using System.Text;

public static class PayloadCopyReceiptHarness
{
    private const string InfoHash = "2b8430716d15c1ac9f78e1cc7625dc2206df6b5081b06b54c8048979d99b6407";
    private const string Input = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88";
    private static int failures;

    [DllImport("libc", SetLastError = true)]
    private static extern int symlink(string target, string linkpath);

    private static void Check(bool value, string name)
    {
        if (!value) { Console.Error.WriteLine("FAIL " + name); failures++; }
    }

    private static object Make(string typeName)
    {
        Type type = typeof(GameAudioOriginalPayloadCopy).GetNestedType(typeName, BindingFlags.NonPublic);
        return Activator.CreateInstance(type, true);
    }

    private static void Set(object target, string field, object value)
    { target.GetType().GetField(field).SetValue(target, value); }

    private static object Receipt(string badMediaPath = null, bool duplicateMedia = false, bool badReference = false, bool wrongInfoHash = false)
    {
        object receipt = Make("Receipt");
        Set(receipt, "schema", "original-game-wwise-bank-cohort-r2");
        Set(receipt, "accepted_input_id", Input);
        Set(receipt, "soundbanks_info_sha256", wrongInfoHash ? new string('e', 64) : InfoHash);
        Set(receipt, "requested_banks", 153);
        Set(receipt, "output_relative_directory", "Audio/GeneratedSoundBanks/Android");
        Set(receipt, "runtime_private_copy_required", true);
        string[] names = new string[153];
        Type entryType = typeof(GameAudioOriginalPayloadCopy).GetNestedType("Entry", BindingFlags.NonPublic);
        Array outputs = Array.CreateInstance(entryType, 154);
        outputs.SetValue(Make("Entry"), 0);
        Set(outputs.GetValue(0), "filename", "Init.bnk");
        Set(outputs.GetValue(0), "sha256", new string('a', 64));
        Set(outputs.GetValue(0), "size_bytes", 1L);
        for (int i = 0; i < names.Length; i++)
        {
            names[i] = "Bank" + i;
            outputs.SetValue(Make("Entry"), i + 1);
            Set(outputs.GetValue(i + 1), "filename", names[i] + ".bnk");
            Set(outputs.GetValue(i + 1), "sha256", new string('b', 64));
            Set(outputs.GetValue(i + 1), "size_bytes", 1L);
            Set(outputs.GetValue(i + 1), "requested_name", names[i]);
        }
        Set(receipt, "outputs", outputs);
        Type mediaType = typeof(GameAudioOriginalPayloadCopy).GetNestedType("MediaEntry", BindingFlags.NonPublic);
        Array media = Array.CreateInstance(mediaType, 120);
        for (int i = 0; i < media.Length; i++)
        {
            long id = i + 1000;
            media.SetValue(Make("MediaEntry"), i);
            Set(media.GetValue(i), "media_id", id);
            Set(media.GetValue(i), "relative_path", i == 0 && badMediaPath != null ? badMediaPath : "Media/" + id + ".wem");
            Set(media.GetValue(i), "sha256", new string('c', 64));
            Set(media.GetValue(i), "size_bytes", 5L);
            Set(media.GetValue(i), "referenced_by", new[] { "Bank0" });
        }
        if (duplicateMedia) Set(media.GetValue(1), "media_id", 1000L);
        if (badReference) Set(media.GetValue(0), "referenced_by", new[] { "UnselectedBank" });
        Set(receipt, "streamed_media", media);
        return receipt;
    }

    private static bool Validate(object receipt)
    {
        string[] names = new string[153];
        for (int i = 0; i < names.Length; i++) names[i] = "Bank" + i;
        var owner = new GameAudioOriginalPayloadCopy("file:///unused", "/tmp/app/Audio/GeneratedSoundBanks/Android", names, new string('d', 64));
        MethodInfo validate = typeof(GameAudioOriginalPayloadCopy).GetMethod("ValidateReceipt", BindingFlags.NonPublic | BindingFlags.Instance);
        return (bool)validate.Invoke(owner, new[] { receipt });
    }

    private static object InvokeStatic(string method, params object[] args)
    {
        MethodInfo target = typeof(GameAudioOriginalPayloadCopy).GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static);
        return target.Invoke(null, args);
    }

    private static void TestExistingPayloadRevalidation()
    {
        string directory = Path.Combine(Path.GetTempPath(), "wwise-copy-check-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            byte[] data = Encoding.UTF8.GetBytes("same-payload");
            string hash;
            using (SHA256 sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
            foreach (string leaf in new[] { "Bank.bnk", "Media.wem" })
            {
                string path = Path.Combine(directory, leaf);
                File.WriteAllBytes(path, data);
                Check((bool)InvokeStatic("ExistingPayloadHasExpectedSize", path, (long)data.Length), leaf + " matching metadata accepted");
                Check((bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), leaf + " matching reuse accepted");
                File.WriteAllText(path, "evil-payload");
                Check((bool)InvokeStatic("ExistingPayloadHasExpectedSize", path, (long)data.Length), leaf + " same-size preflight needs no content read");
                Check(!(bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), leaf + " same-size corruption refused at reuse");
                File.WriteAllText(path, "changed");
                Check(!(bool)InvokeStatic("ExistingPayloadHasExpectedSize", path, (long)data.Length), leaf + " changed size refused in preflight");
                Check(!(bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), leaf + " changed size refused at reuse");
                File.Delete(path);
                Directory.CreateDirectory(path);
                Check(!(bool)InvokeStatic("ExistingPayloadHasExpectedSize", path, (long)data.Length), leaf + " directory refused in preflight");
                Check(!(bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), leaf + " directory refused at reuse");
                Directory.Delete(path);
                string target = path + ".target";
                File.WriteAllBytes(target, data);
                Check(symlink(target, path) == 0, leaf + " symlink fixture created");
                Check(!(bool)InvokeStatic("ExistingPayloadHasExpectedSize", path, (long)data.Length), leaf + " symlink refused in preflight");
                Check(!(bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), leaf + " symlink refused at reuse");
                File.Delete(path);
                File.Delete(target);
            }
        }
        finally { Directory.Delete(directory, true); }
    }

    private static void TestTemporaryPathOwnership()
    {
        string directory = Path.Combine(Path.GetTempPath(), "wwise-temp-check-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            string path = Path.Combine(directory, "payload.part");
            Check((bool)InvokeStatic("TemporaryPathAvailable", path), "absent temp path available");
            File.WriteAllText(path, "unowned");
            Check(!(bool)InvokeStatic("TemporaryPathAvailable", path), "unowned temp file refused");
            File.Delete(path);
            Directory.CreateDirectory(path);
            Check(!(bool)InvokeStatic("TemporaryPathAvailable", path), "unowned temp directory refused");
        }
        finally { Directory.Delete(directory, true); }
    }

    private static void TestVerifiedReuse()
    {
        string path = Path.Combine(Path.GetTempPath(), "wwise-verified-" + Guid.NewGuid().ToString("N"));
        byte[] data = Encoding.UTF8.GetBytes("same-payload");
        string hash;
        using (var sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
        var modified = new UnityEngine.AndroidJavaObject("timespec");
        modified.fields["tv_sec"] = 10L; modified.fields["tv_nsec"] = 1L;
        var changed = new UnityEngine.AndroidJavaObject("timespec");
        changed.fields["tv_sec"] = 10L; changed.fields["tv_nsec"] = 2L;
        var stat = new UnityEngine.AndroidJavaObject("stat");
        stat.fields["st_mtim"] = modified; stat.fields["st_ctim"] = changed;
        stat.fields["st_size"] = (long)data.Length; stat.fields["st_dev"] = 1L; stat.fields["st_ino"] = 2L;
        UnityEngine.AndroidJavaClass.onCallStatic = (method, args) => stat;
        string[] names = new string[153]; for (int i = 0; i < names.Length; i++) names[i] = "Bank" + i;
        var owner = new GameAudioOriginalPayloadCopy("file:///unused", "/tmp/app", names, new string('d', 64));
        var methodInfo = typeof(GameAudioOriginalPayloadCopy).GetMethod("VerifiedPayloadMatches", BindingFlags.Instance | BindingFlags.NonPublic);
        var fields = BindingFlags.Instance | BindingFlags.NonPublic;
        Func<bool> verify = () => (bool)methodInfo.Invoke(owner, new object[] { path, hash, (long)data.Length });
        try
        {
            File.WriteAllBytes(path, data);
            Check(verify(), "cache miss fully verifies actual file");
            Check((int)typeof(GameAudioOriginalPayloadCopy).GetField("fullVerifications", fields).GetValue(owner) == 1, "cache miss hashes once");
            var observed = (IList)typeof(GameAudioOriginalPayloadCopy).GetField("observed", fields).GetValue(owner);
            var cache = (IDictionary)typeof(GameAudioOriginalPayloadCopy).GetField("verified", fields).GetValue(owner);
            cache.Add(path, observed[0]);
            Check(verify(), "unchanged verified file reuses receipt");
            Check((int)typeof(GameAudioOriginalPayloadCopy).GetField("cacheHits", fields).GetValue(owner) == 1, "unchanged file hits cache");
            var savedTime = File.GetLastWriteTimeUtc(path);
            File.WriteAllText(path, "evil-payload"); File.SetLastWriteTimeUtc(path, savedTime);
            changed.fields["tv_nsec"] = 3L;
            Check(!verify(), "same-size corruption with restored mtime rejected by changed nanosecond ctime");
            File.WriteAllBytes(path, data); changed.fields["tv_nsec"] = 2L; stat.fields["st_ino"] = 3L;
            Check(verify(), "replaced inode rehashes good bytes");
            Check((int)typeof(GameAudioOriginalPayloadCopy).GetField("fullVerifications", fields).GetValue(owner) == 3, "ctime and inode changes both force hash");
            UnityEngine.AndroidJavaClass.onCallStatic = (method, args) => { throw new Exception("stat unavailable"); };
            File.WriteAllText(path, "evil-payload");
            Check(!verify(), "unavailable Android stat falls back to full corruption check");
        }
        finally { File.Delete(path); UnityEngine.AndroidJavaClass.onCallStatic = null; }
    }

    private static void TestVerifiedCohortInvalidation()
    {
        string directory = Path.Combine(Path.GetTempPath(), "wwise-cache-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        var activity = new UnityEngine.AndroidJavaObject("activity");
        var cacheDirectory = new UnityEngine.AndroidJavaObject("directory");
        cacheDirectory.onCall = (method, args) => directory;
        var package = new UnityEngine.AndroidJavaObject("package");
        package.fields["lastUpdateTime"] = 123L;
        var packages = new UnityEngine.AndroidJavaObject("packages");
        packages.onCall = (method, args) => package;
        activity.onCall = (method, args) => method == "getCacheDir" ? (object)cacheDirectory :
            method == "getPackageManager" ? (object)packages : method == "getPackageName" ? "dev.fixture" : "/installed.apk";
        UnityEngine.AndroidJavaClass.currentActivity = activity;
        var cohortType = typeof(GameAudioOriginalPayloadCopy).GetNestedType("VerifiedCohort", BindingFlags.NonPublic);
        var fileType = typeof(GameAudioOriginalPayloadCopy).GetNestedType("VerifiedFile", BindingFlags.NonPublic);
        var cohort = Activator.CreateInstance(cohortType, true);
        Set(cohort, "install", "/installed.apk|123"); Set(cohort, "receipt", new string('d', 64));
        var file = Activator.CreateInstance(fileType, true); Set(file, "path", "/payload/bank");
        var files = Array.CreateInstance(fileType, 1); files.SetValue(file, 0); Set(cohort, "files", files);
        UnityEngine.JsonUtility.decoded = cohort;
        var flags = BindingFlags.Instance | BindingFlags.NonPublic;
        string[] names = new string[153]; for (int i = 0; i < names.Length; i++) names[i] = "Bank" + i;
        var owner = new GameAudioOriginalPayloadCopy("file:///unused", "/tmp/app", names, new string('d', 64));
        var load = typeof(GameAudioOriginalPayloadCopy).GetMethod("LoadVerifiedCohort", flags);
        var cache = (IDictionary)typeof(GameAudioOriginalPayloadCopy).GetField("verified", flags).GetValue(owner);
        Action reload = () => load.Invoke(owner, null);
        string path = Path.Combine(directory, "original-audio-verified.json");
        try
        {
            reload(); Check(cache.Count == 0, "missing private cache requires full verification");
            File.WriteAllText(path, "fixture"); reload(); Check(cache.Count == 1, "same install and cohort load private receipt");
            package.fields["lastUpdateTime"] = 124L; reload(); Check(cache.Count == 0, "package update invalidates receipt");
            package.fields["lastUpdateTime"] = 123L; Set(cohort, "receipt", new string('e', 64));
            reload(); Check(cache.Count == 0, "changed packaged cohort invalidates receipt");
            Set(cohort, "receipt", new string('d', 64)); reload(); Check(cache.Count == 1, "valid receipt can reload");
            File.Delete(path); reload(); Check(cache.Count == 0, "clear-cache repair invalidates prior in-memory receipt");
        }
        finally
        {
            Directory.Delete(directory, true); UnityEngine.AndroidJavaClass.currentActivity = null;
            UnityEngine.JsonUtility.decoded = null;
        }
    }

    public static int Main()
    {
        Check(GameAudioOriginalPayloadCopy.NativeSearchRootMatches("/owned/app", "/owned/app/"), "same native POSIX root accepted");
        Check(!GameAudioOriginalPayloadCopy.NativeSearchRootMatches("/owned/app/banks", "/owned/app"), "unregistered bank subfolder refused");
        Check(!GameAudioOriginalPayloadCopy.NativeSearchRootMatches("/owned/app-other", "/owned/app"), "different persistent root refused");
        Check(!GameAudioOriginalPayloadCopy.NativeSearchRootMatches("", "/owned/app"), "empty bank root refused");
        Check(Validate(Receipt()), "exact 154-bank and 120-media receipt accepted");
        Check(!Validate(Receipt("Media/../1000.wem")), "traversal media path refused");
        object zeroIdReceipt = Receipt();
        Array zeroIdRows = (Array)zeroIdReceipt.GetType().GetField("streamed_media").GetValue(zeroIdReceipt);
        Set(zeroIdRows.GetValue(0), "media_id", 0L);
        Set(zeroIdRows.GetValue(0), "relative_path", "Media/0.wem");
        Check(!Validate(zeroIdReceipt), "zero media ID refused");
        Check(!Validate(Receipt(duplicateMedia: true)), "duplicate media ID refused");
        Check(!Validate(Receipt(badReference: true)), "unselected bank reference refused");
        Check(!Validate(Receipt(wrongInfoHash: true)), "wrong SoundbanksInfo pin refused");
        object shortReceipt = Receipt();
        Type mediaType = typeof(GameAudioOriginalPayloadCopy).GetNestedType("MediaEntry", BindingFlags.NonPublic);
        Set(shortReceipt, "streamed_media", Array.CreateInstance(mediaType, 119));
        Check(!Validate(shortReceipt), "incomplete streamed-media closure refused");
        TestExistingPayloadRevalidation();
        TestVerifiedReuse();
        TestVerifiedCohortInvalidation();
        TestTemporaryPathOwnership();
        Console.WriteLine(failures == 0 ? "PASS" : "FAILURES " + failures);
        return failures == 0 ? 0 : 1;
    }
}
