package dev.ror2lab.phonebuildhostfixture;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.system.Os;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.json.*;

public final class ToolHostActivity extends Activity {
    private final OwnerUpdateState model = new OwnerUpdateState();
    private final android.os.Handler handler = new android.os.Handler(android.os.Looper.getMainLooper());
    private TextView statusView;
    private Button checkButton, rollbackButton, recoveryButton, prepareButton, treeButton, zipButton, importButton, buildButton, installButton, pauseButton, resumeButton, cancelButton, retryButton;
    private static final int PICK_TREE = 120, PICK_ZIP = 121;
    private String flowDetail = "";
    private final Runnable refresh = new Runnable() { public void run() { refreshStatus(); handler.postDelayed(this, 500); } };
    private final android.content.SharedPreferences.OnSharedPreferenceChangeListener installObserver =
        new android.content.SharedPreferences.OnSharedPreferenceChangeListener() {
            public void onSharedPreferenceChanged(android.content.SharedPreferences preferences, String key) {
                handler.post(new Runnable() { public void run() { refreshStatus(); } });
            }
        };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); layout.setPadding(24, 24, 24, 24);
        scroll.addView(layout);
        statusView = new TextView(this); layout.addView(statusView);
        checkButton = button(layout, "Check for updates", new Runnable() { public void run() { startUpdate("release-check"); } });
        rollbackButton = button(layout, "Rebuild and install previous release (same key)", new Runnable() { public void run() { startUpdate("release-rollback"); } });
        recoveryButton = button(layout, "Recover and verify retained profile/settings", new Runnable() { public void run() { OwnerBuildService.launch(ToolHostActivity.this, "profile-recover"); } });
        prepareButton = button(layout, "Prepare signed installation plan", new Runnable() { public void run() { startUpdate("install-prepare"); } });
        treeButton = button(layout, "Choose game folder", new Runnable() { public void run() { pickSource(true); } });
        zipButton = button(layout, "Choose game ZIP", new Runnable() { public void run() { pickSource(false); } });
        importButton = button(layout, "Import / resume game files", new Runnable() { public void run() { startImport(); } });
        buildButton = button(layout, "Reconstruct and install verified game", new Runnable() { public void run() { startUpdate("release-build"); } });
        pauseButton = button(layout, "Pause", new Runnable() { public void run() { control("pause"); } });
        resumeButton = button(layout, "Resume", new Runnable() { public void run() { resume(false); } });
        cancelButton = button(layout, "Cancel (keep verified checkpoints)", new Runnable() { public void run() { control("cancel"); } });
        retryButton = button(layout, "Retry first failing stage", new Runnable() { public void run() { resume(true); } });
        installButton = button(layout, "Install verified owner build", new Runnable() { public void run() { installReady(); } });
        setContentView(scroll);
        if (android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 122);
        // Opening the installer is observational: never launch the old fixture or an install implicitly.
        refreshStatus();
    }
    private Button button(LinearLayout layout, String label, final Runnable action) {
        Button result = new Button(this); result.setText(label); layout.addView(result);
        result.setOnClickListener(new android.view.View.OnClickListener() { public void onClick(android.view.View ignored) { action.run(); } });
        return result;
    }
    private void pickSource(boolean tree) {
        if (OwnerBuildService.isRunning() || OwnerInstaller.busy(this)) return;
        Intent pick = new Intent(tree ? Intent.ACTION_OPEN_DOCUMENT_TREE : Intent.ACTION_OPEN_DOCUMENT);
        pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        if (!tree) { pick.setType("application/zip"); pick.addCategory(Intent.CATEGORY_OPENABLE); pick.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/zip", "application/x-zip-compressed", "application/octet-stream"}); }
        try { startActivityForResult(pick, tree ? PICK_TREE : PICK_ZIP); }
        catch (RuntimeException error) { updateStatus(this, "ERROR", "File picker unavailable: " + error.getMessage()); }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if ((request != PICK_TREE && request != PICK_ZIP) || result != RESULT_OK || data == null || data.getData() == null) return;
        if (OwnerBuildService.isRunning() || OwnerInstaller.busy(this)) return;
        try {
            Uri uri = data.getData();
            if (!"content".equals(uri.getScheme())) throw new IOException("Storage Access Framework content required");
            getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            android.content.SharedPreferences preferences = getSharedPreferences(OwnerBuildService.PREFERENCES, 0);
            String previous = preferences.getString("source_uri", "");
            if (!preferences.edit().putString("source_uri", uri.toString()).putString("source_kind", request == PICK_TREE ? "tree" : "zip").commit())
                throw new IOException("Could not retain selected source");
            if (!previous.isEmpty() && !previous.equals(uri.toString())) {
                try { getContentResolver().releasePersistableUriPermission(Uri.parse(previous), Intent.FLAG_GRANT_READ_URI_PERMISSION); } catch (SecurityException ignored) { }
            }
            updateStatus(this, "INPUT_REQUIRED", "Source selected. Import verifies paths, sizes and hashes; originals stay untouched.");
        } catch (Exception error) { updateStatus(this, "ERROR", "Could not retain source access: " + error.getMessage()); }
        refreshStatus();
    }
    private void startImport() {
        if (OwnerBuildService.isRunning() || OwnerInstaller.busy(this)) return;
        try {
            if (!new File(getFilesDir(), "owner-input/install-inputs.json").isFile()) throw new IOException("Prepare a signed installation plan first");
            writeJson(new File(getFilesDir(), "owner-input/import-state.json"), new JSONObject().put("state", "IMPORTING").put("message", "Checking required inputs and private free space…"));
            OwnerBuildService.launch(this, "import");
        } catch (Exception error) { updateStatus(this, "ERROR", error.getMessage()); }
        refreshStatus();
    }
    private void control(String action) {
        try { if (OwnerBuildService.isRunning()) OwnerBuildService.control(this, action); }
        catch (Exception error) { updateStatus(this, "ERROR", error.getMessage()); }
    }
    private void resume(boolean retry) {
        if (OwnerBuildService.isRunning()) { control(retry ? "retry" : "resume"); return; }
        if (OwnerInstaller.busy(this)) return;
        if (retry && "ERROR".equals(OwnerInstaller.state(this))) {
            String previousBuild = getSharedPreferences(OwnerBuildService.PREFERENCES, 0).getString("last_build_action", "release-build");
            startUpdate(previousBuild); return;
        }
        String previous = OwnerBuildService.action(this);
        if ("import".equals(previous)) startImport();
        else if ("release-build".equals(previous) || "release-rollback".equals(previous)) startUpdate(previous);
        else if ("install-prepare".equals(previous) || "release-check".equals(previous)) startUpdate(previous);
        // Installation always requires the separate explicit Install button, including after reboot.
    }
    @Override public void onResume() {
        super.onResume();
        getSharedPreferences(OwnerInstaller.STATUS, 0).registerOnSharedPreferenceChangeListener(installObserver);
        handler.removeCallbacks(refresh); handler.post(refresh);
    }
    @Override public void onPause() {
        handler.removeCallbacks(refresh);
        getSharedPreferences(OwnerInstaller.STATUS, 0).unregisterOnSharedPreferenceChangeListener(installObserver);
        super.onPause();
    }
    static JSONObject readJson(File file) throws Exception {
        if (file.length() > 4 * 1024 * 1024) throw new IOException("Private status is too large");
        try (InputStream input = new FileInputStream(file)) { return readJson(input); }
    }
    static JSONObject readJson(InputStream input) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(); byte[] buffer = new byte[8192]; int count;
        while ((count = input.read(buffer)) != -1) {
            if (bytes.size() + count > 4 * 1024 * 1024) throw new IOException("Private metadata is too large");
            bytes.write(buffer, 0, count);
        }
        return new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8));
    }
    static synchronized void writeJson(File file, JSONObject value) throws Exception {
        File parent = file.getParentFile(); if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("Private owner directory unavailable");
        File staged = new File(parent, file.getName() + ".writing");
        try (FileOutputStream output = new FileOutputStream(staged)) { output.write(value.toString().getBytes(StandardCharsets.UTF_8)); output.getFD().sync(); }
        if (!staged.renameTo(file)) throw new IOException("Could not publish private status");
    }
    static void updateStatus(Context app, String phase, String message) {
        try { File file = new File(app.getFilesDir(), "owner-input/update-state.json"); JSONObject value = file.isFile() ? readJson(file) : new JSONObject(); writeJson(file, value.put("state", phase).put("message", message)); }
        catch (Exception ignored) { /* Worker report retains the underlying failure if storage is unavailable. */ }
    }
    private static JSONObject installedRequest(Context app, String action) throws Exception {
        if (new File(app.getFilesDir(), "owner-input/debug-release-source.json").exists() && !debuggable(app))
            throw new IOException("Test release source and publisher key are forbidden in release builds");
        JSONObject trust;
        try (InputStream input = app.getAssets().open("release-trust.json")) { trust = readJson(input); }
        String packageName = trust.getString("application_id");
        if (!OwnerAlphaInstall.PACKAGE.equals(packageName)) throw new IOException("Final owner flow requires dev.ror2lab.alpha");
        long installed = 0, published = 0;
        try {
            android.content.pm.PackageInfo actual = app.getPackageManager().getPackageInfo(packageName, android.content.pm.PackageManager.GET_SIGNATURES);
            installed = OwnerInstaller.version(actual);
            JSONObject owned = OwnerAlphaInstall.owned(app, actual, false);
            published = owned.getJSONObject("release").getLong("version_code");
        } catch (android.content.pm.PackageManager.NameNotFoundException absent) { /* first install */ }
        android.content.pm.PackageInfo installer = app.getPackageManager().getPackageInfo(app.getPackageName(), android.content.pm.PackageManager.GET_SIGNATURES);
        return new JSONObject().put("action", action).put("application_id", packageName)
            .put("installed_version", installed).put("installed_release_version", published)
            .put("installer_version", OwnerInstaller.version(installer))
            .put("installer_package", app.getPackageName()).put("installer_signer_sha256", OwnerInstaller.signer(installer));
    }

    private void startUpdate(final String action) {
        final Context app = getApplicationContext();
        if (OwnerBuildService.isRunning() || OwnerInstaller.busy(app) || OwnerAlphaInstall.pending(app)) return;
        try {
            OwnerInstaller.clearTerminalStatus(app);
            if ("release-build".equals(action) || "release-rollback".equals(action))
                if (!getSharedPreferences(OwnerBuildService.PREFERENCES, 0).edit().putString("last_build_action", action).commit()) throw new IOException("Could not retain explicit build action");
            writeJson(new File(getFilesDir(), "owner-input/update-request.json"), installedRequest(app, action));
            updateStatus(app, "release-check".equals(action) ? "CHECKING" : "BUILDING", "install-prepare".equals(action) ? "Verifying the signed installation plan…" : "Starting local release work…");
            OwnerBuildService.launch(app, action);
        } catch (Exception error) { updateStatus(app, "ERROR", error.getMessage()); }
        refreshStatus();
    }
    private void installReady() {
        if (OwnerBuildService.isRunning() || OwnerInstaller.busy(this)) return;
        try {
            if (!model.canInstall() && !"ERROR".equals(OwnerInstaller.state(this))) throw new IOException("Reconstruct and verify the release first");
            if (android.os.Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
                startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()))); return;
            }
            OwnerBuildService.launch(this, "install");
        } catch (Exception error) { updateStatus(this, "ERROR", error.getMessage()); }
        refreshStatus();
    }
    static void installPrepared(Context app) throws Exception {
        JSONObject ready = readJson(new File(app.getFilesDir(), "owner-input/owner-apk-ready.json"));
        JSONObject request = installedRequest(app, "release-build");
        if (!ready.getString("application_id").equals(request.getString("application_id"))) throw new IOException("Ready package differs from trusted release configuration");
        File apk = new File(ready.getString("apk")).getCanonicalFile();
        if (!apk.getPath().startsWith(app.getFilesDir().getCanonicalPath() + "/") || !apk.isFile()) throw new IOException("Private owner APK required");
        OwnerInstaller.install(app, apk, ready.getString("sha256"), ready.getString("application_id"), ready.getLong("version_code"));
    }
    static void reconcileBuildStop(Context app, String phase, String message) {
        try {
            File file = new File(app.getFilesDir(), "owner-input/install-checkpoint.json");
            if (!file.isFile()) { updateStatus(app, phase, message); return; }
            JSONObject checkpoint = readJson(file);
            JSONObject existingFailure = checkpoint.optJSONObject("first_failure");
            String current = checkpoint.optString("current_stage", "admission");
            if (current.isEmpty() || current.equals("null")) current = "admission";
            String status = "CANCELLED".equals(phase) ? "cancelled" : "failed";
            checkpoint.put("status", status).put("updated_at", System.currentTimeMillis() / 1000.0);
            if (existingFailure == null && !"CANCELLED".equals(phase)) checkpoint.put("first_failure", new JSONObject().put("stage", current).put("reason", message));
            JSONArray stages = checkpoint.getJSONArray("stages");
            for (int i = 0; i < stages.length(); i++) {
                JSONObject stage = stages.getJSONObject(i);
                if (current.equals(stage.optString("id")) && !"complete".equals(stage.optString("status"))) stage.put("status", "CANCELLED".equals(phase) ? "interrupted" : "failed");
            }
            writeJson(file, checkpoint);
            File update = new File(app.getFilesDir(), "owner-input/update-state.json");
            JSONObject progress = update.isFile() ? readJson(update) : new JSONObject();
            writeJson(update, progress.put("pipeline", checkpoint).put("state", phase).put("message", existingFailure == null ? message : existingFailure.optString("reason", message)));
        } catch (Exception ignored) { updateStatus(app, phase, message); }
    }
    static void updateInstallCheckpoint(Context app, String state, String message) {
        try {
            File file = new File(app.getFilesDir(), "owner-input/install-checkpoint.json");
            if (!file.isFile() || "IDLE".equals(state)) return;
            JSONObject checkpoint = readJson(file);
            String phase = "INSTALLED".equals(state) ? "complete" : ("ERROR".equals(state) || "RECOVERY_REQUIRED".equals(state)) ? "failed" : "AWAITING_CONFIRMATION".equals(state) ? "awaiting_consent" : "running";
            checkpoint.put("status", phase).put("current_stage", "install").put("updated_at", System.currentTimeMillis() / 1000.0);
            checkpoint.put("first_failure", ("ERROR".equals(state) || "RECOVERY_REQUIRED".equals(state)) ? new JSONObject().put("stage", "install").put("reason", message) : JSONObject.NULL);
            JSONArray stages = checkpoint.getJSONArray("stages");
            for (int i = 0; i < stages.length(); i++) {
                JSONObject stage = stages.getJSONObject(i);
                if ("install".equals(stage.getString("id"))) stage.put("status", phase).put("completed", "INSTALLED".equals(state) ? 1 : 0).put("total", 1);
            }
            writeJson(file, checkpoint);
            File update = new File(app.getFilesDir(), "owner-input/update-state.json");
            JSONObject progress = update.isFile() ? readJson(update) : new JSONObject();
            writeJson(update, progress.put("pipeline", checkpoint).put("state", state).put("message", message));
        } catch (Exception ignored) { /* PackageInstaller's durable identity/status remains authoritative. */ }
    }
    private void refreshStatus() {
        if (statusView == null) return;
        try {
            File progress = new File(getFilesDir(), "owner-input/update-state.json");
            if (progress.isFile()) {
                JSONObject value = readJson(progress); String detail = value.optString("message");
                if (value.has("release")) {
                    JSONObject release = value.getJSONObject("release");
                    detail += "\nRelease " + release.optString("version") + " (" + release.optLong("version_code") + ")";
                }
                if (value.has("changed_entries")) detail += "\nChanged outputs: " + value.getJSONArray("changed_entries").length();
                if (value.has("rebuilt")) detail += "\nRebuilt: " + value.getJSONArray("rebuilt").length() + "; reused: " + value.getJSONArray("reused").length();
                model.observe(value.getString("state"), detail);
                if ("import".equals(OwnerBuildService.action(this))) {
                    File imported = new File(getFilesDir(), "owner-input/import-state.json");
                    if (imported.isFile()) { JSONObject inputState = readJson(imported); model.observe(inputState.optString("state", "INPUT_REQUIRED"), inputState.optString("message")); }
                }
            }
            String installation = OwnerInstaller.state(this);
            if (!OwnerBuildService.isRunning() && OwnerInstaller.busy(this)) { OwnerInstaller.reconcile(this); installation = OwnerInstaller.state(this); }
            if (OwnerInstaller.busy(this)) model.observe(installation, OwnerInstaller.status(this));
            else if (!OwnerBuildService.isRunning() && (model.phase() == OwnerUpdateState.Phase.READY || model.phase() == OwnerUpdateState.Phase.INSTALLING || model.phase() == OwnerUpdateState.Phase.AWAITING_CONFIRMATION || model.phase() == OwnerUpdateState.Phase.VERIFYING_PROFILE || model.phase() == OwnerUpdateState.Phase.RECOVERING_PROFILE)) {
                if ("INSTALLED".equals(installation)) { model.observe(installation, OwnerInstaller.status(this)); }
                else if ("ERROR".equals(installation) || "RECOVERY_REQUIRED".equals(installation)) model.observe(installation, OwnerInstaller.status(this));
            }
            if (OwnerAlphaInstall.pending(this) && !OwnerInstaller.busy(this) && !OwnerBuildService.isRunning()) model.observe("RECOVERY_REQUIRED", OwnerInstaller.status(this));
            // A killed worker is not still running. Rechecking safely rediscovers the release/cache.
            if (!OwnerBuildService.isRunning() && model.busy() && !OwnerInstaller.busy(this)) model.observe("ERROR", "Work is not running. Tap Resume to revalidate retained checkpoints.");
        } catch (Exception error) { model.observe("ERROR", error.getMessage()); }
        render();
    }
    private String phoneProgress() throws Exception {
        StringBuilder detail = new StringBuilder();
        File debugSource = new File(getFilesDir(), "owner-input/debug-release-source.json");
        if (debugSource.exists()) {
            if (!debuggable(this)) detail.append("\n\nTEST RELEASE OVERRIDE REJECTED — installer is not debuggable.");
            else {
                JSONObject override = readJson(debugSource);
                detail.append("\n\nTEST RELEASE SOURCE — additional test publisher trust requested. NOT A PRODUCTION RELEASE.\n")
                    .append(override.optString("base_url", "Invalid override; release work will refuse."));
            }
        }
        detail.append("\n\n").append(OwnerAlphaInstall.rollbackStatus(this));
        detail.append("\nInstaller-private filesystem free: ").append(getFilesDir().getUsableSpace()).append(" bytes. Android chooses installation placement; no storage is reconfigured.");
        if (OwnerAlphaInstall.pending(this)) detail.append("\nProfile/settings snapshot transaction retained in game-private storage. Recovery is required before another operation if installation stops.");
        File imported = new File(getFilesDir(), "owner-input/import-state.json");
        if (imported.isFile()) {
            JSONObject state = readJson(imported);
            detail.append("\n\nGame import: ").append(state.optString("state")).append("\n").append(state.optString("message"));
            JSONArray extras = state.optJSONArray("extra");
            if (extras != null && extras.length() > 0) {
                detail.append("\nIgnored extra files:");
                for (int i = 0; i < Math.min(20, extras.length()); i++) detail.append("\n  ").append(extras.getString(i));
                if (extras.length() > 20) detail.append("\n  … and ").append(extras.length() - 20).append(" more");
            }
            if (state.optLong("total", 0) > 0) detail.append("\n").append(state.optLong("completed")).append(" / ").append(state.optLong("total")).append(" bytes");
            if (state.has("elapsed_seconds")) detail.append(" · ").append(state.optLong("elapsed_seconds")).append(" s");
        }
        File update = new File(getFilesDir(), "owner-input/update-state.json");
        JSONObject state = update.isFile() ? readJson(update) : new JSONObject();
        JSONObject pipeline = state.optJSONObject("pipeline");
        File durable = new File(getFilesDir(), "owner-input/install-checkpoint.json");
        if (durable.isFile()) pipeline = readJson(durable);
        if (pipeline == null) {
            File plan = new File(getFilesDir(), "owner-input/install-inputs.json");
            if (plan.isFile()) pipeline = readJson(plan);
        }
        if (pipeline != null) {
            detail.append("\n\nReconstruction stages");
            long liveSeconds = OwnerBuildService.isRunning() && "running".equals(pipeline.optString("status"))
                ? Math.max(0, System.currentTimeMillis() / 1000 - pipeline.optLong("updated_at")) : 0;
            File currentThermal = new File(getFilesDir(), "owner-input/thermal-state.json");
            if (currentThermal.isFile() && "paused".equals(readJson(currentThermal).optString("status"))) liveSeconds = 0;
            JSONArray stages = pipeline.optJSONArray("stages");
            if (stages != null) for (int i = 0; i < stages.length(); i++) {
                JSONObject stage = stages.getJSONObject(i);
                detail.append("\n").append(stage.optString("label", stage.optString("title", stage.optString("id"))))
                    .append(": ").append(stage.optString("status", "pending"));
                if (stage.has("total")) detail.append(" · ").append(stage.optLong("completed")).append('/').append(stage.optLong("total"));
                if (stage.has("elapsed_seconds")) detail.append(" · ").append(stage.optLong("elapsed_seconds") + ("running".equals(stage.optString("status")) ? liveSeconds : 0)).append(" s");
            }
            if (pipeline.has("elapsed_seconds")) detail.append("\nTotal elapsed: ").append(pipeline.optLong("elapsed_seconds") + liveSeconds).append(" s");
            JSONObject failure = pipeline.optJSONObject("first_failure");
            if (failure != null) detail.append("\nFirst failure: ").append(failure.optString("stage")).append(" — ").append(failure.optString("reason"));
        }
        File thermal = new File(getFilesDir(), "owner-input/thermal-state.json");
        if (thermal.isFile()) {
            JSONObject reading = readJson(thermal);
            detail.append("\n\nDuty runner: ").append(reading.optString("status", "unavailable"));
            if (!OwnerBuildService.isRunning() || System.currentTimeMillis() / 1000 - reading.optLong("updated_at") > 5) detail.append(" (last recorded reading; not live)");
            for (String zone : new String[]{"cpu", "gpu", "battery", "skin"})
                detail.append("\n").append(zone).append(": ").append(reading.has(zone + "_celsius") && !reading.isNull(zone + "_celsius") ? reading.optString(zone + "_celsius") + " °C" : "unavailable");
            if (reading.optBoolean("manual_paused")) detail.append("\nPaused by you; thermal monitoring remains active");
            if (reading.optBoolean("thermal_paused")) detail.append("\nCooling under the unchanged thermal policy");
            if (reading.has("error")) detail.append("\n").append(reading.optString("error"));
        }
        else detail.append("\n\nThermal / battery: awaiting existing duty runner telemetry");
        Intent battery = registerReceiver(null, new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (battery != null) {
            int level = battery.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1), scale = battery.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1);
            int charging = battery.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1), health = battery.getIntExtra(android.os.BatteryManager.EXTRA_HEALTH, -1);
            detail.append("\nBattery charge: ").append(level >= 0 && scale > 0 ? (100 * level / scale) + "%" : "unavailable")
                .append(charging == android.os.BatteryManager.BATTERY_STATUS_CHARGING ? " · charging" : " · not charging")
                .append(" · health ").append(health == android.os.BatteryManager.BATTERY_HEALTH_GOOD ? "good" : health == android.os.BatteryManager.BATTERY_HEALTH_OVERHEAT ? "overheat" : health == android.os.BatteryManager.BATTERY_HEALTH_UNKNOWN || health < 0 ? "unavailable" : "attention needed");
        }
        if (!OwnerBuildService.isRunning() && getSharedPreferences(OwnerBuildService.PREFERENCES, 0).getBoolean("interrupted", false))
            detail.append("\nWork was interrupted. Tap Resume to verify retained checkpoints; nothing runs or installs automatically.");
        return detail.toString();
    }
    private void render() {
        String phase = model.phase() == OwnerUpdateState.Phase.ERROR ? "FAILED" : model.phase().toString().replace('_', ' ');
        try { flowDetail = phoneProgress(); } catch (Exception error) { flowDetail = "\nPrivate progress unavailable: " + error.getMessage(); }
        statusView.setText(phase + "\n" + model.message() + flowDetail);
        boolean idle = !OwnerBuildService.isRunning() && !OwnerInstaller.busy(this) && !OwnerAlphaInstall.pending(this);
        rollbackButton.setEnabled(idle && OwnerAlphaInstall.canRollback(this));
        recoveryButton.setEnabled(!OwnerBuildService.isRunning() && !OwnerInstaller.busy(this) && OwnerAlphaInstall.pending(this));
        prepareButton.setEnabled(idle); treeButton.setEnabled(idle); zipButton.setEnabled(idle);
        importButton.setEnabled(idle && new File(getFilesDir(), "owner-input/install-inputs.json").isFile());
        pauseButton.setEnabled(OwnerBuildService.isRunning() && !OwnerInstaller.busy(this)); cancelButton.setEnabled(OwnerBuildService.isRunning() && !OwnerInstaller.busy(this));
        resumeButton.setEnabled(!OwnerInstaller.busy(this)); retryButton.setEnabled(idle && model.phase() == OwnerUpdateState.Phase.ERROR);
        checkButton.setEnabled(idle && model.canCheck());
        buildButton.setEnabled(idle && (model.canBuild() || new File(getFilesDir(), "owner-input/import-state.json").isFile()));
        installButton.setEnabled(idle && model.canInstall());
    }
    private static File readyApk(Context app) throws Exception {
        File report=new File(app.getFilesDir(),"tool-host-report.json");
        byte[] bytes=new byte[(int)report.length()];
        try(DataInputStream in=new DataInputStream(new FileInputStream(report))){in.readFully(bytes);}
        JSONObject value=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        if(!value.getBoolean("success"))throw new IOException("successful owner build required");
        File apk=new File(value.getJSONObject("ownerApk").getString("apk")).getCanonicalFile();
        if(!apk.getPath().startsWith(app.getFilesDir().getCanonicalPath()+"/")||!apk.isFile())throw new IOException("private owner APK required");
        return apk;
    }
    public static final class ApkProvider extends ContentProvider {
        public boolean onCreate(){return true;}
        private File selected(Uri uri) throws FileNotFoundException {
            if(!"/owner.apk".equals(uri.getPath()))throw new FileNotFoundException("unknown owner APK");
            try{return readyApk(getContext());}catch(Exception error){throw new FileNotFoundException(error.toString());}
        }
        public String getType(Uri uri){return "application/vnd.android.package-archive";}
        public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
            if(!"r".equals(mode))throw new FileNotFoundException("read-only owner APK");
            return ParcelFileDescriptor.open(selected(uri),ParcelFileDescriptor.MODE_READ_ONLY);
        }
        public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort) {
            try { File apk=selected(uri);MatrixCursor cursor=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});cursor.addRow(new Object[]{"owner-built.apk",apk.length()});return cursor; }
            catch(FileNotFoundException error){return null;}
        }
        public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
        public int update(Uri uri,ContentValues values,String where,String[] args){throw new UnsupportedOperationException();}
        public int delete(Uri uri,String where,String[] args){throw new UnsupportedOperationException();}
    }
    private static boolean debuggable(Context app) {
        return (app.getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0;
    }
    public static class Runner extends Instrumentation {
        public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
        public void onStart() {
            new Worker(getTargetContext()).executeFixture();
            finish(Activity.RESULT_OK, new Bundle());
        }
    }
    static class Worker {
    private volatile java.lang.Process activeChild;
    private volatile boolean cancelled;
    void cancel() { cancelled = true; java.lang.Process child = activeChild; if (child != null) child.destroy(); }
    private final Context app;
    private File hostfxr;
    Worker(Context app) { this.app=app; }
    private android.content.res.AssetManager getAssets() { return app.getAssets(); }
    private File getFilesDir() { return app.getFilesDir(); }
    private File getCacheDir() { return app.getCacheDir(); }
    private android.content.pm.ApplicationInfo getApplicationInfo() { return app.getApplicationInfo(); }
    private void copyAssets(String name, File destination) throws Exception {
        if (cancelled) throw new InterruptedIOException("Worker cancelled");
        String[] children = getAssets().list(name);
        if (children.length > 0) {
            if (!destination.mkdirs() && !destination.isDirectory()) throw new IOException("asset directory");
            for (String child : children) copyAssets(name.isEmpty() ? child : name + "/" + child, new File(destination, child));
        } else {
            try (InputStream source=getAssets().open(name); OutputStream output=new FileOutputStream(destination)) {
                byte[] bytes=new byte[65536]; int n; while ((n=source.read(bytes))!=-1) { if (cancelled) throw new InterruptedIOException("Worker cancelled"); output.write(bytes,0,n); }
            }
        }
    }
    private String text(File file) throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try (InputStream source=new FileInputStream(file)) { byte[] b=new byte[65536]; int n; while ((n=source.read(b))!=-1) bytes.write(b,0,n); }
        return new String(bytes.toByteArray(),StandardCharsets.UTF_8);
    }
    private String hash(File file) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try (InputStream source=new FileInputStream(file)) {byte[] b=new byte[65536]; int n; while((n=source.read(b))!=-1) { if (cancelled) throw new InterruptedIOException("Worker cancelled"); digest.update(b,0,n); }}
        StringBuilder s=new StringBuilder(); for(byte b:digest.digest()) s.append(String.format(Locale.ROOT,"%02x",b&255)); return s.toString();
    }
    private void systemTrust(File directory) throws Exception {
        // Use this Android app's default TLS trust, not the embedded OpenSSL
        // build's host-specific CA path. Publisher signature trust is separate.
        javax.net.ssl.TrustManagerFactory factory = javax.net.ssl.TrustManagerFactory.getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());
        factory.init((java.security.KeyStore) null);
        File bundle = new File(directory, "system-ca.pem"); int count = 0;
        try (FileOutputStream output = new FileOutputStream(bundle)) {
            for (javax.net.ssl.TrustManager manager : factory.getTrustManagers()) {
                if (!(manager instanceof javax.net.ssl.X509TrustManager)) continue;
                for (java.security.cert.X509Certificate certificate : ((javax.net.ssl.X509TrustManager) manager).getAcceptedIssuers()) {
                    String encoded = android.util.Base64.encodeToString(certificate.getEncoded(), android.util.Base64.NO_WRAP);
                    output.write(("-----BEGIN CERTIFICATE-----\n" + encoded + "\n-----END CERTIFICATE-----\n").getBytes(StandardCharsets.US_ASCII));
                    count++;
                }
            }
            output.getFD().sync();
        }
        if (count == 0 || !bundle.setReadOnly()) throw new IOException("Android system TLS trust unavailable");
        File empty = new File(directory, "empty-ca-directory");
        if (!empty.mkdir() || !empty.setReadOnly()) throw new IOException("Private TLS CA directory unavailable");
    }
    private JSONObject child(String label, List<String> arguments, File directory, File nativeDir, File links) throws Exception {
        File output=new File(directory,label+".log");
        // Pin before interpreter/JVM startup; a periodic watcher can miss its short heat spike.
        List<String> command=new ArrayList<>(Arrays.asList("/system/bin/taskset","1"));
        File thermalReceipt=new File(directory,label+"-thermal.json");
        if(label.equals("owner-backend") || label.equals("public-profile")) {
            command.addAll(Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),
                new File(nativeDir,"libpython3.14.so").getPath(),new File(directory,"python").getPath(),
                new File(directory,"repo/tools/phone-build/accepted-output/phone_runner.py").getPath(),
                "--receipt",thermalReceipt.getPath(),"--timeout","86400"));
            if (label.equals("owner-backend") && new File(getFilesDir(), "owner-input/update-request.json").isFile())
                command.addAll(Arrays.asList("--control", new File(getFilesDir(), "owner-input/update-control.json").getPath(), "--status", new File(getFilesDir(), "owner-input/thermal-state.json").getPath()));
            command.add("--");
        }
        command.addAll(arguments);
        ProcessBuilder builder=new ProcessBuilder(command).directory(directory).redirectErrorStream(true).redirectOutput(output);
        Map<String,String> env=builder.environment();
        // Always overwrite inherited values; private request/override JSON cannot enable this.
        env.put("ROR2_INSTALLER_DEBUGGABLE", debuggable(app) ? "1" : "0");
        File systemCa = new File(directory, "system-ca.pem");
        if (systemCa.isFile()) {
            env.put("SSL_CERT_FILE", systemCa.getCanonicalPath());
            env.put("SSL_CERT_DIR", new File(directory, "empty-ca-directory").getCanonicalPath());
        }
        for(String key:new ArrayList<>(env.keySet())) if(key.startsWith("DOTNET_") || key.startsWith("MONO_") || key.startsWith("CORECLR_") || key.startsWith("COMPlus_")) env.remove(key);
        env.put("LD_LIBRARY_PATH",nativeDir.getCanonicalPath()+":"+links.getCanonicalPath());
        env.put("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT","1"); env.put("DOTNET_MULTILEVEL_LOOKUP","0");
        env.put("DOTNET_CLI_TELEMETRY_OPTOUT","1"); env.put("DOTNET_CLI_HOME",new File(directory,"home").getPath());
        env.put("TMPDIR",getCacheDir().getPath());
        env.put("ROR2LAB_BUILD_DOTNET_ROOT",new File(directory,"dotnet").getPath());
        env.put("ROR2LAB_BUILD_HOSTFXR",hostfxr.getPath());
        env.put("ROR2LAB_BUILD_DOTNET_LAUNCHER",new File(nativeDir,"libdotnetmuxer.so").getPath());
        for(String key:new String[]{"JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","_JAVA_OPTIONS","JAVA_HOME","CLASSPATH"})env.remove(key);
        if(new File(nativeDir,"libjvm.so").isFile()) {
            env.put("ROR2LAB_BUILD_JVM",new File(nativeDir,"libjvm.so").getPath());
            env.put("ROR2LAB_BUILD_JAVA_HOME",new File(directory,"java").getPath());
        }
        if (cancelled) throw new InterruptedIOException("Worker stopped");
        java.lang.Process process=builder.start(); activeChild = process;
        try {
        if(!process.waitFor((label.equals("owner-backend") || label.equals("public-profile"))?86400:90,TimeUnit.SECONDS)){
            process.destroy();
            if(!process.waitFor(15,TimeUnit.SECONDS)) process.destroyForcibly();
            throw new IOException(label+" timeout");
        }
        JSONObject result=new JSONObject(); result.put("exit",process.exitValue());result.put("log",output.getName());result.put("sha256",hash(output));
        if(thermalReceipt.isFile()) result.put("thermal",new JSONObject(text(thermalReceipt)));
        if(process.exitValue()!=0) throw new IOException(label+" exit "+process.exitValue()+" "+text(output).substring(0,Math.min(2000,text(output).length())));
        return result;
        } finally {
            if (process.isAlive()) { process.destroy(); try { if (!process.waitFor(15, TimeUnit.SECONDS)) process.destroyForcibly(); } catch (InterruptedException interrupted) { process.destroyForcibly(); Thread.currentThread().interrupt(); } }
            activeChild = null;
        }
    }
    private void executeFixture() { execute(null); }
    void executeUpdate(String action) { execute(action); }
    private void execute(String updateAction) {
        JSONObject report=new JSONObject();
        try {
            report.put("schema",1);report.put("success",false);report.put("securityQualified",false);report.put("gameRuntimeChanged",false);
            report.put("selfContext",text(new File("/proc/self/attr/current")).trim());report.put("deviceApi",android.os.Build.VERSION.SDK_INT);report.put("targetSdk",getApplicationInfo().targetSdkVersion);
            File root=new File(getFilesDir(),"fixture-"+System.nanoTime()); if(root.exists())throw new IOException("fresh data directory required");
            copyAssets("",root);
            report.put("dataDirectory",root.getPath());
            JSONObject dataHashes=new JSONObject(text(new File(root,"data-hashes.json")));
            Iterator<String> dataNames=dataHashes.keys();int dataCount=0;
            while(dataNames.hasNext()) {String name=dataNames.next();File file=new File(root,name).getCanonicalFile();if(!file.getPath().startsWith(root.getCanonicalPath()+"/")||!file.isFile()||!hash(file).equals(dataHashes.getString(name)))throw new IOException("asset data drift "+name);dataCount++;}
            report.put("dataFilesVerified",dataCount);
            File nativeDir=new File(getApplicationInfo().nativeLibraryDir).getCanonicalFile();
            File runtime=new File(root,"dotnet");File framework=new File(runtime,"shared/Microsoft.NETCore.App/8.0.32");File links=new File(root,"native-links");links.mkdir();
            JSONObject hashes=new JSONObject(text(new File(root,"native-hashes.json")));
            JSONArray verified=new JSONArray();Iterator<String> names=hashes.keys();
            while(names.hasNext()){
                String name=names.next();File file=new File(nativeDir,name).getCanonicalFile();
                if(!file.getParentFile().equals(nativeDir)||!file.isFile()||file.canWrite()||!hash(file).equals(hashes.getString(name)))throw new IOException("native identity/read-only failure "+name);
                verified.put(name);
            }
            report.put("nativeVerified",verified);report.put("nativeDirectory",nativeDir.getPath());report.put("appUid",android.os.Process.myUid());
            hostfxr=new File(nativeDir,hashes.has("libhostfxr10.so")?"libhostfxr10.so":"libhostfxr.so");
            for(String name:new String[]{"libcoreclr.so","libhostpolicy.so","libSystem.Native.so","libSystem.Globalization.Native.so","libSystem.IO.Compression.Native.so","libSystem.Net.Security.Native.so","libSystem.Security.Cryptography.Native.Android.so","libSystem.Security.Cryptography.Native.OpenSsl.so"}) Os.symlink(new File(nativeDir,name).getPath(),new File(framework,name).getPath());
            Os.symlink(new File(nativeDir,"libcrypto.so").getPath(),new File(links,"libcrypto.so.3").getPath());
            Os.symlink(new File(nativeDir,"libssl.so").getPath(),new File(links,"libssl.so.3").getPath());
            JSONObject pythonLinks=new JSONObject(text(new File(root,"python-links.json")));
            Iterator<String> pythonNames=pythonLinks.keys();
            while(pythonNames.hasNext()){
                String name=pythonNames.next();File link=new File(root,name);File target=new File(nativeDir,pythonLinks.getString(name)).getCanonicalFile();
                if(name.startsWith("/") || name.contains("..") || !link.getParentFile().getCanonicalPath().startsWith(root.getCanonicalPath()+"/") || !target.getParentFile().equals(nativeDir) || !hashes.has(target.getName()))throw new IOException("native link boundary");
                link.getParentFile().mkdirs();
                if(link.exists()){if(!link.getCanonicalFile().equals(target))throw new IOException("existing native link differs");}
                else Os.symlink(target.getPath(),link.getPath());
            }
            if (updateAction != null) systemTrust(root);
            File ownerJob=new File(getFilesDir(), updateAction == null ? "owner-input/request.json" : "owner-input/update-request.json");
            if(ownerJob.isFile()) {
                List<String> backend=Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),new File(nativeDir,"libpython3.14.so").getPath(),new File(root,"python").getPath(),new File(root, OwnerUpdateState.backendScript(updateAction)).getPath(),ownerJob.getPath(),root.getPath(),nativeDir.getPath());
                report.put("ownerBackend",child("owner-backend",backend,root,nativeDir,links));
                File ready=new File(getFilesDir(),"owner-input/owner-apk-ready.json");
                JSONObject job=new JSONObject(text(ownerJob));
                if((job.has("signing")||job.has("packaging")||("release-build".equals(updateAction) || "release-rollback".equals(updateAction)))&&ready.isFile()) {
                    JSONObject apk=new JSONObject(text(ready)); File file=new File(apk.getString("apk")).getCanonicalFile();
                    if(!file.getPath().startsWith(getFilesDir().getCanonicalPath()+"/")||!hash(file).equals(apk.getString("sha256")))throw new IOException("owner APK output drift");
                    report.put("ownerApk",apk);
                }
                report.put("success",true);
            } else {
            if (updateAction != null) throw new IOException("Explicit update request required");
            List<String> prefix=Arrays.asList(new File(nativeDir,"libtoolhost.so").getPath(),new File(nativeDir,"libhostfxr.so").getPath(),runtime.getPath());
            List<String> version=new ArrayList<>(prefix);version.add(new File(root,"compiler/csc.dll").getPath());version.add("-version");
            report.put("compilerVersion",child("version",version,root,nativeDir,links));
            List<String> compile=new ArrayList<>(prefix);compile.add(new File(root,"compiler/csc.dll").getPath());compile.addAll(Arrays.asList("/nologo","/noconfig","/nostdlib+","/target:exe","/out:"+new File(root,"Hello.dll").getPath()));
            File[] refs=new File(root,"refs").listFiles();Arrays.sort(refs);
            for(File reference:refs) if(reference.getName().endsWith(".dll"))compile.add("/r:"+reference.getPath());
            compile.add(new File(root,"Hello.cs").getPath());report.put("compile",child("compile",compile,root,nativeDir,links));
            List<String> run=new ArrayList<>(prefix);run.add(new File(root,"Hello.dll").getPath());report.put("run",child("run",run,root,nativeDir,links));
            if(!text(new File(root,"run.log")).contains("PHONE_TOOL_HOST_OK 8.0.32 "))throw new IOException("managed output marker missing");
            report.put("helloSha256",hash(new File(root,"Hello.dll")));report.put("success",true);
            report.put("success",false);
            List<String> python=Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),new File(nativeDir,"libpython3.14.so").getPath(),new File(root,"python").getPath(),new File(root,"run_profile.py").getPath(),root.getPath());
            report.put("publicProfileChild",child("public-profile",python,root,nativeDir,links));
            JSONObject pythonReport=new JSONObject(text(new File(root,"python-profile-report.json")));
            JSONObject publicReceipt=new JSONObject(text(new File(root,"repo/work/rebuild/app-component-v1/public-tools-receipt.json")));
            if(!pythonReport.getBoolean("success") || !publicReceipt.getBoolean("success") || publicReceipt.getBoolean("game_assemblies_executed"))throw new IOException("public producer contract differs");
            report.put("pythonProfile",pythonReport);report.put("publicReceipt",publicReceipt);report.put("success",true);
            }
        }catch(Exception error){
            try{report.put("failure",error.toString());}catch(Exception ignored){}
            if (updateAction != null) {
                try {
                    File thermal = new File(getFilesDir(), "owner-input/thermal-state.json");
                    JSONObject cooling = thermal.isFile() ? readJson(thermal) : new JSONObject();
                    File status = new File(getFilesDir(), "owner-input/update-state.json");
                    JSONObject prior = status.isFile() ? readJson(status) : new JSONObject();
                    if ("cancelled".equals(cooling.optString("status")) || cancelled) {
                        if (("release-build".equals(updateAction) || "release-rollback".equals(updateAction))) reconcileBuildStop(app, "CANCELLED", "Cancelled. Verified stage checkpoints are retained; tap Resume when ready.");
                        else updateStatus(app, "CANCELLED", "Cancelled. Retained public downloads can be verified on retry.");
                    } else if (("release-build".equals(updateAction) || "release-rollback".equals(updateAction))) reconcileBuildStop(app, "ERROR", cooling.has("error") ? cooling.optString("error") : prior.optString("message", error.toString()));
                    else if (!"ERROR".equals(prior.optString("state"))) updateStatus(app, "ERROR", cooling.has("error") ? cooling.optString("error") : error.toString());
                } catch (Exception ignored) { updateStatus(app, "ERROR", error.toString()); }
            }
        }
        try {
            writeJson(new File(getFilesDir(), updateAction == null ? "tool-host-report.json" : "update-tool-report.json"), report);
            if (("release-build".equals(updateAction) || "release-rollback".equals(updateAction)) && report.getBoolean("success") && report.has("ownerApk"))
                writeJson(new File(getFilesDir(), "tool-host-report.json"), report);
        } catch(Exception error) { if (updateAction != null) updateStatus(app, "ERROR", "Could not retain build result: " + error.getMessage()); }
    }
    }
}
