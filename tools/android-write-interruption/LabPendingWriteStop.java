// Authored shell diagnostic: observe the owned settings transaction, then stop
// only that package through the normal ActivityManager shell permission.
import android.os.FileObserver;
import android.os.Process;
import android.os.SystemClock;
import java.io.File;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONObject;

public final class LabPendingWriteStop {
    private static final String PACKAGE = "dev.ror2lab.arm64";
    private static void bind(int pid, int uid) throws Exception {
        String name = new String(Files.readAllBytes(Paths.get("/proc/" + pid + "/cmdline")), StandardCharsets.UTF_8);
        String status = new String(Files.readAllBytes(Paths.get("/proc/" + pid + "/status")), StandardCharsets.UTF_8);
        if (!name.split("\0", 2)[0].equals(PACKAGE) || !java.util.regex.Pattern.compile("(?m)^Uid:\\s+" + uid + "\\s").matcher(status).find())
            throw new IllegalStateException("Owned PID/UID binding changed");
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 4 || Process.myUid() != 2000)
            throw new IllegalArgumentException("Requires shell, settings directory, ready path, observed PID and UID");
        final File directory = new File(args[0]).getCanonicalFile();
        final File pending = new File(directory, "preferences.json.pending");
        final File ready = new File(args[1]);
        final int pid = Integer.parseInt(args[2]), uid = Integer.parseInt(args[3]);
        if (pid <= 0 || uid < 10000 || !directory.isDirectory()
            || !directory.getPath().endsWith("/Android/data/" + PACKAGE + "/files/offline-settings-v1")
            || !ready.getPath().matches("/data/local/tmp/ror2lab-write-[0-9a-f]{32}\\.ready")
            || ready.exists() || pending.exists())
            throw new IllegalArgumentException("Unexpected transaction or temporary path");
        bind(pid, uid);
        final Object activity = Class.forName("android.app.ActivityManager").getMethod("getService").invoke(null);
        final Class<?> api = Class.forName("android.app.IActivityManager");
        final Method stop = api.getMethod("forceStopPackage", String.class, int.class);
        final Method state = api.getMethod("getUidProcessState", int.class, String.class);
        final CountDownLatch done = new CountDownLatch(1);
        final AtomicBoolean triggered = new AtomicBoolean();
        final AtomicReference<Throwable> failure = new AtomicReference<>();
        final JSONObject result = new JSONObject();
        FileObserver observer = new FileObserver(directory, FileObserver.CREATE) {
            @Override public void onEvent(int event, String name) {
                if ((event & FileObserver.CREATE) == 0 || !"preferences.json.pending".equals(name) || !triggered.compareAndSet(false, true)) return;
                try {
                    bind(pid, uid);
                    if (((Integer)state.invoke(activity, uid, "com.android.shell")) != 2)
                        throw new IllegalStateException("Owned UID left foreground before interruption");
                    result.put("createObserved", true).put("pendingPresentBeforeStop", pending.isFile())
                        .put("pendingBytesBeforeStop", pending.length());
                    long started = SystemClock.uptimeMillis();
                    stop.invoke(activity, PACKAGE, uid / 100000);
                    result.put("stopMilliseconds", SystemClock.uptimeMillis() - started)
                        .put("pendingPresentAfterStop", pending.isFile()).put("pendingBytesAfterStop", pending.length());
                } catch (Throwable error) { failure.set(error); }
                finally { done.countDown(); }
            }
        };
        try {
            observer.startWatching();
            if (!ready.createNewFile()) throw new IllegalStateException("Ready target already exists");
            if (!done.await(30, TimeUnit.SECONDS)) throw new IllegalStateException("No pending-file create observed within 30 seconds");
            if (failure.get() != null) throw new IllegalStateException("Interruption refused", failure.get());
            System.out.println(result.put("success", true).toString());
        } finally { observer.stopWatching(); }
    }
}
