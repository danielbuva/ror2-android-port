package dev.ror2lab.phonebuildhostfixture;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.content.pm.VersionedPackage;
import android.os.Build;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import java.io.*;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Locale;
import java.util.UUID;

/** Owns sessions and exact readback for completed owner builds. */
public final class OwnerInstaller {
    public static final String STATUS = "owner-install";
    // The framework-owned intent is process-local and handled on the main thread.
    // Persist only session/status; never serialize or manufacture a consent intent.
    private static String confirmationSession;
    private static Intent pendingConfirmation;
    private static boolean confirmationOpened;
    private static volatile boolean removalInFlight;
    private static final String REMOVING = "REMOVING_MISPLACED";

    private static String removalAction(Context app) {
        return app.getPackageName() + ".REMOVE_MISPLACED." + app.getSharedPreferences(STATUS, 0).getString("version", "");
    }

    static boolean hasConfirmation(Context app) {
        if (pendingConfirmation == null || confirmationOpened) return false;
        return REMOVING.equals(state(app)) ? confirmationSession.equals(removalAction(app)) :
            "AWAITING_CONFIRMATION".equals(state(app)) && confirmationSession.equals(app.getSharedPreferences(STATUS, 0).getString("session", ""));
    }

    static void openConfirmation(Context activity) {
        if (!hasConfirmation(activity)) return;
        boolean removal = REMOVING.equals(state(activity));
        try {
            activity.startActivity(pendingConfirmation);
        } catch (RuntimeException unavailable) {
            status(activity, removal ? REMOVING : "AWAITING_CONFIRMATION", removal ?
                OwnerInstallPlacement.REFUSED + " Tap Open Android removal confirmation to retry." :
                "Android confirmation could not open. Tap Open Android install confirmation to retry the existing session.");
            return;
        }
        confirmationOpened = true;
        pendingConfirmation = null;
        status(activity, removal ? REMOVING : "AWAITING_CONFIRMATION", removal ?
            OwnerInstallPlacement.REFUSED + " Confirm removal of the rejected fresh install in Android." : "Complete the Android install confirmation, then return here.");
    }

    public static String state(Context app) {
        return app.getSharedPreferences(STATUS, 0).getString("state", "IDLE");
    }

    public static boolean busy(Context app) {
        String state = state(app);
        return "INSTALLING".equals(state) || "AWAITING_CONFIRMATION".equals(state) || "VERIFYING_PROFILE".equals(state) || "RECOVERING_PROFILE".equals(state) || REMOVING.equals(state);
    }

    public static void clearTerminalStatus(Context app) {
        if (busy(app) || OwnerAlphaInstall.pending(app)) throw new IllegalStateException("Installation or profile recovery is pending");
        confirmationSession = null;
        pendingConfirmation = null;
        confirmationOpened = false;
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
        if (REMOVING.equals(state(app))) {
            if (!removalInFlight) finishRemoval(app);
            return;
        }
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

    // Diagnostics are best effort and never alter install decisions or expose identities.
    private static void diagnostic(Context app, String stage, String callback, boolean match) {
        try { ToolHostActivity.updateInstallDiagnostic(app, stage, callback, match); }
        catch (RuntimeException ignored) { }
    }

    private static void receiverDiagnostic(Context app, String registration, boolean entered) {
        try { ToolHostActivity.updateInstallReceiverDiagnostic(app, registration, entered); }
        catch (RuntimeException ignored) { }
    }

    // Query only our exact packaged receiver; report no class/package/device identities.
    // This is observation only: it must not change permission, commit or recovery behavior.
    private static String receiverRegistration(Context app) {
        try {
            PackageManager manager = app.getPackageManager();
            ComponentName component = new ComponentName(app, Result.class);
            ActivityInfo receiver = manager.getReceiverInfo(component, PackageManager.MATCH_DISABLED_COMPONENTS);
            if (receiver == null || receiver.applicationInfo == null) return "unavailable";
            int setting = manager.getComponentEnabledSetting(component);
            boolean enabled;
            if (setting == PackageManager.COMPONENT_ENABLED_STATE_DEFAULT) enabled = receiver.enabled;
            else if (setting == PackageManager.COMPONENT_ENABLED_STATE_ENABLED) enabled = true;
            else if (setting == PackageManager.COMPONENT_ENABLED_STATE_DISABLED || setting == PackageManager.COMPONENT_ENABLED_STATE_DISABLED_USER
                    || setting == PackageManager.COMPONENT_ENABLED_STATE_DISABLED_UNTIL_USED) enabled = false;
            else return "unavailable";
            if (!enabled || !receiver.applicationInfo.enabled) return "disabled";
            return receiver.exported ? "exported" : "private";
        } catch (PackageManager.NameNotFoundException missing) { return "missing"; }
        catch (RuntimeException unavailable) { return "unavailable"; }
    }

    private static String digestHex(MessageDigest hash) {
        StringBuilder value = new StringBuilder();
        for (byte b : hash.digest()) value.append(String.format(Locale.ROOT, "%02x", b & 255));
        return value.toString();
    }
    private static void verifyPreparedBytes(File apk, String expectedHash) throws Exception {
        if (expectedHash == null || !expectedHash.matches("[0-9a-f]{64}"))
            throw new IOException("Verified APK checksum missing. Rebuild before installing; the installed version was not changed.");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(apk)) {
            byte[] buffer = new byte[65536]; int count;
            while ((count = input.read(buffer)) != -1) hash.update(buffer, 0, count);
        }
        if (!expectedHash.equals(digestHex(hash)))
            throw new IOException("Owner APK output drift: checksum differs. Rebuild before installing; the installed version was not changed.");
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
                throw new IOException("Owner signing key differs. The installed version was not changed. Restore the original key; never uninstall to update or roll back.");
        }
        // Reject corrupt bytes before profile preparation or creation of a
        // package session; keep the streamed hash below to catch later drift.
        verifyPreparedBytes(apk, expectedHash);
        diagnostic(app, "prepare", null, false);
        boolean alpha = OwnerAlphaInstall.PACKAGE.equals(next.packageName);
        if (alpha) {
            try {
                UUID adopted = OwnerInstallPlacement.required(app) ? OwnerInstallPlacement.preflight(app,
                    current == null ? null : current.applicationInfo, apk.length()) : null;
                OwnerAlphaInstall.prepare(app, apk, expectedHash, next, current, adopted);
            }
            catch (Exception error) { failed(app, error.getMessage()); throw error; }
        }
        PackageInstaller installer = manager.getPackageInstaller();
        PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(next.packageName);
        params.setSize(apk.length());
        if (alpha) params.setInstallLocation(PackageInfo.INSTALL_LOCATION_PREFER_EXTERNAL);
        if (Build.VERSION.SDK_INT >= 31 && current != null)
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        int id;
        diagnostic(app, "session-create", null, false);
        try { id = installer.createSession(params); }
        catch (Exception error) { failed(app, "Could not create installation session: " + error.getMessage()); throw error; }
        boolean committed = false;
        diagnostic(app, "session-open", null, false);
        try (PackageInstaller.Session session = installer.openSession(id)) {
            String installing = "Installing " + next.packageName + "…";
            // Session ownership and active admission must survive recreation together.
            // A separate unchecked status commit could leave a committed session idle.
            if (!app.getSharedPreferences(STATUS, 0).edit().putString("session", Integer.toString(id))
                .putString("package", next.packageName).putString("version", Long.toString(version(next)))
                .putString("signer", nextSigner).putString("state", "INSTALLING").putString("status", installing).commit())
                throw new IOException("Could not retain installation identity");
            ToolHostActivity.updateInstallCheckpoint(app, "INSTALLING", installing);
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            diagnostic(app, "write-start", null, false);
            try (InputStream input = new FileInputStream(apk);
                 OutputStream output = session.openWrite("base.apk", 0, apk.length())) {
                byte[] buffer = new byte[65536]; int count;
                while ((count = input.read(buffer)) != -1) {
                    hash.update(buffer, 0, count); output.write(buffer, 0, count);
                }
                if (!expectedHash.equals(digestHex(hash))) throw new IOException("Owner APK output drift");
                diagnostic(app, "write-complete", null, false);
                diagnostic(app, "fsync-start", null, false);
                session.fsync(output);
                diagnostic(app, "fsync-complete", null, false);
            }
            Intent callback = new Intent(app, Result.class).setAction(app.getPackageName() + ".OWNER_INSTALL");
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;
            PendingIntent result = PendingIntent.getBroadcast(app, id, callback, flags);
            receiverDiagnostic(app, receiverRegistration(app), false);
            diagnostic(app, "commit-start", null, false);
            session.commit(result.getIntentSender());
            diagnostic(app, "commit-returned", null, false);
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
            if (OwnerAlphaInstall.finishPlacementRefusal(app)) { placementRefused(app); return; }
            boolean installed = OwnerAlphaInstall.recover(app);
            status(app, installed ? "INSTALLED" : "ERROR", installed ? "Installation complete after verified profile/settings recovery." : message);
        }
        catch (OwnerAlphaInstall.MisplacedFreshInstall refused) { removeMisplaced(app, refused.version); }
        catch (Exception error) { status(app, "RECOVERY_REQUIRED", message + " Profile recovery remains pending. Fully stop the game, ensure free space, then tap Recover and verify retained profile/settings: " + error.getMessage()); }
    }

    public static void finishVerification(Context app) {
        if ("RECOVERING_PROFILE".equals(state(app))) { failed(app, status(app)); return; }
        try { verifyInstalled(app); }
        catch (OwnerAlphaInstall.MisplacedFreshInstall refused) { removeMisplaced(app, refused.version); }
        catch (Exception error) { failed(app, "Could not verify installation: " + error.getMessage()); }
    }

    public static void recoverProfiles(Context app) {
        try {
            if (OwnerAlphaInstall.finishPlacementRefusal(app)) { placementRefused(app); return; }
            boolean installed = OwnerAlphaInstall.recover(app);
            status(app, installed ? "INSTALLED" : "ERROR", installed ? "Installation complete after verified profile/settings recovery." :
                "Previous profile/settings verified and released. Rebuild before retrying installation.");
        } catch (OwnerAlphaInstall.MisplacedFreshInstall refused) { removeMisplaced(app, refused.version); }
        catch (Exception error) { status(app, "RECOVERY_REQUIRED", "Profile recovery remains pending. Fully stop the game, ensure free space, then retry recovery: " + error.getMessage()); }
    }

    private static void placementRefused(Context app) {
        status(app, "ERROR", OwnerInstallPlacement.REFUSED + " The rejected fresh install was removed.");
    }

    private static void finishRemoval(Context app) {
        removalInFlight = false;
        confirmationSession = null;
        pendingConfirmation = null;
        confirmationOpened = false;
        try {
            if (OwnerAlphaInstall.finishPlacementRefusal(app)) { placementRefused(app); return; }
        } catch (Exception ignored) { /* Recover from the persisted refusal. */ }
        status(app, "RECOVERY_REQUIRED", OwnerInstallPlacement.REFUSED + " Removal is unverified. Tap Recover and verify retained profile/settings to retry and confirm in Android.");
    }

    private static void removeMisplaced(Context app, long version) {
        removalInFlight = true;
        status(app, REMOVING, OwnerInstallPlacement.REFUSED + " Requesting removal of the rejected fresh install.");
        try {
            Intent callback = new Intent(app, RemovalResult.class).setAction(removalAction(app));
            PendingIntent result = PendingIntent.getBroadcast(app, 0, callback, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_MUTABLE);
            app.getPackageManager().getPackageInstaller().uninstall(new VersionedPackage(OwnerAlphaInstall.PACKAGE, version), result.getIntentSender());
        } catch (RuntimeException unavailable) { finishRemoval(app); }
    }

    public static final class RemovalResult extends BroadcastReceiver {
        @Override public void onReceive(Context app, Intent intent) {
            String action = removalAction(app);
            if (!REMOVING.equals(state(app)) || !action.equals(intent.getAction())) return;
            if (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE) == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                if (confirmationOpened) return;
                pendingConfirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT);
                if (pendingConfirmation == null) { finishRemoval(app); return; }
                confirmationSession = action;
                removalInFlight = true;
                status(app, REMOVING, OwnerInstallPlacement.REFUSED + " Tap Open Android removal confirmation to remove the rejected fresh install.");
                ToolHostActivity visible = ToolHostActivity.activeForConfirmation();
                if (visible != null) openConfirmation(visible);
            } else finishRemoval(app);
        }
    }

    public static final class Result extends BroadcastReceiver {
        @Override public void onReceive(Context app, Intent intent) {
            receiverDiagnostic(app, null, true);
            String session = app.getSharedPreferences(STATUS, 0).getString("session", "");
            boolean matches = session.equals(Integer.toString(intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1)));
            int code = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
            diagnostic(app, null, code == PackageInstaller.STATUS_PENDING_USER_ACTION ? "pending-user-action" : code == PackageInstaller.STATUS_SUCCESS ? "success" : code == PackageInstaller.STATUS_FAILURE ? "failure" : "unknown", matches);
            if (!matches || (!"INSTALLING".equals(state(app)) && !"AWAITING_CONFIRMATION".equals(state(app)))) return;
            if (code == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                if (!session.equals(confirmationSession)) {
                    confirmationSession = session;
                    pendingConfirmation = null;
                    confirmationOpened = false;
                }
                if (confirmationOpened) return;
                Intent confirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT);
                if (confirmation != null) pendingConfirmation = confirmation;
                if (pendingConfirmation == null) {
                    status(app, "AWAITING_CONFIRMATION", "Android confirmation unavailable; the existing install session is retained. No second session will be created.");
                    return;
                }
                status(app, "AWAITING_CONFIRMATION", "Android confirmation required. If the prompt is not visible, return to the installer and tap Open Android install confirmation.");
                ToolHostActivity visible = ToolHostActivity.activeForConfirmation();
                if (visible != null) openConfirmation(visible);
                // Otherwise the ongoing build notification returns the owner here.
                // A visible button also works when notifications are disabled.
                return;
            }
            confirmationSession = null;
            pendingConfirmation = null;
            confirmationOpened = false;
            if (code == PackageInstaller.STATUS_SUCCESS) {
                if (OwnerAlphaInstall.pending(app)) {
                    status(app, "VERIFYING_PROFILE", "Verifying installed identity and retained profiles/settings…");
                    if (!OwnerBuildService.isRunning()) OwnerBuildService.launch(app, "install-verify");
                    return;
                }
                try {
                    verifyInstalled(app);
                } catch (OwnerAlphaInstall.MisplacedFreshInstall refused) {
                    removeMisplaced(app, refused.version);
                } catch (Exception error) { failed(app, "Could not verify installation: " + error.getMessage()); }
            } else {
                String message = "Installation failed: " + intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
                recoverLater(app, message);
            }
        }
    }
}

/** Preflight and readback for an explicitly adopted-only alpha installation. */
final class OwnerInstallPlacement {
    static final String REFUSED = "Installation unavailable on this placement.";
    private static final String REQUIRE_ADOPTED = "require_adopted_storage";

    static boolean required(Context app) {
        return "true".equals(app.getSharedPreferences(OwnerInstaller.STATUS, 0).getString(REQUIRE_ADOPTED, "false"));
    }

    static boolean select(Context app, boolean required) {
        return app.getSharedPreferences(OwnerInstaller.STATUS, 0).edit().putString(REQUIRE_ADOPTED, Boolean.toString(required)).commit();
    }

    static boolean matches(ApplicationInfo installed, UUID volume) {
        if (installed == null || volume == null || StorageManager.UUID_DEFAULT.equals(volume) || !volume.equals(installed.storageUuid)) return false;
        String root = "/mnt/expand/" + volume + "/";
        return installed.sourceDir != null && installed.sourceDir.startsWith(root + "app/") &&
            installed.dataDir != null && installed.dataDir.startsWith(root);
    }

    static UUID preflight(Context app, ApplicationInfo current, long apkBytes) throws IOException {
        if (Build.VERSION.SDK_INT < 31) throw new IOException(REFUSED + " Adopted-only installation requires Android 12 or newer.");
        if (current != null && !matches(current, current.storageUuid))
            throw new IOException(REFUSED + " The existing game is not on adopted storage. Its data is unchanged.");
        StorageManager storage = app.getSystemService(StorageManager.class);
        UUID selected = null;
        // Android ranks the mounted volumes by allocatable bytes for a fresh session.
        // Refuse when internal storage would win or tie.
        long best = current == null ? storage.getAllocatableBytes(StorageManager.UUID_DEFAULT) : -1;
        for (StorageVolume candidate : storage.getStorageVolumes()) {
            if (!candidate.isEmulated() || !Environment.MEDIA_MOUNTED.equals(candidate.getState())) continue;
            UUID volume = candidate.getStorageUuid();
            if (volume == null || StorageManager.UUID_DEFAULT.equals(volume) || (current != null && !volume.equals(current.storageUuid))) continue;
            long bytes = storage.getAllocatableBytes(volume);
            if (bytes >= apkBytes && bytes > best) {
                selected = volume;
                best = bytes;
            }
        }
        if (selected == null) throw new IOException(REFUSED + " No eligible mounted adopted volume has enough allocatable space.");
        return selected;
    }
}
