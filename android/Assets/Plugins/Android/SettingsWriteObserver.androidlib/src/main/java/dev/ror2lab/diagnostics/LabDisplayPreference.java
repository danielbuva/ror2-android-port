package dev.ror2lab.diagnostics;

import android.app.Activity;
import android.os.Build;
import android.util.Log;
import android.view.Display;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import java.lang.ref.WeakReference;
import java.util.ArrayList;

/** Application-owned display request. All window/surface state stays on the UI thread. */
public final class LabDisplayPreference implements SurfaceHolder.Callback {
    private static volatile String observation = "unavailable: awaiting UI thread";

    /** Read only; asynchronous UI observation never blocks the Unity thread. */
    public static String observe(Activity current) {
        current.runOnUiThread(() -> {
            if (current.isDestroyed()) return;
            Display display = current.getWindowManager().getDefaultDisplay();
            Display.Mode mode = display.getMode();
            WindowManager.LayoutParams attributes = current.getWindow().getAttributes();
            observation = "uptimeMs=" + android.os.SystemClock.uptimeMillis()
                    + " mode=" + mode.getModeId() + " modeRate=" + mode.getRefreshRate()
                    + " observedRate=" + display.getRefreshRate()
                    + " preferredMode=" + attributes.preferredDisplayModeId
                    + " preferredRate=" + attributes.preferredRefreshRate;
        });
        return observation;
    }
    private final WeakReference<Activity> activity;
    private final ArrayList<SurfaceHolder> holders = new ArrayList<>();
    private boolean captured, closed;
    private int priorMode;
    private float priorRate, requestedRate;

    public LabDisplayPreference(Activity activity) {
        this.activity = new WeakReference<>(activity);
    }

    public void apply(final boolean highRefreshRate) {
        final Activity current = activity.get();
        if (current == null) return;
        current.runOnUiThread(() -> {
            if (closed || current.isDestroyed()) return;
            WindowManager.LayoutParams attributes = current.getWindow().getAttributes();
            if (!captured) {
                priorMode = attributes.preferredDisplayModeId;
                priorRate = attributes.preferredRefreshRate;
                captured = true;
            }
            Display display = current.getWindowManager().getDefaultDisplay();
            Display.Mode active = display.getMode();
            Display.Mode selected = active;
            for (Display.Mode mode : display.getSupportedModes()) {
                // Preserve the current physical resolution and display; only rate is a preference.
                if (mode.getPhysicalWidth() != active.getPhysicalWidth()
                        || mode.getPhysicalHeight() != active.getPhysicalHeight()) continue;
                boolean better = highRefreshRate
                        ? mode.getRefreshRate() > selected.getRefreshRate()
                        : Math.abs(mode.getRefreshRate() - 60f) < Math.abs(selected.getRefreshRate() - 60f);
                if (better) selected = mode;
            }
            requestedRate = selected.getRefreshRate();
            attributes.preferredDisplayModeId = selected.getModeId();
            attributes.preferredRefreshRate = requestedRate;
            current.getWindow().setAttributes(attributes);
            clearSurfaces();
            collect(current.getWindow().getDecorView());
            for (SurfaceHolder holder : holders) hint(holder, requestedRate);
            Log.i("RoR2LabDisplay", "request high=" + highRefreshRate + " mode=" + selected.getModeId()
                    + " rate=" + requestedRate + " observed=" + display.getRefreshRate()
                    + " surfaces=" + holders.size());
        });
    }

    private void collect(View view) {
        if (view instanceof SurfaceView) {
            SurfaceHolder holder = ((SurfaceView) view).getHolder();
            if (!holders.contains(holder)) {
                holders.add(holder);
                holder.addCallback(this);
            }
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) collect(group.getChildAt(i));
        }
    }

    private static void hint(SurfaceHolder holder, float rate) {
        Surface surface = holder.getSurface();
        if (Build.VERSION.SDK_INT >= 30 && surface != null && surface.isValid())
            surface.setFrameRate(rate, Surface.FRAME_RATE_COMPATIBILITY_DEFAULT);
    }

    private void clearSurfaces() {
        for (SurfaceHolder holder : holders) {
            hint(holder, 0f);
            holder.removeCallback(this);
        }
        holders.clear();
    }

    @Override public void surfaceCreated(SurfaceHolder holder) { if (!closed) hint(holder, requestedRate); }
    @Override public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
        if (!closed) hint(holder, requestedRate);
    }
    @Override public void surfaceDestroyed(SurfaceHolder holder) { }

    public void close() {
        final Activity current = activity.get();
        if (current == null) return;
        current.runOnUiThread(() -> {
            if (closed) return;
            closed = true;
            clearSurfaces();
            if (captured && !current.isDestroyed()) {
                WindowManager.LayoutParams attributes = current.getWindow().getAttributes();
                attributes.preferredDisplayModeId = priorMode;
                attributes.preferredRefreshRate = priorRate;
                current.getWindow().setAttributes(attributes);
            }
            activity.clear();
        });
    }
}
