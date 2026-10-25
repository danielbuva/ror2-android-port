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
    private static final String STATUS = "owner-install";

    public static String status(Context app) {
        return app.getSharedPreferences(STATUS, 0).getString("status", "");
    }

    private static void status(Context app, String value) {
        app.getSharedPreferences(STATUS, 0).edit().putString("status", value).commit();
    }

    public static void install(Context app, File apk, String expectedHash) throws Exception {
        PackageManager manager = app.getPackageManager();
        PackageInfo next = manager.getPackageArchiveInfo(apk.getPath(), PackageManager.GET_SIGNATURES);
        if (next == null || next.signatures == null || next.signatures.length == 0)
            throw new IOException("Signed owner APK required");
        PackageInfo current = null;
        try { current = manager.getPackageInfo(next.packageName, PackageManager.GET_SIGNATURES); }
        catch (PackageManager.NameNotFoundException absent) { /* first install */ }
        if (current != null) {
            long oldVersion = Build.VERSION.SDK_INT >= 28 ? current.getLongVersionCode() : current.versionCode;
            long newVersion = Build.VERSION.SDK_INT >= 28 ? next.getLongVersionCode() : next.versionCode;
            if (newVersion <= oldVersion) throw new IOException("Update version must increase");
            if (!Arrays.equals(current.signatures, next.signatures))
                throw new IOException("Owner signing key differs. Export saves before reinstalling; never uninstall to update.");
        }
        PackageInstaller installer = manager.getPackageInstaller();
        PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(next.packageName);
        params.setSize(apk.length());
        if (Build.VERSION.SDK_INT >= 31 && current != null)
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        int id = installer.createSession(params);
        boolean committed = false;
        try (PackageInstaller.Session session = installer.openSession(id)) {
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
            status(app, "Installing " + next.packageName + "…");
            session.commit(result.getIntentSender());
            committed = true;
        } finally {
            if (!committed) installer.abandonSession(id);
        }
    }

    public static final class Result extends BroadcastReceiver {
        @Override public void onReceive(Context app, Intent intent) {
            int code = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
            if (code == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                Intent confirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT);
                if (confirmation == null) { status(app, "Installation confirmation unavailable"); return; }
                status(app, "Confirm installation in Android, then return here.");
                confirmation.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                app.startActivity(confirmation);
            } else if (code == PackageInstaller.STATUS_SUCCESS) {
                status(app, "Installation complete. Existing saves retained.");
            } else {
                status(app, "Installation failed: " + intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE));
            }
        }
    }
}
