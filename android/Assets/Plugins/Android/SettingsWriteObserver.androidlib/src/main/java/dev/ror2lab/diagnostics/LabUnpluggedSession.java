package dev.ror2lab.diagnostics;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** One USB-armed owner session. Safety sampling does not depend on Unity frames. */
public final class LabUnpluggedSession {
    private static final String REQUEST = "owner-unplugged-request.json";
    private static final long DURATION_MS = 30 * 60 * 1000L;
    private static final long UNPLUG_TIMEOUT_MS = 5 * 60 * 1000L;

    private final Activity activity;
    private final File logFile;
    private final String nonce;
    private final JSONArray zones;
    private final BatteryManager battery;
    private final PowerManager power;
    private final IntentFilter batteryChanged = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
    private final Thread worker;
    private volatile int foregroundFrames;
    private volatile boolean closing;

    public static LabUnpluggedSession start(Activity activity) {
        try {
            File root = activity.getExternalFilesDir(null);
            if (root == null) throw new IOException("App storage unavailable");
            File request = new File(root, REQUEST);
            JSONObject config = new JSONObject(readLine(request));
            if (!request.delete()) throw new IOException("Could not consume owner session request");
            LabUnpluggedSession session = new LabUnpluggedSession(activity, root, config);
            session.worker.start();
            return session;
        } catch (Exception error) {
            Log.e("LabUnpluggedSession", "Could not arm unplugged session", error);
            return null;
        }
    }

    private LabUnpluggedSession(Activity activity, File root, JSONObject config) throws Exception {
        this.activity = activity;
        nonce = config.getString("nonce");
        if (!nonce.matches("[0-9a-f]{32}")) throw new IOException("Invalid owner session nonce");
        logFile = new File(root, "owner-unplugged-" + nonce + ".jsonl");
        zones = config.getJSONArray("zones");
        battery = activity.getSystemService(BatteryManager.class);
        power = activity.getSystemService(PowerManager.class);
        worker = new Thread(this::record, "lab-unplugged-sampler");
    }

    public void observeFrame(int count) {
        foregroundFrames = count;
    }

    public void close() {
        closing = true;
        worker.interrupt();
    }

    private void record() {
        try {
            if (!logFile.createNewFile()) throw new IOException("Owner session log already exists");
            try (FileOutputStream stream = new FileOutputStream(logFile)) {
                try {
                    sampleSession(stream);
                } catch (Exception error) {
                    write(stream, row("aborted").put("reason", error.toString()));
                    stream.getFD().sync();
                    if (!closing) Process.killProcess(Process.myPid());
                    return;
                }
                stream.getFD().sync();
            }
            activity.runOnUiThread(() -> {
                Toast.makeText(activity, "Unplugged recording finished. Reconnect USB.", Toast.LENGTH_LONG).show();
                activity.finish();
            });
        } catch (Exception error) {
            Log.e("LabUnpluggedSession", "Could not persist unplugged telemetry", error);
            if (!closing) Process.killProcess(Process.myPid());
        }
    }

    private void sampleSession(FileOutputStream stream) throws Exception {
        boolean hasCpu = false;
        boolean hasGpu = false;
        for (int index = 0; index < zones.length(); index++) {
            JSONArray zone = zones.getJSONArray(index);
            String kind = zone.getString(0);
            String path = zone.getString(1);
            if (!path.matches("/sys/class/thermal/thermal_zone[0-9]+/temp"))
                throw new IOException("Invalid thermal sensor path");
            if (kind.equals("cpu")) hasCpu = true;
            else if (kind.equals("gpu")) hasGpu = true;
            else if (!kind.equals("battery") && !kind.equals("skin")) throw new IOException("Invalid thermal sensor class");
        }
        if (!hasCpu || !hasGpu) throw new IOException("CPU and GPU sensor coverage is required");

        long[] hotSince = new long[zones.length()];
        long readyAt = SystemClock.elapsedRealtime();
        long previous = readyAt;
        long start = -1;
        boolean ready = false;
        while (!closing) {
            long now = SystemClock.elapsedRealtime();
            Intent state = activity.registerReceiver(null, batteryChanged);
            if (state == null) throw new IOException("Battery telemetry unavailable");
            int temperature = state.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
            int plugged = state.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1);
            int level = state.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = state.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
            int voltage = state.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1);
            long current = battery.getLongProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);
            long charge = battery.getLongProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER);
            if (temperature < -100 || plugged < 0 || level < 0 || level > scale || scale <= 0 || voltage <= 0 || current == Long.MIN_VALUE)
                throw new IOException("Required battery telemetry unavailable");

            JSONArray temperatures = new JSONArray();
            int cpuGpuPeak = Integer.MIN_VALUE;
            int batteryPeak = temperature * 100;
            int skinPeak = Integer.MIN_VALUE;
            for (int index = 0; index < zones.length(); index++) {
                JSONArray zone = zones.getJSONArray(index);
                int value = Integer.parseInt(readLine(new File(zone.getString(1))));
                if (value <= -30000) throw new IOException("Thermal sensor unavailable: " + zone.getString(1));
                temperatures.put(value);
                if (zone.getString(0).equals("battery")) {
                    batteryPeak = Math.max(batteryPeak, value);
                    continue;
                }
                if (zone.getString(0).equals("skin")) {
                    skinPeak = Math.max(skinPeak, value);
                    continue;
                }
                cpuGpuPeak = Math.max(cpuGpuPeak, value);
                if (value <= 95000) hotSince[index] = 0;
                else if (hotSince[index] == 0) hotSince[index] = now;
                else if (now - hotSince[index] >= 3000) {
                    throw new IOException("CPU/GPU sensor above 95 C for three seconds: " + zone.getString(1));
                }
            }
            if (batteryPeak >= 43000) throw new IOException("Battery at or above 43 C");
            long at = SystemClock.elapsedRealtime();
            long gap = at - previous;
            if (gap > 5000) throw new IOException("Thermal sample gap exceeded five seconds");
            previous = at;

            if (!ready) {
                if (plugged == 0) throw new IOException("External power must be present when arming");
                write(stream, row("ready").put("zones", zones));
                stream.getFD().sync();
                ready = true;
            }
            if (start < 0 && plugged == 0) {
                if (batteryPeak > 35000 || Math.max(cpuGpuPeak, skinPeak) > 50000 || level * 100 > scale * 85)
                    throw new IOException("Cool-start admission failed at USB disconnect");
                start = at;
            }
            if (start >= 0) {
                if (plugged != 0) throw new IOException("External power returned before recording completed");
                write(stream, row("sample")
                    .put("elapsed_ms", at - start)
                    .put("gap_ms", gap)
                    .put("plugged", plugged)
                    .put("level", level)
                    .put("scale", scale)
                    .put("battery_decic", temperature)
                    .put("voltage_mv", voltage)
                    .put("current_ua", current)
                    .put("charge_uah", charge == Long.MIN_VALUE ? JSONObject.NULL : charge)
                    .put("thermal_status", Build.VERSION.SDK_INT >= 29 ? power.getCurrentThermalStatus() : JSONObject.NULL)
                    .put("zones_millic", temperatures)
                    .put("frames", foregroundFrames));
                if (at - start >= DURATION_MS) {
                    write(stream, row("complete"));
                    return;
                }
            } else if (at - readyAt >= UNPLUG_TIMEOUT_MS) {
                throw new IOException("USB was not unplugged after arming");
            }

            Thread.sleep(Math.max(0, 250 - (SystemClock.elapsedRealtime() - now)));
        }
        throw new IOException("Player stopped before recording completed");
    }

    private JSONObject row(String kind) throws Exception {
        return new JSONObject().put("kind", kind).put("nonce", nonce).put("pid", Process.myPid());
    }

    private static void write(FileOutputStream stream, JSONObject row) throws IOException {
        stream.write((row.toString() + "\n").getBytes(StandardCharsets.UTF_8));
    }

    private static String readLine(File path) throws IOException {
        try (BufferedReader reader = new BufferedReader(new FileReader(path))) {
            String line = reader.readLine();
            if (line == null) throw new IOException("Empty telemetry input: " + path.getName());
            return line;
        }
    }
}
