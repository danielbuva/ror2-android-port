package dev.ror2lab.diagnostics;

// Authored debug-UID diagnostic: observe the real settings transaction and
// terminate only its PID/UID-bound writer through normal same-UID signalling.
import android.os.FileObserver;
import android.os.Process;
import android.os.SystemClock;
import java.io.File;
import android.system.Os;
import android.system.OsConstants;
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
    static void enforceDeadline(final long milliseconds) {
        Thread deadline = new Thread(() -> {
            try { Thread.sleep(milliseconds); }
            catch (InterruptedException cancelled) { return; }
            System.err.println("Owned settings observer exceeded its deadline");
            System.err.flush();
            Runtime.getRuntime().halt(124);
        }, "owned-settings-observer-deadline");
        deadline.setDaemon(true);
        deadline.start();
    }
    public static void main(String[] args) {
        enforceDeadline(35000);
        try {
            run(args);
            System.out.flush();
            System.exit(0);
        } catch (Throwable error) {
            error.printStackTrace(System.err);
            System.err.flush();
            System.exit(1);
        }
    }
    private static void run(String[] args) throws Exception {
        System.out.println(observe(args, () -> false).toString());
    }
    public static void atomicJson(File destination, JSONObject value) throws Exception {
        File temporary = new File(destination.getPath() + ".tmp");
        Files.write(temporary.toPath(), value.toString().getBytes(StandardCharsets.UTF_8), java.nio.file.StandardOpenOption.CREATE_NEW);
        Files.move(temporary.toPath(), destination.toPath(), java.nio.file.StandardCopyOption.ATOMIC_MOVE);
    }
    static String observerNonce(File ready) {
        String name = ready.getName();
        return name.substring("ror2lab-write-".length(), name.length() - ".ready".length());
    }
    public static JSONObject observe(String[] args, java.util.function.BooleanSupplier cancelled) throws Exception {
        if (args.length != 4)
            throw new IllegalArgumentException("Requires owned debug UID, settings directory, ready path, observed PID and UID");
        final File directory = new File(args[0]).getCanonicalFile();
        final File pending = new File(directory, "preferences.json.pending");
        final File ready = new File(args[1]);
        final int pid = Integer.parseInt(args[2]), uid = Integer.parseInt(args[3]);
        if (pid <= 0 || uid < 10000 || Process.myUid() != uid || !directory.isDirectory()
            || !directory.getPath().endsWith("/Android/data/" + PACKAGE + "/files/offline-settings-v1")
            || !ready.getCanonicalFile().getParentFile().equals(directory.getParentFile())
            || !ready.getName().matches("ror2lab-write-[0-9a-f]{32}\\.ready")
            || ready.exists() || pending.exists())
            throw new IllegalArgumentException("Unexpected transaction or temporary path");
        bind(pid, uid);
        final CountDownLatch done = new CountDownLatch(1);
        final AtomicBoolean triggered = new AtomicBoolean();
        final AtomicReference<Throwable> failure = new AtomicReference<>();
        final JSONObject result = new JSONObject();
        FileObserver observer = new FileObserver(directory, FileObserver.CREATE) {
            @Override public void onEvent(int event, String name) {
                if (cancelled.getAsBoolean() || (event & FileObserver.CREATE) == 0 || !"preferences.json.pending".equals(name) || !triggered.compareAndSet(false, true)) return;
                try {
                    bind(pid, uid);
                    result.put("createObserved", true).put("pendingPresentBeforeStop", pending.isFile())
                        .put("pendingBytesBeforeStop", pending.length());
                    long started = SystemClock.uptimeMillis();
                    Os.kill(pid, OsConstants.SIGKILL);
                    while (Files.exists(Paths.get("/proc/" + pid)) && SystemClock.uptimeMillis() - started < 1000)
                        SystemClock.sleep(1);
                    if (Files.exists(Paths.get("/proc/" + pid)))
                        throw new IllegalStateException("Bound writer did not exit after same-UID termination");
                    result.put("writerExited", true).put("stopMilliseconds", SystemClock.uptimeMillis() - started)
                        .put("pendingPresentAfterStop", pending.isFile()).put("pendingBytesAfterStop", pending.length());
                } catch (Throwable error) { failure.set(error); }
                finally { done.countDown(); }
            }
        };
        try {
            observer.startWatching();
            atomicJson(ready, new JSONObject().put("nonce", observerNonce(ready))
                .put("pid", pid).put("uid", uid).put("observerPid", Process.myPid()));
            long deadline = SystemClock.uptimeMillis() + 30000;
            while (!done.await(100, TimeUnit.MILLISECONDS)) {
                if (cancelled.getAsBoolean()) throw new InterruptedException("Owner cancelled observer");
                if (SystemClock.uptimeMillis() >= deadline) throw new IllegalStateException("No pending-file create observed within 30 seconds");
            }
            if (failure.get() != null) throw new IllegalStateException("Interruption refused", failure.get());
            return result.put("success", true);
        } finally { observer.stopWatching(); }
    }
}
