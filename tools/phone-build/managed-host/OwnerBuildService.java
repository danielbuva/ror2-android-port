package dev.ror2lab.phonebuildhostfixture;

import android.app.*;
import android.content.*;
import android.os.*;
import java.io.*;
import org.json.*;

/** Owns the worker, foreground notification and wake lock, independently of any Activity. */
public final class OwnerBuildService extends Service {
    public static final String PREFERENCES = "owner-phone-flow";
    private static final int NOTIFICATION = 119;
    private static final String CHANNEL = "owner-local-build";
    private static volatile boolean running;
    private static volatile boolean pending;
    private volatile String importControl = "continue";
    private volatile boolean destroyed;
    private Thread thread;
    private volatile ToolHostActivity.Worker worker;
    private volatile OwnerInputSource.Access inputAccess;
    private PowerManager.WakeLock wakeLock;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private long lastImportProgress;
    private final Runnable refresh = new Runnable() { public void run() {
        if (!running) return;
        ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(NOTIFICATION, notification());
        handler.postDelayed(this, 1000);
    } };
    public static boolean isRunning() { return running || pending; }
    public static String action(Context app) { return app.getSharedPreferences(PREFERENCES, 0).getString("action", ""); }
    public static synchronized void launch(Context app, String action) {
        if (running || pending) return;
        pending = true;
        Intent intent = new Intent(app, OwnerBuildService.class).setAction(action);
        try { if (Build.VERSION.SDK_INT >= 26) app.startForegroundService(intent); else app.startService(intent); }
        catch (RuntimeException error) { pending = false; throw error; }
    }
    public static void control(Context app, String action) throws Exception {
        app.startService(new Intent(app, OwnerBuildService.class).setAction("control-" + action));
    }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(CHANNEL, "Local game installation", NotificationManager.IMPORTANCE_LOW);
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(channel);
        }
    }
    private PendingIntent command(String action, int code) {
        return PendingIntent.getService(this, code, new Intent(this, OwnerBuildService.class).setAction("control-" + action), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
    private Notification notification() {
        String detail = "Your game files stay on this device";
        try {
            File file = new File(getFilesDir(), "owner-input/" + ("import".equals(action(this)) ? "import-state.json" : "update-state.json"));
            if (file.isFile()) detail = ToolHostActivity.readJson(file).optString("message", detail);
        } catch (Exception ignored) { }
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, ToolHostActivity.class), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.stat_sys_download).setContentTitle("Owner game installer")
            .setContentText(detail).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true);
        if (!"install".equals(action(this)) && !OwnerInstaller.busy(this)) builder.addAction(new Notification.Action.Builder(null, "Pause", command("pause", 1)).build())
            .addAction(new Notification.Action.Builder(null, "Resume", command("resume", 2)).build())
            .addAction(new Notification.Action.Builder(null, "Cancel", command("cancel", 3)).build());
        return builder.build();
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        final String action = intent == null ? "" : intent.getAction();
        if (action != null && action.startsWith("control-")) {
            if (running) {
                if (OwnerInstaller.busy(this)) return START_NOT_STICKY;
                importControl = action.substring(8);
                if ("cancel".equals(importControl)) { if (inputAccess != null) inputAccess.cancel(); if (worker != null) worker.cancel(); }
                try { ToolHostActivity.writeJson(new File(getFilesDir(), "owner-input/update-control.json"), new JSONObject().put("id", java.util.UUID.randomUUID().toString()).put("action", importControl)); }
                catch (Exception error) { ToolHostActivity.updateStatus(this, "ERROR", "Could not retain control: " + error.getMessage()); }
            } else stopSelf(startId);
            return START_NOT_STICKY;
        }
        if (running) return START_NOT_STICKY;
        pending = false;
        if (!("release-check".equals(action) || "install-prepare".equals(action) || "release-build".equals(action) || "import".equals(action) || "install".equals(action) || "release-rollback".equals(action) || "profile-recover".equals(action) || "install-verify".equals(action))) {
            stopSelf(startId); return START_NOT_STICKY;
        }
        if ((OwnerInstaller.busy(this) && !"install-verify".equals(action)) || (OwnerAlphaInstall.pending(this) && !"profile-recover".equals(action) && !"install-verify".equals(action))) { stopSelf(startId); return START_NOT_STICKY; }
        // Clear a previous generation before exposing an active job; fresh pause/cancel must not be lost.
        File staleControl = new File(getFilesDir(), "owner-input/update-control.json");
        if (staleControl.exists() && !staleControl.delete()) {
            ToolHostActivity.updateStatus(this, "ERROR", "Could not clear previous control"); stopSelf(startId); return START_NOT_STICKY;
        }
        // This foreground service is started only by an explicit visible UI action. Never auto-install after boot.
        running = true; destroyed = false; importControl = "continue";
        getSharedPreferences(PREFERENCES, 0).edit().putString("action", action).putBoolean("interrupted", true).commit();
        startForeground(NOTIFICATION, notification());
        wakeLock = ((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, getPackageName() + ":owner-build");
        wakeLock.acquire(); handler.post(refresh);
        thread = new Thread(new Runnable() { public void run() {
            try {
                if ("import".equals(action) || "release-build".equals(action) || "release-rollback".equals(action)) requireBatteryAdmission();
                if ("import".equals(action)) importFiles();
                else if ("install-verify".equals(action)) OwnerInstaller.finishVerification(OwnerBuildService.this);
                else if ("profile-recover".equals(action)) OwnerInstaller.recoverProfiles(OwnerBuildService.this);
                else if ("install".equals(action)) {
                    ToolHostActivity.installPrepared(OwnerBuildService.this);
                    awaitInstallation();
                }
                else {
                    worker = new ToolHostActivity.Worker(getApplicationContext()); worker.executeUpdate(action);
                    File status = new File(getFilesDir(), "owner-input/update-state.json");
                    if (("release-build".equals(action) || "release-rollback".equals(action)) && !destroyed && !"cancel".equals(importControl) && status.isFile()
                        && "READY".equals(ToolHostActivity.readJson(status).optString("state"))) {
                        if (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls()) {
                            ToolHostActivity.installPrepared(OwnerBuildService.this);
                            awaitInstallation();
                        } else ToolHostActivity.updateStatus(OwnerBuildService.this, "READY", "Reconstruction verified. Tap Install to allow installation in Android, then tap Install again to continue.");
                    }
                }
            } catch (Exception error) {
                if ("import".equals(action)) {
                    try { ToolHostActivity.writeJson(new File(getFilesDir(), "owner-input/import-state.json"), new JSONObject().put("state", (error instanceof InterruptedIOException || destroyed || "cancel".equals(importControl)) ? "CANCELLED" : "ERROR").put("message", error.getMessage())); }
                    catch (Exception ignored) { }
                } else ToolHostActivity.updateStatus(OwnerBuildService.this, "ERROR", error.getMessage());
            } finally {
                getSharedPreferences(PREFERENCES, 0).edit().putBoolean("interrupted", destroyed).commit();
                handler.post(new Runnable() { public void run() { finishService(); } });
            }
        } }, "owner-phone-installer"); thread.start();
        return START_NOT_STICKY;
    }
    private void awaitInstallation() throws Exception {
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        while (!destroyed && OwnerInstaller.busy(this)) {
            String phase = OwnerInstaller.state(this);
            if ("VERIFYING_PROFILE".equals(phase) || "RECOVERING_PROFILE".equals(phase)) {
                if (wakeLock != null && !wakeLock.isHeld()) wakeLock.acquire();
                try { OwnerInstaller.finishVerification(this); }
                finally { if (wakeLock != null && wakeLock.isHeld()) wakeLock.release(); }
            } else Thread.sleep(500);
        }
    }
    private void requireBatteryAdmission() throws Exception {
        Intent battery = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (battery == null) throw new IOException("Battery state unavailable; cannot admit a build safely");
        int temperature = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1);
        int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1), scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        int status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
        if (temperature < 0 || level < 0 || scale <= 0 || status < 0) throw new IOException("Battery telemetry unavailable");
        double percent = 100.0 * level / scale;
        // Existing phone runner caller-admission policy; no limits are relaxed here.
        if (temperature > 350 || percent > 85 || (status == BatteryManager.BATTERY_STATUS_CHARGING && percent >= 80))
            throw new IOException("Battery admission refused: cool to ≤ 35 C, level ≤ 85%, and unplug when charging at ≥ 80%");
    }
    private void importFiles() throws Exception {
        final long started = SystemClock.elapsedRealtime();
        inputAccess = new OwnerInputSource.Access();
        OwnerInputSource.run(this, new OwnerInputImport.Observer() {
            public void checkpoint() throws Exception {
                while ("pause".equals(importControl) && !destroyed) {
                    File state = new File(getFilesDir(), "owner-input/import-state.json");
                    JSONObject current = state.isFile() ? ToolHostActivity.readJson(state) : new JSONObject();
                    if (!"PAUSED".equals(current.optString("state"))) ToolHostActivity.writeJson(state, current.put("state", "PAUSED").put("message", "Import paused. Verified files are retained."));
                    Thread.sleep(250);
                }
                if (destroyed || "cancel".equals(importControl)) throw new InterruptedIOException("Import cancelled. Verified files retained; resume when ready.");
            }
            public void progress(String path, long complete, long total) throws Exception {
                long now = SystemClock.elapsedRealtime();
                if (now - lastImportProgress < 250 && complete != total) return;
                lastImportProgress = now;
                boolean validating = path.startsWith("Checking version:");
                JSONObject progress = new JSONObject().put("state", validating ? "VALIDATING" : "IMPORTING")
                    .put("message", validating ? path : "Importing " + path).put("elapsed_seconds", (now - started) / 1000);
                // Identification reports a phase, not copied bytes (tree counts are files).
                if (!validating && total > 0) progress.put("completed", complete).put("total", total);
                ToolHostActivity.writeJson(new File(getFilesDir(), "owner-input/import-state.json"), progress);
            }
        }, inputAccess);
    }
    private void finishService() {
        running = false; pending = false;
        handler.removeCallbacks(refresh);
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        stopForeground(true); stopSelf();
    }
    @Override public void onDestroy() {
        destroyed = true; handler.removeCallbacks(refresh);
        if (inputAccess != null) inputAccess.cancel();
        if (worker != null) worker.cancel();
        if (thread != null && thread.isAlive()) thread.interrupt();
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        super.onDestroy();
    }
}
