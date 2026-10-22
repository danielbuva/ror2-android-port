using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;

// Copies the receipt-verified authored cohort from packaged StreamingAssets to
// the exact Android SoundBankPersistentDataPath selected by the original Wwise
// settings. This helper does not set native paths or call Wwise.
public sealed class GameAudioOriginalPayloadCopy : IGameAudioOriginalPayloadCopyOperation
{
    [Serializable]
    private sealed class Receipt
    {
        public string schema;
        public string accepted_input_id;
        public string soundbanks_info_sha256;
        public int requested_banks;
        public string output_relative_directory;
        public bool runtime_private_copy_required;
        public Entry[] outputs;
        public MediaEntry[] streamed_media;
    }

    [Serializable]
    private sealed class MediaEntry
    {
        public long media_id;
        public string relative_path;
        public string sha256;
        public long size_bytes;
        public string[] referenced_by;
    }

    [Serializable]
    private sealed class Entry
    {
        public string filename;
        public string sha256;
        public long size_bytes;
        public string requested_name;
    }

    private const string ExpectedInput = "6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88";
    private const string ExpectedSoundbanksInfo = "2b8430716d15c1ac9f78e1cc7625dc2206df6b5081b06b54c8048979d99b6407";
    private const string ExpectedDirectory = "Audio/GeneratedSoundBanks/Android";
    private const float CopyDeadlineSeconds = 300.0f;
    private readonly string streamingRoot;
    private readonly string persistentRoot;
    private readonly HashSet<string> expectedNames;
    private readonly string expectedReceiptSha256;
    private string refusal;

    public GameAudioOriginalPayloadCopy(string streamingRootPath, string persistentRootPath,
        IEnumerable<string> sourceBankNames, string receiptSha256)
    {
        streamingRoot = (streamingRootPath ?? throw new ArgumentNullException(nameof(streamingRootPath))).TrimEnd('/', '\\');
        persistentRoot = Path.GetFullPath(persistentRootPath ?? throw new ArgumentNullException(nameof(persistentRootPath)));
        if (!ValidHash(receiptSha256)) throw new ArgumentException("A request-bound receipt SHA-256 is required.", nameof(receiptSha256));
        expectedReceiptSha256 = receiptSha256;
        expectedNames = new HashSet<string>(StringComparer.Ordinal);
        if (sourceBankNames == null) throw new ArgumentNullException(nameof(sourceBankNames));
        foreach (string name in sourceBankNames)
        {
            if (String.IsNullOrEmpty(name) || name.IndexOfAny(new[] { '/', '\\' }) >= 0 || !expectedNames.Add(name))
                throw new ArgumentException("Source bank names must be unique safe leaves.", nameof(sourceBankNames));
        }
        if (expectedNames.Count != 153) throw new ArgumentException("Expected current source cohort is exactly 153 names.", nameof(sourceBankNames));
    }

    public string Refusal { get { return refusal; } }
    public string PersistentRoot { get { return persistentRoot; } }

    public IEnumerator CopyToOriginalSearchRoot()
    {
        // The accepted native Android IO adds persistentDataPath as its POSIX
        // search root. SetBasePath alone changes the APK/OBB lookup, so a
        // nonempty bank subfolder is not qualified by this copy operation.
        if (!NativeSearchRootMatches(persistentRoot, Application.persistentDataPath))
        { refusal = "persistent_bank_subfolder_not_qualified_for_native_io"; yield break; }
        float deadline = Time.realtimeSinceStartup + CopyDeadlineSeconds;
        Receipt receipt = null;
        using (var request = UnityWebRequest.Get(Url("stage-receipt.json")))
        {
            request.timeout = RemainingTimeout(deadline);
            yield return request.SendWebRequest();
            if (request.result != UnityWebRequest.Result.Success)
            { refusal = "stage_receipt_read_failed:" + request.result; yield break; }
            if (Time.realtimeSinceStartup >= deadline)
            { refusal = "stage_receipt_read_deadline_exceeded"; yield break; }
            if (!EqualsHash(Sha256(request.downloadHandler.data), expectedReceiptSha256))
            { refusal = "stage_receipt_hash_mismatch"; yield break; }
            try { receipt = JsonUtility.FromJson<Receipt>(request.downloadHandler.text); }
            catch (Exception error) { refusal = "stage_receipt_parse_failed:" + error.GetType().Name; yield break; }
        }
        if (!ValidateReceipt(receipt)) yield break;
        if (!EnsurePrivateDirectoryTree(persistentRoot, Application.persistentDataPath))
        { refusal = "persistent_search_root_missing_or_reparse"; yield break; }
        if (receipt.streamed_media.Length > 0 && !EnsurePrivateDirectoryTree(Path.Combine(persistentRoot, "Media"), Application.persistentDataPath))
        { refusal = "persistent_media_directory_missing_or_reparse"; yield break; }

        long pendingBytes = 0;
        long largestPending = 0;
        foreach (Entry entry in receipt.outputs)
        {
            string destination = Path.Combine(persistentRoot, entry.filename);
            if (Directory.Exists(destination))
            { refusal = "persistent_bank_conflict:" + entry.filename; yield break; }
            if (File.Exists(destination))
            {
                if (IsReparse(destination) || !Matches(destination, entry.sha256, entry.size_bytes))
                { refusal = "persistent_bank_conflict:" + entry.filename; yield break; }
            }
            else { pendingBytes = checked(pendingBytes + entry.size_bytes); largestPending = Math.Max(largestPending, entry.size_bytes); }
        }
        foreach (MediaEntry entry in receipt.streamed_media)
        {
            string destination = Path.Combine(persistentRoot, entry.relative_path.Replace('/', Path.DirectorySeparatorChar));
            if (PathExistsIncludingReparse(destination) &&
                (!File.Exists(destination) || Directory.Exists(destination) || IsReparse(destination) || !Matches(destination, entry.sha256, entry.size_bytes)))
            { refusal = "persistent_media_conflict:" + entry.media_id; yield break; }
            if (File.Exists(destination))
            {
                if (IsReparse(destination) || !Matches(destination, entry.sha256, entry.size_bytes))
                { refusal = "persistent_media_conflict:" + entry.media_id; yield break; }
            }
            else { pendingBytes = checked(pendingBytes + entry.size_bytes); largestPending = Math.Max(largestPending, entry.size_bytes); }
        }
        long available;
        if (!TryAvailableBytes(persistentRoot, out available) || available < checked(pendingBytes + largestPending))
        { refusal = "persistent_payload_space_insufficient_or_unknown"; yield break; }

        foreach (Entry entry in receipt.outputs)
        {
            if (Time.realtimeSinceStartup >= deadline)
            { refusal = "payload_copy_deadline_exceeded"; yield break; }
            string destination = Path.Combine(persistentRoot, entry.filename);
            if (File.Exists(destination))
            {
                if (IsReparse(destination) || !Matches(destination, entry.sha256, entry.size_bytes))
                { refusal = "persistent_bank_conflict:" + entry.filename; yield break; }
                continue;
            }
            string temporary = destination + ".audio-copy-" + Guid.NewGuid().ToString("N") + ".part";
            try
            {
                if (File.Exists(temporary) || Directory.Exists(temporary))
                { refusal = "persistent_bank_temporary_conflict:" + entry.filename; yield break; }
                using (var request = UnityWebRequest.Get(Url(ExpectedDirectory + "/" + entry.filename)))
                {
                    request.timeout = RemainingTimeout(deadline);
                    request.downloadHandler = new DownloadHandlerFile(temporary, false);
                    yield return request.SendWebRequest();
                    if (request.result != UnityWebRequest.Result.Success)
                    { refusal = "bank_payload_read_failed:" + entry.filename + ":" + request.result; yield break; }
                }
                if (Time.realtimeSinceStartup >= deadline)
                { refusal = "payload_copy_deadline_exceeded:" + entry.filename; yield break; }
                if (!Matches(temporary, entry.sha256, entry.size_bytes))
                { refusal = "bank_payload_hash_mismatch:" + entry.filename; yield break; }
                if (File.Exists(destination) || Directory.Exists(destination))
                { refusal = "persistent_bank_race:" + entry.filename; yield break; }
                File.Move(temporary, destination);
                temporary = null;
                if (!Matches(destination, entry.sha256, entry.size_bytes))
                { refusal = "persistent_bank_postcopy_mismatch:" + entry.filename; yield break; }
            }
            finally
            {
                if (!String.IsNullOrEmpty(temporary))
                    try { if (File.Exists(temporary) && !IsReparse(temporary)) File.Delete(temporary); }
                    catch { refusal = refusal ?? "persistent_bank_temporary_cleanup_failed:" + entry.filename; }
            }
        }
        long remainingMediaBytes = 0;
        long largestRemainingMedia = 0;
        foreach (MediaEntry entry in receipt.streamed_media)
        {
            string destination = Path.Combine(persistentRoot, entry.relative_path.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(destination))
            {
                remainingMediaBytes = checked(remainingMediaBytes + entry.size_bytes);
                largestRemainingMedia = Math.Max(largestRemainingMedia, entry.size_bytes);
            }
        }
        if (!TryAvailableBytes(persistentRoot, out available) || available < checked(remainingMediaBytes + largestRemainingMedia))
        { refusal = "persistent_media_space_insufficient_or_unknown"; yield break; }
        foreach (MediaEntry entry in receipt.streamed_media)
        {
            if (Time.realtimeSinceStartup >= deadline)
            { refusal = "payload_copy_deadline_exceeded"; yield break; }
            string relative = entry.relative_path.Replace('/', Path.DirectorySeparatorChar);
            string destination = Path.Combine(persistentRoot, relative);
            if (PathExistsIncludingReparse(destination))
            {
                if (!ExistingPayloadMatches(destination, entry.sha256, entry.size_bytes))
                { refusal = "persistent_media_conflict:" + entry.media_id; yield break; }
                continue;
            }
            string temporary = destination + ".audio-copy-" + Guid.NewGuid().ToString("N") + ".part";
            try
            {
                if (!TemporaryPathAvailable(temporary))
                { refusal = "persistent_media_temporary_conflict:" + entry.media_id; yield break; }
                using (var request = UnityWebRequest.Get(Url(ExpectedDirectory + "/" + entry.relative_path)))
                {
                    request.timeout = RemainingTimeout(deadline);
                    request.downloadHandler = new DownloadHandlerFile(temporary, false);
                    yield return request.SendWebRequest();
                    if (request.result != UnityWebRequest.Result.Success)
                    { refusal = "media_payload_read_failed:" + entry.media_id + ":" + request.result; yield break; }
                }
                if (Time.realtimeSinceStartup >= deadline)
                { refusal = "payload_copy_deadline_exceeded:" + entry.media_id; yield break; }
                if (!Matches(temporary, entry.sha256, entry.size_bytes))
                { refusal = "media_payload_hash_mismatch:" + entry.media_id; yield break; }
                if (File.Exists(destination) || Directory.Exists(destination))
                { refusal = "persistent_media_race:" + entry.media_id; yield break; }
                File.Move(temporary, destination);
                temporary = null;
                if (!Matches(destination, entry.sha256, entry.size_bytes))
                { refusal = "persistent_media_postcopy_mismatch:" + entry.media_id; yield break; }
            }
            finally
            {
                if (!String.IsNullOrEmpty(temporary))
                    try { if (File.Exists(temporary) && !IsReparse(temporary)) File.Delete(temporary); }
                    catch { refusal = refusal ?? "persistent_media_temporary_cleanup_failed:" + entry.media_id; }
            }
        }
    }

    internal static bool NativeSearchRootMatches(string bankRoot, string appRoot)
    {
        try
        {
            if (String.IsNullOrEmpty(bankRoot) || String.IsNullOrEmpty(appRoot)) return false;
            return String.Equals(Path.GetFullPath(bankRoot).TrimEnd(Path.DirectorySeparatorChar),
                Path.GetFullPath(appRoot).TrimEnd(Path.DirectorySeparatorChar), StringComparison.Ordinal);
        }
        catch { return false; }
    }

    private static int RemainingTimeout(float deadline)
    {
        float remaining = deadline - Time.realtimeSinceStartup;
        if (remaining <= 0f) return 1;
        return Math.Max(1, (int)Math.Ceiling(remaining));
    }

    private bool ValidateReceipt(Receipt receipt)
    {
        if (receipt == null || receipt.schema != "original-game-wwise-bank-cohort-r2" ||
            receipt.accepted_input_id != ExpectedInput || receipt.requested_banks != 153 ||
            receipt.soundbanks_info_sha256 != ExpectedSoundbanksInfo ||
            receipt.output_relative_directory != ExpectedDirectory || !receipt.runtime_private_copy_required ||
            receipt.outputs == null || receipt.outputs.Length != 154 || receipt.streamed_media == null || receipt.streamed_media.Length != 120)
        { refusal = "stage_receipt_contract_mismatch"; return false; }
        var names = new HashSet<string>(StringComparer.Ordinal);
        var banks = new HashSet<string>(StringComparer.Ordinal);
        foreach (Entry row in receipt.outputs)
        {
            if (row == null || !SafeFileName(row.filename) || !ValidHash(row.sha256) || row.size_bytes <= 0 || !names.Add(row.filename))
            { refusal = "stage_receipt_entry_invalid"; return false; }
            if (row.filename == "Init.bnk") continue;
            if (row.filename.Length <= 4 || !row.filename.EndsWith(".bnk", StringComparison.Ordinal) ||
                row.requested_name == null || row.filename != row.requested_name + ".bnk" || !banks.Add(row.requested_name))
            { refusal = "stage_receipt_bank_name_invalid"; return false; }
        }
        if (!names.Contains("Init.bnk") || !banks.SetEquals(expectedNames))
        { refusal = "stage_receipt_missing_or_extra_bank"; return false; }
        var mediaIds = new HashSet<long>();
        foreach (MediaEntry row in receipt.streamed_media)
        {
            if (row == null || row.media_id <= 0 || !mediaIds.Add(row.media_id) ||
                row.relative_path != "Media/" + row.media_id.ToString(System.Globalization.CultureInfo.InvariantCulture) + ".wem" ||
                !ValidHash(row.sha256) || row.size_bytes <= 0 || row.referenced_by == null || row.referenced_by.Length == 0)
            { refusal = "stage_receipt_media_entry_invalid"; return false; }
            var references = new HashSet<string>(StringComparer.Ordinal);
            foreach (string name in row.referenced_by)
                if (!expectedNames.Contains(name) || !references.Add(name))
                { refusal = "stage_receipt_media_reference_invalid"; return false; }
        }
        return true;
    }

    private static bool TryAvailableBytes(string existingPath, out long bytes)
    {
        bytes = 0;
        try
        {
            using (var stat = new AndroidJavaObject("android.os.StatFs", existingPath))
            {
                try { bytes = stat.Call<long>("getAvailableBytes"); }
                catch { bytes = checked(stat.Call<long>("getAvailableBlocksLong") * stat.Call<long>("getBlockSizeLong")); }
            }
            return bytes >= 0;
        }
        catch { return false; }
    }

    private static bool ExistingPayloadMatches(string path, string expectedHash, long expectedSize)
    {
        return File.Exists(path) && !Directory.Exists(path) && !IsReparse(path) && Matches(path, expectedHash, expectedSize);
    }

    private static bool TemporaryPathAvailable(string path)
    {
        return !PathExistsIncludingReparse(path);
    }

    private static bool PathExistsIncludingReparse(string path)
    {
        if (File.Exists(path) || Directory.Exists(path)) return true;
        try { File.GetAttributes(path); return true; }
        catch (FileNotFoundException) { return false; }
        catch (DirectoryNotFoundException) { return false; }
        catch { return true; }
    }

    private string Url(string relative) { return streamingRoot + "/" + relative.Replace('\\', '/'); }
    private static bool SafeFileName(string value) => !String.IsNullOrEmpty(value) && value != "." && value != ".." &&
        value.IndexOfAny(new[] { '/', '\\', ':' }) < 0;
    private static bool ValidHash(string value)
    {
        if (value == null || value.Length != 64) return false;
        foreach (char c in value) if (!Uri.IsHexDigit(c)) return false;
        return true;
    }
    private static string Sha256(byte[] data)
    {
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant();
    }
    private static bool EqualsHash(string left, string right) => String.Equals(left, right, StringComparison.OrdinalIgnoreCase);
    private static bool IsReparse(string path)
    {
        try { return (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0; }
        catch { return true; }
    }
    internal static bool EnsurePrivateDirectoryTree(string path, string appPersistentPath)
    {
        try
        {
            string full = Path.GetFullPath(path);
            string appRoot = Path.GetFullPath(appPersistentPath ?? String.Empty).TrimEnd(Path.DirectorySeparatorChar);
            if (String.IsNullOrEmpty(appRoot) || (full != appRoot && !full.StartsWith(appRoot + Path.DirectorySeparatorChar, StringComparison.Ordinal)))
                return false;
            string root = Path.GetPathRoot(full);
            if (String.IsNullOrEmpty(root)) return false;
            if (!Directory.Exists(appRoot) || File.Exists(appRoot)) return false;
            string appPath = appRoot.Substring(root.Length);
            string appCursor = root;
            foreach (string segment in appPath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
            {
                if (String.IsNullOrEmpty(segment)) continue;
                appCursor = Path.Combine(appCursor, segment);
                if (!Directory.Exists(appCursor) || File.Exists(appCursor) || IsReparse(appCursor)) return false;
            }
            string relative = full.Substring(appRoot.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string current = appRoot;
            foreach (string segment in relative.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
            {
                if (String.IsNullOrEmpty(segment)) continue;
                current = Path.Combine(current, segment);
                if (!Directory.Exists(current) && !File.Exists(current)) Directory.CreateDirectory(current);
                if (File.Exists(current) || IsReparse(current)) return false;
            }
            return Directory.Exists(full) && !IsReparse(full);
        }
        catch { return false; }
    }
    private static bool Matches(string path, string expectedHash, long expectedSize)
    {
        var info = new FileInfo(path);
        if (!info.Exists || info.Length != expectedSize) return false;
        using (var file = File.OpenRead(path))
        using (var sha = SHA256.Create())
        {
            string actual = BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
            return String.Equals(actual, expectedHash, StringComparison.OrdinalIgnoreCase);
        }
    }
}
