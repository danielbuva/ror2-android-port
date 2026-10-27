package dev.ror2lab.phonebuildhostfixture;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import java.io.*;
import java.security.MessageDigest;
import java.util.Locale;
import org.json.*;

/** Alpha admission, local ownership and game-UID retention across one installer session.
 * No game-private paths are opened by the installer: the certificate-bound provider
 * takes and restores the snapshot inside the game UID. All receipts stay private.
 */
public final class OwnerAlphaInstall {
    public static final String PACKAGE = "dev.ror2lab.alpha";
    private static final Uri RETENTION = Uri.parse("content://dev.ror2lab.alpha.retention");
    private static File file(Context app, String name) { return new File(app.getFilesDir(), "owner-input/" + name); }
    private static JSONObject read(Context app, String name) throws Exception { return ToolHostActivity.readJson(file(app, name)); }
    private static void write(Context app, String name, JSONObject value) throws Exception { ToolHostActivity.writeJson(file(app, name), value); }
    private static String digest(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[65536]; int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder result = new StringBuilder();
        for (byte value : digest.digest()) result.append(String.format(Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }
    public static boolean pending(Context app) { return file(app, "pending-install.json").isFile(); }
    public static boolean blocked(Context app) { return "RECOVERY_REQUIRED".equals(OwnerInstaller.state(app)); }
    private static void removePending(Context app) throws IOException {
        if (pending(app) && !file(app, "pending-install.json").delete()) throw new IOException("Could not clear verified retention transaction");
    }
    public static JSONObject owned(Context app, PackageInfo installed) throws Exception { return owned(app, installed, true); }
    public static JSONObject owned(Context app, PackageInfo installed, boolean verifyHash) throws Exception {
        if (!file(app, "installed-release.json").isFile()) throw new IOException("Occupied alpha identity has no local ownership receipt; refusing adoption. Never uninstall to update.");
        JSONObject receipt = read(app, "installed-release.json");
        if (!receipt.getBoolean("installed_readback_verified") || !PACKAGE.equals(installed.packageName) || !PACKAGE.equals(receipt.getString("application_id")) ||
            receipt.getLong("version_code") != OwnerInstaller.version(installed) ||
            !receipt.getString("signer_sha256").equals(OwnerInstaller.signer(installed)) ||
            (verifyHash && !receipt.getString("sha256").equals(digest(new File(installed.applicationInfo.sourceDir)))))
            throw new IOException("Installed alpha identity/hash differs from its local ownership receipt; refusing adoption");
        return receipt;
    }
    private static boolean reads(JSONObject release, int schema) throws Exception {
        JSONArray reads = release.getJSONObject("data_schema").getJSONArray("reads");
        for (int i = 0; i < reads.length(); i++) if (reads.getInt(i) == schema) return true;
        return false;
    }
    private static Bundle provider(Context app, String method, JSONObject transaction) throws Exception {
        Bundle extras = new Bundle();
        extras.putBoolean("user_requested", true);
        extras.putInt("expected_schema", transaction.getInt("data_schema"));
        extras.putString("snapshot", transaction.optString("snapshot", ""));
        Bundle result;
        try { result = app.getContentResolver().call(RETENTION, method, null, extras); }
        catch (RuntimeException failure) { throw new IOException("Profile retention " + method + " refused: " + failure.getMessage(), failure); }
        if (result == null || !"verified".equals(result.getString("status"))) {
            String message = result == null ? null : result.getString("message");
            throw new IOException("Profile retention " + method + " did not verify: " +
                (message == null ? "Fully stop the game (Back/background is not enough), ensure free space, then retry recovery." : message));
        }
        String token = result.getString("snapshot");
        if (token == null || !token.matches("[0-9a-f]{64}") || result.getInt("data_schema", -1) != transaction.getInt("data_schema") ||
            (transaction.has("snapshot") && !transaction.getString("snapshot").equals(token)))
            throw new IOException("Profile retention " + method + " returned another snapshot/schema");
        return result;
    }
    private static void verifyIssued(Context app, JSONObject ready) throws Exception {
        long code = ready.getLong("version_code");
        String hash = ready.getString("sha256"), certificate = ready.getString("signer_sha256");
        JSONObject ledger = read(app, "work/releases/issued-versions.json");
        if (ledger.getInt("schema") != 1 || !PACKAGE.equals(ledger.getString("application_id")) || ledger.getLong("last_issued") < code)
            throw new IOException("Owner-local issued-version ledger identity differs");
        JSONObject issues = ledger.getJSONObject("issues");
        JSONObject issue = issues.getJSONObject(Long.toString(code));
        if (!"signed".equals(issue.getString("status")) || !hash.equals(issue.getString("apk_sha256")) ||
            !certificate.equals(issue.getString("signer_sha256")) || issue.getLong("publisher_version_code") != ready.getJSONObject("release").getLong("version_code"))
            throw new IOException("Signed owner-local issued-version receipt required");
        for (String key : new String[]{"source_sha256", "input_sha256", "toolchain_sha256", "payload_sha256"})
            if (!issue.getString(key).equals(ready.getString(key))) throw new IOException("Issued build binding differs: " + key);
    }
    public static void prepare(Context app, File apk, String hash, PackageInfo next, PackageInfo current) throws Exception {
        if (pending(app)) throw new IOException("A previous profile transaction requires recovery before another installation");
        JSONObject ready = read(app, "owner-apk-ready.json");
        String certificate = OwnerInstaller.signer(next);
        long code = OwnerInstaller.version(next);
        if (!apk.getCanonicalPath().startsWith(file(app, "work/releases").getCanonicalPath() + File.separator))
            throw new IOException("Signed alpha APK must remain in private retained release storage");
        if (!PACKAGE.equals(next.packageName) || !PACKAGE.equals(ready.getString("application_id")) ||
            code <= 0 || code > 2100000000L || code != ready.getLong("version_code") ||
            !certificate.equals(ready.getString("signer_sha256")) || !hash.equals(ready.getString("sha256")) ||
            !apk.getCanonicalPath().equals(new File(ready.getString("apk")).getCanonicalPath()) || !hash.equals(digest(apk)))
            throw new IOException("Alpha build/issued identity differs from the signed ready receipt");
        verifyIssued(app, ready);
        long attempted = Long.parseLong(app.getSharedPreferences(OwnerInstaller.STATUS, 0).getString("last_dispatched_version", "0"));
        if (code <= attempted) throw new IOException("This issued code was already dispatched. Rebuild to allocate a higher code; do not retry a second install session.");
        JSONObject transaction = new JSONObject().put("ready", ready).put("installer_free_bytes_before", app.getFilesDir().getUsableSpace()).put("data_schema", ready.getJSONObject("release").getJSONObject("data_schema").getInt("writes"));
        if (current != null) {
            JSONObject previous = owned(app, current);
            if (!certificate.equals(previous.getString("signer_sha256"))) throw new IOException("Rollback/update must use the same owner signing key");
            int schema = previous.getJSONObject("release").getJSONObject("data_schema").getInt("writes");
            if (!reads(ready.getJSONObject("release"), schema)) throw new IOException("Schema-incompatible update/rollback refused before installation; current profile is unchanged");
            transaction.put("previous", previous).put("data_schema", schema);
        }
        // Retain intent first. A provider interruption can be recovered by its idempotent snapshot call.
        write(app, "pending-install.json", transaction);
        if (current != null) {
            Bundle snapshot = provider(app, "snapshot", transaction);
            String token = snapshot.getString("snapshot");
            if (token == null || !token.matches("[0-9a-f]{64}") || snapshot.getInt("data_schema", -1) != transaction.getInt("data_schema"))
                throw new IOException("Profile backup identity/schema did not verify");
            transaction.put("snapshot", token).put("backup_bytes", snapshot.getLong("bytes", 0)); write(app, "pending-install.json", transaction);
        }
        if (!app.getSharedPreferences(OwnerInstaller.STATUS, 0).edit().putString("last_dispatched_version", Long.toString(code)).commit())
            throw new IOException("Could not durably consume issued version before installation");
    }
    private static boolean retainProfiles(Context app, JSONObject transaction) throws Exception {
        if (!transaction.has("previous")) return false;
        if (!transaction.has("snapshot")) {
            Bundle recovered = provider(app, "snapshot", transaction);
            transaction.put("snapshot", recovered.getString("snapshot")); write(app, "pending-install.json", transaction);
        }
        String phase = provider(app, "status", transaction).getString("state");
        // A released token proves a prior verify+release, not that live data still
        // equals the snapshot: legitimate gameplay may already have resumed.
        if ("released".equals(phase)) return true;
        if (!"active".equals(phase)) throw new IOException("Profile retention lease status is unverified");
        try { provider(app, "verify", transaction); }
        catch (Exception mismatch) { provider(app, "restore", transaction); provider(app, "verify", transaction); }
        return false;
    }
    public static void complete(Context app, PackageInfo installed) throws Exception {
        if (!pending(app)) { owned(app, installed); return; }
        JSONObject transaction = read(app, "pending-install.json"), ready = transaction.getJSONObject("ready");
        if (!PACKAGE.equals(installed.packageName) || OwnerInstaller.version(installed) != ready.getLong("version_code") ||
            !OwnerInstaller.signer(installed).equals(ready.getString("signer_sha256")) ||
            !digest(new File(installed.applicationInfo.sourceDir)).equals(ready.getString("sha256")))
            throw new IOException("Installed alpha package, code, certificate or APK hash did not match exact readback");
        verifyIssued(app, ready);
        boolean released = retainProfiles(app, transaction);
        if (transaction.has("previous")) write(app, "previous-installed-release.json", transaction.getJSONObject("previous"));
        ready.put("installed_readback_verified", true).put("profile_retention_verified", transaction.has("previous"));
        if (transaction.has("snapshot")) ready.put("retention_backup", new JSONObject().put("snapshot", transaction.getString("snapshot")).put("data_schema", transaction.getInt("data_schema")).put("bytes", transaction.optLong("backup_bytes", 0)));
        write(app, "installed-release.json", ready);
        if (transaction.has("snapshot") && !released) provider(app, "release", transaction);
        removePending(app);
    }
    /** Recovery never uninstalls, downgrades or clears data. A failed restore keeps the lock and receipt. */
    public static boolean recover(Context app) throws Exception {
        if (!pending(app)) return false;
        JSONObject transaction = read(app, "pending-install.json"), ready = transaction.getJSONObject("ready");
        PackageInfo actual = null;
        try { actual = app.getPackageManager().getPackageInfo(PACKAGE, PackageManager.GET_SIGNATURES); }
        catch (PackageManager.NameNotFoundException absent) { /* first install failed */ }
        if (actual != null && OwnerInstaller.version(actual) == ready.getLong("version_code")) { complete(app, actual); return true; }
        if (transaction.has("previous")) {
            if (actual == null) throw new IOException("Previously owned alpha disappeared; retention recovery requires the same package/key");
            JSONObject previous = transaction.getJSONObject("previous");
            if (OwnerInstaller.version(actual) != previous.getLong("version_code") || !OwnerInstaller.signer(actual).equals(previous.getString("signer_sha256")) ||
                !digest(new File(actual.applicationInfo.sourceDir)).equals(previous.getString("sha256")))
                throw new IOException("Installed alpha changed during recovery; refusing another identity");
            verifyIssued(app, previous);
            boolean released = retainProfiles(app, transaction);
            if (transaction.has("snapshot") && !released) provider(app, "release", transaction);
        }
        File readyFile = file(app, "owner-apk-ready.json");
        if (readyFile.exists() && !readyFile.delete()) throw new IOException("Could not invalidate the failed ready installation");
        removePending(app);
        return false;
    }
    public static String rollbackStatus(Context app) {
        try {
            if (!file(app, "previous-installed-release.json").isFile()) return "Rollback: no previous verified installed release retained.";
            JSONObject previous = read(app, "previous-installed-release.json");
            PackageInfo actual = app.getPackageManager().getPackageInfo(PACKAGE, PackageManager.GET_SIGNATURES);
            JSONObject current = owned(app, actual, false);
            if (!current.getString("signer_sha256").equals(previous.getString("signer_sha256"))) return "Rollback unavailable: owner signing certificate differs.";
            if (!reads(previous.getJSONObject("release"), current.getJSONObject("release").getJSONObject("data_schema").getInt("writes"))) return "Rollback unavailable: retained release cannot read the current profile schema.";
            File apk = new File(previous.getString("apk"));
            if (!apk.isFile() || apk.length() != previous.getLong("bytes")) return "Rollback unavailable: retained signed APK reference is missing or changed.";
            String backup = current.has("retention_backup") ? "\nLast verified profile/settings snapshot: " + current.getJSONObject("retention_backup").getLong("bytes") + " bytes in game-private storage, separate from the release references." : "";
            return "Rollback eligible: " + previous.getJSONObject("release").optString("version") + ". Rebuild with the same key and a higher issued code.\nRetained signed APKs: " + (apk.length() + new File(current.getString("apk")).length()) + " bytes plus manifests (no copied game data). Older unreferenced release artifacts are pruned at the next release operation; current and previous remain protected." + backup;
        } catch (Exception error) { return "Rollback unavailable: " + error.getMessage(); }
    }
    public static boolean canRollback(Context app) { return !pending(app) && rollbackStatus(app).startsWith("Rollback eligible:"); }
}
