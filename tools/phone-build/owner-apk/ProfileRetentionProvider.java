package dev.ror2owner.bootstrap;

import android.app.Activity;
import android.app.Application;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Build;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.os.StatFs;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** Bounded control-only IPC. Backups NEVER leave the game's UID/private storage.
 * The ordinary installer and game can have different signing keys. The public
 * installer certificate is pinned by the owner build, not learned from callers.
 */
public final class ProfileRetentionProvider extends ContentProvider {
    static final Object LOCK = new Object();
    private static boolean unityStarted;
    private String installerPackage, installerCertificate;
    private int writes;
    private int[] reads;
    private ProfileStore store;
    private boolean configured;

    @Override public boolean onCreate() {
        try {
            Context context = getContext();
            JSONObject policy;
            try (InputStream in = context.getAssets().open("owner-bootstrap/retention-policy.json"); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] bytes = new byte[1024]; int count;
                while ((count = in.read(bytes)) != -1) { if (out.size() + count > 8192) throw new IOException("Retention policy exceeds bound"); out.write(bytes, 0, count); }
                policy = new JSONObject(new String(out.toByteArray(), StandardCharsets.UTF_8));
            }
            installerPackage = policy.getString("installer_package");
            installerCertificate = policy.getString("installer_certificate_sha256");
            if (policy.length() != 4 || policy.getInt("schema") != 1 || !installerPackage.matches("[A-Za-z][A-Za-z0-9_]*(?:\\.[A-Za-z][A-Za-z0-9_]*)+") || !installerCertificate.matches("[0-9a-f]{64}")) throw new IOException("Retention trust policy invalid");
            JSONObject schemas = policy.getJSONObject("data_schema");
            writes = schemas.getInt("writes"); JSONArray accepted = schemas.getJSONArray("reads");
            if (schemas.length() != 2 || writes <= 0 || accepted.length() == 0 || accepted.length() > 32) throw new IOException("Retention schema policy invalid");
            reads = new int[accepted.length()]; boolean includesWrite = false;
            for (int i = 0; i < reads.length; i++) {
                reads[i] = accepted.getInt(i); if (reads[i] <= 0) throw new IOException("Retention schema policy invalid");
                for (int j = 0; j < i; j++) if (reads[j] == reads[i]) throw new IOException("Retention schema policy duplicated");
                includesWrite |= reads[i] == writes;
            }
            if (!includesWrite) throw new IOException("Retention writer must read its own schema");
            // This release has no native schema migration. Do not relabel restored
            // old bytes with a newer writer declaration just because JSON says so.
            if (writes != ProfileStore.DATA_SCHEMA || reads.length != 1 || reads[0] != ProfileStore.DATA_SCHEMA)
                throw new IOException("Native retention schema migration unavailable");
            store = openStore(context);
            ((Application) context.getApplicationContext()).registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
                public void onActivityCreated(Activity activity, Bundle state) { if (activity.getClass().getName().startsWith("com.unity3d.player.")) synchronized (LOCK) { unityStarted = true; } }
                public void onActivityStarted(Activity activity) {}
                public void onActivityResumed(Activity activity) {}
                public void onActivityPaused(Activity activity) {}
                public void onActivityStopped(Activity activity) {}
                public void onActivitySaveInstanceState(Activity activity, Bundle state) {}
                public void onActivityDestroyed(Activity activity) {}
            });
            configured = true;
        } catch (Exception failure) { configured = false; }
        return true; // Fail closed at each call; never expose an unbound bridge.
    }
    private static ProfileStore openStore(Context context) throws IOException {
        File live = context.getExternalFilesDir(null);
        if (live == null) throw new IOException("App-specific profile storage unavailable");
        // Normalize only framework-owned storage roots (Android may alias /data/user/0).
        // The fixed vault child and every retained path still reject redirection.
        return new ProfileStore(live.getCanonicalFile(), new File(context.getNoBackupFilesDir().getCanonicalFile(), "owner-profile-retention"), new ProfileStore.Environment() {
            public long availableBytes(File directory) { return new StatFs(directory.toString()).getAvailableBytes(); }
            public void checkpoint(String stage) {}
            public void syncDirectory(File directory) throws IOException {
                FileDescriptor descriptor = null;
                try {
                    descriptor = Os.open(directory.toString(), OsConstants.O_RDONLY | OsConstants.O_NOFOLLOW, 0);
                    if (!OsConstants.S_ISDIR(Os.fstat(descriptor).st_mode)) throw new IOException("Retention sync target is not a directory");
                    Os.fsync(descriptor);
                }
                catch (ErrnoException failure) { throw new IOException("Retention directory sync failed", failure); }
                finally { if (descriptor != null) try { Os.close(descriptor); } catch (ErrnoException failure) { throw new IOException("Retention directory close failed", failure); } }
            }
        });
    }
    /** Called inside the only exported launch path before Unity is requested. */
    static void beforeUnityLaunch(Context context) throws IOException {
        synchronized (LOCK) {
            if (openStore(context).frozen()) throw new IOException("Finish local profile recovery in the installer before launching");
            unityStarted = true; // A failed launch is conservatively quiescent only after process restart.
        }
    }
    private void authorize() throws Exception {
        if (!configured) throw new SecurityException("Retention bridge is unavailable");
        PackageManager manager = getContext().getPackageManager();
        String[] packages = manager.getPackagesForUid(Binder.getCallingUid());
        // Shared-UID callers are refused rather than trusting a package-name extra.
        if (packages == null || packages.length != 1 || !installerPackage.equals(packages[0])) throw new SecurityException("Untrusted retention caller");
        PackageInfo info = manager.getPackageInfo(installerPackage, Build.VERSION.SDK_INT >= 28 ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES);
        if (info.applicationInfo == null || info.applicationInfo.uid != Binder.getCallingUid()) throw new SecurityException("Retention caller UID differs");
        Signature[] signatures = Build.VERSION.SDK_INT >= 28 ? info.signingInfo.getApkContentsSigners() : info.signatures;
        byte[][] certificates = signatures == null ? null : new byte[signatures.length][];
        if (signatures != null) for (int i = 0; i < signatures.length; i++) certificates[i] = signatures[i].toByteArray();
        if (!ProfileStore.authorized(installerPackage, installerCertificate, packages, certificates)) throw new SecurityException("Retention caller certificate differs");
    }
    @Override public Bundle call(String method, String argument, Bundle extras) {
        try {
            authorize();
            if (argument != null || extras == null) throw new IOException("Retention request invalid");
            if (!("snapshot".equals(method) || "verify".equals(method) || "restore".equals(method) || "release".equals(method) || "status".equals(method))) throw new IOException("Retention method unavailable");
            int schema = extras.getInt("expected_schema", 0);
            String token = extras.getString("snapshot");
            synchronized (LOCK) {
                // Historical release proof is safe even while new gameplay writes
                // progress. It reads only the bounded private lease journal.
                if ("status".equals(method)) {
                    ProfileStore.Status state = store.status(token, schema, reads);
                    Bundle response = new Bundle(); response.putString("status", "verified");
                    response.putString("snapshot", state.token); response.putInt("data_schema", state.schema);
                    response.putString("state", state.state); return response;
                }
                // Unity/native save threads may outlive an Activity. No activity-count guess.
                if (unityStarted) throw new IOException("Fully stop the game before local backup or recovery");
                ProfileStore.Snapshot result;
                if ("snapshot".equals(method)) {
                    if (!extras.getBoolean("user_requested", false) || schema != writes) throw new IOException("Explicit compatible local backup required");
                    result = store.snapshot(schema);
                } else if ("restore".equals(method)) result = store.restore(token, schema, reads);
                else {
                    result = store.verify(token, schema, reads);
                    if ("release".equals(method)) store.release(token, schema, reads);
                }
                Bundle response = new Bundle();
                response.putString("status", "verified"); response.putString("snapshot", result.token);
                response.putInt("data_schema", result.schema); response.putInt("files", result.files); response.putLong("bytes", result.bytes);
                return response;
            }
        } catch (SecurityException denied) { throw denied; }
        catch (Exception failure) {
            Bundle response = new Bundle(); response.putString("status", "blocked");
            // Never return raw paths or saved data. The installer retains the token for retry.
            response.putString("message", "Local profile retention is blocked. Fully stop the game, check free storage, and retry with a compatible release.");
            return response;
        }
    }
    private static SecurityException noData() { return new SecurityException("Retention IPC has no file/data export"); }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) { throw noData(); }
    @Override public String getType(Uri uri) { throw noData(); }
    @Override public Uri insert(Uri uri, ContentValues values) { throw noData(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw noData(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw noData(); }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) { throw noData(); }
}
