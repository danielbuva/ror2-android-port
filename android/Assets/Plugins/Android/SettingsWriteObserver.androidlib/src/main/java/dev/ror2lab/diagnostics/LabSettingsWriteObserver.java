package dev.ror2lab.diagnostics;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Process;
import java.util.concurrent.atomic.AtomicBoolean;

/** Default-off same-UID observer; never changes the original settings save. */
public final class LabSettingsWriteObserver extends Service {
    private final AtomicBoolean cancelled = new AtomicBoolean();
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

    @Override public IBinder onBind(Intent intent) {
        return null;
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        handler.removeCallbacks(deadline);
        handler.postDelayed(deadline, 10000);
        return START_NOT_STICKY;
    }

    @Override public void onDestroy() {
        handler.removeCallbacks(deadline);
        cancelled.set(true);
        super.onDestroy();
    }
}
