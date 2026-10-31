package dev.ror2lab.diagnostics;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Process;
import java.io.File;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/** Default-off same-UID observer; never changes the original settings save. */
public final class LabSettingsWriteObserver extends Service {
    private final AtomicBoolean cancelled = new AtomicBoolean();
    private Thread worker;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable deadline = () -> { cancelled.set(true); stopSelf(); };

    public static void start(Context context, String nonce) {
        if (nonce == null || !nonce.matches("[0-9a-f]{32}")) throw new IllegalArgumentException("Invalid nonce");
        Intent intent = new Intent(context, LabSettingsWriteObserver.class);
        intent.putExtra("nonce", nonce).putExtra("writerPid", Process.myPid());
        context.startService(intent);
    }
    public static void cancel(Context context) {
        context.stopService(new Intent(context, LabSettingsWriteObserver.class));
    }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || worker != null) return START_NOT_STICKY;
        final String nonce = intent.getStringExtra("nonce");
        final int pid = intent.getIntExtra("writerPid", -1);
        if (nonce == null || !nonce.matches("[0-9a-f]{32}") || pid <= 0 || pid == Process.myPid()) {
            stopSelf(); return START_NOT_STICKY;
        }
        final File runtime = getExternalFilesDir(null);
        if (runtime == null) { stopSelf(); return START_NOT_STICKY; }
        handler.postDelayed(deadline, 35000);
        worker = new Thread(() -> {
            JSONObject result = new JSONObject();
            try {
                result = LabPendingWriteStop.observe(new String[] {
                    new File(runtime, "offline-settings-v1").getPath(),
                    new File(runtime, "ror2lab-write-" + nonce + ".ready").getPath(),
                    Integer.toString(pid), Integer.toString(Process.myUid())
                }, cancelled::get);
            } catch (Throwable error) {
                try { result.put("success", false).put("error", error.toString()); }
                catch (Exception ignored) { }
            } finally {
                try {
                    result.put("nonce", nonce).put("pid", pid).put("uid", Process.myUid()).put("observerPid", Process.myPid());
                    LabPendingWriteStop.atomicJson(new File(runtime, "ror2lab-write-" + nonce + ".result"), result);
                } catch (Exception error) { android.util.Log.e("SettingsWriteObserver", "Cannot persist witness", error); }
                handler.post(() -> stopSelf(startId));
            }
        }, "settings-write-observer");
        worker.start();
        return START_NOT_STICKY;
    }
    @Override public void onDestroy() {
        cancelled.set(true);
        handler.removeCallbacks(deadline);
        super.onDestroy();
    }
}
