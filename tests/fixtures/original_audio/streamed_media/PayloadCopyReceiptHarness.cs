using System;
using System.Collections;
using System.Reflection;
using System.IO;
using System.Security.Cryptography;
using System.Text;

public static class PayloadCopyReceiptHarness
{
    private const string InfoHash = "2b8430716d15c1ac9f78e1cc7625dc2206df6b5081b06b54c8048979d99b6407";
    private const string Input = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88";
    private static int failures;

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
            string path = Path.Combine(directory, "Media.wem");
            byte[] data = Encoding.UTF8.GetBytes("same-payload");
            File.WriteAllBytes(path, data);
            string hash;
            using (SHA256 sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
            Check((bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), "matching existing WEM accepted");
            File.WriteAllText(path, "changed");
            Check(!(bool)InvokeStatic("ExistingPayloadMatches", path, hash, (long)data.Length), "changed existing WEM refused");
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
        TestTemporaryPathOwnership();
        Console.WriteLine(failures == 0 ? "PASS" : "FAILURES " + failures);
        return failures == 0 ? 0 : 1;
    }
}
