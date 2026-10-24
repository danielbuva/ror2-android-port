// Authored shell diagnostic. Normal INJECT_EVENTS permission is required;
// Android 13's targetUid overload confines every event to the owned app UID.
import android.os.Process;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import org.json.JSONArray;
import org.json.JSONObject;

public final class LabTouchGesture {
    private static final class Point {
        int id;
        float x, y;
        Point(int id, float x, float y) { this.id = id; this.x = x; this.y = y; }
    }
    private final ArrayList<Point> points = new ArrayList<>();
    private final Object input;
    private final Method inject;
    private final Object activity;
    private final Method uidState;
    private final int uid, device;
    private long downTime;
    private int sent;
    private String termination = "steps-complete";

    private LabTouchGesture(int uid) throws Exception {
        if (Process.myUid() != 2000 || uid < 10000)
            throw new IllegalStateException("Requires authorized adb shell and an application UID");
        this.uid = uid;
        Class<?> manager = Class.forName("android.hardware.input.InputManager");
        input = manager.getMethod("getInstance").invoke(null);
        // Refuse unavailable targeted injection; never fall back to all windows.
        inject = manager.getMethod("injectInputEvent", InputEvent.class, int.class, int.class);
        activity = Class.forName("android.app.ActivityManager").getMethod("getService").invoke(null);
        uidState = Class.forName("android.app.IActivityManager").getMethod("getUidProcessState", int.class, String.class);
        int found = 0;
        for (int id : InputDevice.getDeviceIds()) {
            InputDevice candidate = InputDevice.getDevice(id);
            if (candidate != null && candidate.supportsSource(InputDevice.SOURCE_TOUCHSCREEN)) {
                found = id;
                break;
            }
        }
        device = found;
    }
    private boolean foreground() throws Exception {
        // PROCESS_STATE_TOP is 2 on the supported Android 13 framework.
        if (((Integer)uidState.invoke(activity, uid, "com.android.shell")) == 2) return true;
        if (sent == 0) throw new IllegalStateException("Owned UID left foreground before injection");
        // Home ends the window's pointer stream. Do not inject a stale UP or
        // CANCEL into a background window, or keep a shell actor across sleep.
        termination = "focus-lost";
        points.clear();
        return false;
    }
    private int index(int id) {
        for (int i = 0; i < points.size(); i++) if (points.get(i).id == id) return i;
        return -1;
    }
    private void send(int action) throws Exception {
        int count = points.size();
        MotionEvent.PointerProperties[] properties = new MotionEvent.PointerProperties[count];
        MotionEvent.PointerCoords[] coordinates = new MotionEvent.PointerCoords[count];
        for (int i = 0; i < count; i++) {
            Point point = points.get(i);
            properties[i] = new MotionEvent.PointerProperties();
            properties[i].id = point.id;
            properties[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
            coordinates[i] = new MotionEvent.PointerCoords();
            coordinates[i].x = point.x;
            coordinates[i].y = point.y;
            int masked = action & MotionEvent.ACTION_MASK;
            boolean released = masked == MotionEvent.ACTION_UP || masked == MotionEvent.ACTION_CANCEL
                || masked == MotionEvent.ACTION_POINTER_UP && i == (action >> MotionEvent.ACTION_POINTER_INDEX_SHIFT);
            coordinates[i].pressure = released ? 0 : 1;
            coordinates[i].size = 1;
        }
        MotionEvent event = MotionEvent.obtain(downTime, SystemClock.uptimeMillis(), action,
            count, properties, coordinates, 0, 0, 1, 1, device, 0,
            InputDevice.SOURCE_TOUCHSCREEN, 0);
        try {
            // WAIT_FOR_RESULT checks dispatch permission/target without waiting
            // for Unity to finish handling the frame.
            if (!Boolean.TRUE.equals(inject.invoke(input, event, 1, uid)))
                throw new IllegalStateException("Targeted touch dispatch refused");
            sent++;
        } finally { event.recycle(); }
    }
    private void execute(JSONArray steps) throws Exception {
        int totalWait = 0;
        if (steps.length() < 1 || steps.length() > 128)
            throw new IllegalArgumentException("Use 1 to 128 gesture steps");
        try {
            for (int i = 0; i < steps.length(); i++) {
                if (!foreground()) return;
                JSONObject step = steps.getJSONObject(i);
                String action = step.getString("action");
                if (action.equals("wait")) {
                    int milliseconds = step.getInt("ms");
                    totalWait += milliseconds;
                    if (milliseconds < 0 || totalWait > 30000)
                        throw new IllegalArgumentException("Gesture waits exceed 30 seconds");
                    long until = SystemClock.uptimeMillis() + milliseconds;
                    while (true) {
                        if (!foreground()) return;
                        long remaining = until - SystemClock.uptimeMillis();
                        if (remaining <= 0) break;
                        SystemClock.sleep(Math.min(remaining, 50));
                    }
                    continue;
                }
                int id = step.getInt("id"), slot = index(id);
                float x = (float)step.getDouble("x"), y = (float)step.getDouble("y");
                if (id < 0 || id > 9 || Float.isNaN(x) || Float.isNaN(y) || Float.isInfinite(x) || Float.isInfinite(y))
                    throw new IllegalArgumentException("Invalid pointer");
                if (action.equals("down")) {
                    if (slot >= 0 || points.size() >= 10)
                        throw new IllegalArgumentException("Pointer already held or too many fingers");
                    if (points.isEmpty()) downTime = SystemClock.uptimeMillis();
                    points.add(new Point(id, x, y));
                    int edge = points.size() == 1 ? MotionEvent.ACTION_DOWN
                        : MotionEvent.ACTION_POINTER_DOWN | ((points.size() - 1) << MotionEvent.ACTION_POINTER_INDEX_SHIFT);
                    send(edge);
                } else {
                    if (slot < 0) throw new IllegalArgumentException("Pointer is not held");
                    Point point = points.get(slot);
                    point.x = x; point.y = y;
                    if (action.equals("move")) send(MotionEvent.ACTION_MOVE);
                    else if (action.equals("up")) {
                        send(points.size() == 1 ? MotionEvent.ACTION_UP
                            : MotionEvent.ACTION_POINTER_UP | (slot << MotionEvent.ACTION_POINTER_INDEX_SHIFT));
                        points.remove(slot);
                    } else throw new IllegalArgumentException("Unknown touch action");
                }
            }
        } finally {
            if (!points.isEmpty()) {
                try { if (foreground()) send(MotionEvent.ACTION_CANCEL); }
                finally { points.clear(); }
            }
        }
    }
    public static void main(String[] args) throws Exception {
        JSONObject request = new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])), StandardCharsets.UTF_8));
        LabTouchGesture gesture = new LabTouchGesture(Integer.parseInt(args[1]));
        gesture.execute(request.getJSONArray("steps"));
        System.out.println(new JSONObject().put("success", true).put("events", gesture.sent)
            .put("termination", gesture.termination).toString());
    }
}
