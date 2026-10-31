package dev.ror2lab.phonebuildhostfixture;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.os.Build;
import java.io.*;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Locale;

/** Installs a completed owner build without uninstalling or touching game data. */
public final class OwnerInstaller {
    public static final String STATUS = "owner-install";

    public static String state(Context app) {
        return app.getSharedPreferences(STATUS, 0).getString("state", "IDLE");
    }

    public static boolean busy(Context app) {
        return "INSTALLING".equals(state(app)) || "AWAITING_CONFIRMATION".equals(state(app)) || "VERIFYING_PROFILE".equals(state(app)) || "RECOVERING_PROFILE".equals(state(app));
    }

    public static void clearTerminalStatus(Context app) {
        if (busy(app) || OwnerAlphaInstall.pending(app)) throw new IllegalStateException("Installation or profile recovery is pending");
        app.getSharedPreferences(STATUS, 0).edit().putString("state", "IDLE").putString("status", "").putString("session", "").commit();
    }

    public static String status(Context app) {
        return app.getSharedPreferences(STATUS, 0).getString("status", "");
    }

    private static void status(Context app, String state, String value) {
        app.getSharedPreferences(STATUS, 0).edit().putString("state", state).putString("status", value).commit();
        ToolHostActivity.updateInstallCheckpoint(app, state, value);
    }

    public static String signer(PackageInfo info) throws Exception {
        if (info.signatures == null || info.signatures.length != 1)
            throw new IOException("Exactly one owner signing certificate required");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        StringBuilder value = new StringBuilder();
        for (byte b : hash.digest(info.signatures[0].toByteArray())) value.append(String.format(Locale.ROOT, "%02x", b & 255));
        return value.toString();
    }

    public static long version(PackageInfo info) {
        return Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
    }

    private static void verifyInstalled(Context app) throws Exception {
        String name = app.getSharedPreferences(STATUS, 0).getString("package", "");
        PackageInfo actual = app.getPackageManager().getPackageInfo(name, PackageManager.GET_SIGNATURES);
        if (!Long.toString(version(actual)).equals(app.getSharedPreferences(STATUS, 0).getString("version", "")) ||
            !signer(actual).equals(app.getSharedPreferences(STATUS, 0).getString("signer", "")))
            throw new IOException("Installed identity differs from owner build");
        if (OwnerAlphaInstall.PACKAGE.equals(name)) OwnerAlphaInstall.complete(app, actual);
        status(app, "INSTALLED", "Installation complete; exact identity verified and any pre-update profile/settings snapshot verified. No uninstall or game-data reset was performed.");
    }

    /** Called only when this process has no install thread; reconcile after recreation. */
    public static void reconcile(Context app) {
        if (!busy(app)) return;
        if ("VERIFYING_PROFILE".equals(state(app)) || "RECOVERING_PROFILE".equals(state(app))) { OwnerBuildService.launch(app, "install-verify"); return; }
        try {
            int id = Integer.parseInt(app.getSharedPreferences(STATUS, 0).getString("session", "-1"));
            PackageInstaller installer = app.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionInfo session = installer.getSessionInfo(id);
            if (session == null) {
                if (OwnerAlphaInstall.pending(app)) {
                    status(app, "VERIFYING_PROFILE", "Verifying installed identity and retained profiles/settings…");
                    OwnerBuildService.launch(app, "install-verify");
                } else verifyInstalled(app);
            }
            else if (Build.VERSION.SDK_INT >= 26 && !session.isSealed()) {
                installer.abandonSession(id);
                recoverLater(app, "Installation was interrupted before commit. Rebuild to allocate a fresh version before retrying.");
            }
        } catch (Exception error) { recoverLater(app, "Installation interrupted or not verified: " + error.getMessage()); }
    }

    public static void install(Context app, File apk, String expectedHash) throws Exception {
        install(app, apk, expectedHash, null, 0);
    }

    public static synchronized void install(Context app, File apk, String expectedHash, String expectedPackage, long expectedVersion) throws Exception {
        if (busy(app)) throw new IOException("An installation is already pending");
        PackageManager manager = app.getPackageManager();
        PackageInfo next = manager.getPackageArchiveInfo(apk.getPath(), PackageManager.GET_SIGNATURES);
        if (next == null || next.signatures == null || next.signatures.length == 0)
            throw new IOException("Signed owner APK required");
        if (expectedPackage != null && (!expectedPackage.equals(next.packageName) || expectedVersion != version(next)))
            throw new IOException("Built package/version differs from verified release");
        String nextSigner = signer(next);
        PackageInfo current = null;
        try { current = manager.getPackageInfo(next.packageName, PackageManager.GET_SIGNATURES); }
        catch (PackageManager.NameNotFoundException absent) { /* first install */ }
        if (current != null) {
            long oldVersion = version(current);
            long newVersion = version(next);
            if (newVersion <= oldVersion) throw new IOException("Update version must increase");
            if (!Arrays.equals(current.signatures, next.signatures))
                throw new IOException("Owner signing key differs. Retain the original key; never uninstall to update or roll back.");
        }
        if (OwnerAlphaInstall.PACKAGE.equals(next.packageName)) {
            try { OwnerAlphaInstall.prepare(app, apk, expectedHash, next, current); }
            catch (Exception error) { failed(app, error.getMessage()); throw error; }
        }
        PackageInstaller installer = manager.getPackageInstaller();
        PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(next.packageName);
        params.setSize(apk.length());
        if (Build.VERSION.SDK_INT >= 31 && current != null)
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        int id;
        try { id = installer.createSession(params); }
        catch (Exception error) { failed(app, "Could not create installation session: " + error.getMessage()); throw error; }
        boolean committed = false;
        try (PackageInstaller.Session session = installer.openSession(id)) {
            if (!app.getSharedPreferences(STATUS, 0).edit().putString("session", Integer.toString(id))
                .putString("package", next.packageName).putString("version", Long.toString(version(next)))
                .putString("signer", nextSigner).commit()) throw new IOException("Could not retain installation identity");
            status(app, "INSTALLING", "Installing " + next.packageName + "…");
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            try (InputStream input = new FileInputStream(apk);
                 OutputStream output = session.openWrite("base.apk", 0, apk.length())) {
                byte[] buffer = new byte[65536]; int count;
                while ((count = input.read(buffer)) != -1) {
                    hash.update(buffer, 0, count); output.write(buffer, 0, count);
                }
                StringBuilder actual = new StringBuilder();
                for (byte value : hash.digest()) actual.append(String.format(Locale.ROOT, "%02x", value & 255));
                if (!actual.toString().equals(expectedHash)) throw new IOException("Owner APK output drift");
                session.fsync(output);
            }
            Intent callback = new Intent(app, Result.class).setAction(app.getPackageName() + ".OWNER_INSTALL");
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;
            PendingIntent result = PendingIntent.getBroadcast(app, id, callback, flags);
            session.commit(result.getIntentSender());
            committed = true;
        } finally {
            if (!committed) {
                installer.abandonSession(id);
                failed(app, "Installation did not complete. Rebuild for a fresh issued code before retrying.");
            }
        }
    }

    private static void recoverLater(Context app, String message) {
        if (OwnerAlphaInstall.pending(app)) {
            status(app, "RECOVERING_PROFILE", message);
            if (!OwnerBuildService.isRunning()) OwnerBuildService.launch(app, "install-verify");
        } else status(app, "ERROR", message);
    }

    private static void failed(Context app, String message) {
        try {
            boolean installed = OwnerAlphaInstall.recover(app);
            status(app, installed ? "INSTALLED" : "ERROR", installed ? "Installation complete after verified profile/settings recovery." : message);
        }
        catch (Exception error) { status(app, "RECOVERY_REQUIRED", message + " Profile recovery remains pending. Fully stop the game, ensure free space, then tap Recover and verify retained profile/settings: " + error.getMessage()); }
    }

    public static void finishVerification(Context app) {
        if ("RECOVERING_PROFILE".equals(state(app))) { failed(app, status(app)); return; }
        try { verifyInstalled(app); }
        catch (Exception error) { failed(app, "Could not verify installation: " + error.getMessage()); }
    }

    public static void recoverProfiles(Context app) {
        try {
            boolean installed = OwnerAlphaInstall.recover(app);
            status(app, installed ? "INSTALLED" : "ERROR", installed ? "Installation complete after verified profile/settings recovery." :
                "Previous profile/settings verified and released. Rebuild before retrying installation.");
        } catch (Exception error) { status(app, "RECOVERY_REQUIRED", "Profile recovery remains pending. Fully stop the game, ensure free space, then retry recovery: " + error.getMessage()); }
    }

    public static final class Result extends BroadcastReceiver {
        @Override public void onReceive(Context app, Intent intent) {
            String session = app.getSharedPreferences(STATUS, 0).getString("session", "");
            if (!session.equals(Integer.toString(intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1)))) return;
            int code = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
            if (code == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                Intent confirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT);
                if (confirmation == null) { status(app, "AWAITING_CONFIRMATION", "Android confirmation unavailable; the existing install session is retained. No second session will be created."); return; }
                status(app, "AWAITING_CONFIRMATION", "Confirm installation in Android, then return here.");
                confirmation.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                try { app.startActivity(confirmation); }
                catch (RuntimeException error) { status(app, "AWAITING_CONFIRMATION", "Android confirmation unavailable; existing session retained: " + error.getMessage()); }
            } else if (code == PackageInstaller.STATUS_SUCCESS) {
                if (OwnerAlphaInstall.pending(app)) {
                    status(app, "VERIFYING_PROFILE", "Verifying installed identity and retained profiles/settings…");
                    if (!OwnerBuildService.isRunning()) OwnerBuildService.launch(app, "install-verify");
                    return;
                }
                try {
                    verifyInstalled(app);
                } catch (Exception error) { failed(app, "Could not verify installation: " + error.getMessage()); }
            } else {
                String message = "Installation failed: " + intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
                recoverLater(app, message);
            }
        }
    }
}
