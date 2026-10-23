package dev.ror2owner.bootstrap;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Hash-bound, per-file transactional preparation inside the calling app's data. */
public final class PayloadStore {
    public static final long RESERVE = 2L * 1024 * 1024 * 1024;
    private static final long MAX_FILE = 2L * 1024 * 1024 * 1024 - 1;
    private static final long DEADLINE_NANOS = 900L * 1000 * 1000 * 1000;

    public interface Source {
        InputStream open(String name) throws IOException;
        long availableBytes() throws IOException;
    }
    public interface Progress {
        void update(String phase, long done, long total);
        boolean pauseRequested();
    }
    public static final class Row {
        public final String name;
        public final String sha256;
        public final long bytes;
        public Row(String name, long bytes, String sha256) {
            if (!name.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,179}")
                    || !sha256.matches("[0-9a-f]{64}") || bytes < 0 || bytes > MAX_FILE)
                throw new IllegalArgumentException("Invalid payload record");
            this.name = name;
            this.bytes = bytes;
            this.sha256 = sha256;
        }
    }
    public static final class Paused extends IOException {
        Paused() { super("Preparation paused between files"); }
    }
    public static final class Drift extends IOException {
        public final Map<String, String> observed;
        Drift(Map<String, String> observed) {
            super("Existing prepared files require review");
            this.observed = Collections.unmodifiableMap(new HashMap<>(observed));
        }
    }

    private PayloadStore() {}

    private static MessageDigest digest() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException error) { throw new IllegalStateException(error); }
    }
    private static String hex(byte[] value) {
        StringBuilder text = new StringBuilder(value.length * 2);
        for (byte b : value) text.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        return text.toString();
    }
    public static String hash(File path) throws IOException {
        if (!path.getAbsoluteFile().equals(path.getCanonicalFile()) || !path.isFile()
                || path.length() > MAX_FILE) throw new IOException("Invalid prepared file");
        MessageDigest sha = digest();
        try (InputStream input = new FileInputStream(path)) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = input.read(buffer)) != -1) sha.update(buffer, 0, count);
        }
        return hex(sha.digest());
    }
    private static File child(File root, String name) throws IOException {
        File result = new File(root, name).getAbsoluteFile();
        if (!result.getCanonicalFile().equals(result)
                || !result.getPath().startsWith(root.getPath() + File.separator))
            throw new IOException("Unsafe preparation path");
        return result;
    }
    private static File directory(File parent, String name) throws IOException {
        File path = child(parent, name);
        if (!path.exists() && !path.mkdir()) throw new IOException("Preparation directory unavailable");
        if (!path.isDirectory()) throw new IOException("Preparation directory differs");
        return path;
    }
    private static void move(File source, File destination) throws IOException {
        if (destination.exists() || !source.renameTo(destination))
            throw new IOException("Atomic preparation rename refused");
    }
    private static void checkpoint(Progress progress, long started) throws IOException {
        if (System.nanoTime() - started > DEADLINE_NANOS) throw new IOException("Preparation deadline exceeded");
        if (progress.pauseRequested()) throw new Paused();
    }

    public static void verify(File root, List<Row> rows, Progress progress) throws IOException {
        long started = System.nanoTime();
        for (int i = 0; i < rows.size(); i++) {
            checkpoint(progress, started);
            Row row = rows.get(i);
            File path = child(root, row.name);
            if (path.length() != row.bytes || !hash(path).equals(row.sha256))
                throw new IOException("Prepared file verification differs");
            progress.update("verify", i + 1, rows.size());
        }
    }

    public static Map<String, String> install(File selectedRoot, List<Row> rows,
            Source source, Progress progress, Map<String, String> accepted) throws IOException {
        if (rows.isEmpty() || rows.size() > 512 || !selectedRoot.getAbsoluteFile().equals(selectedRoot.getCanonicalFile()))
            throw new IOException("Invalid payload selection");
        File root = selectedRoot.getCanonicalFile();
        if (!root.isDirectory()) throw new IOException("Payload root absent");
        long started = System.nanoTime();
        Map<String, String> drift = new HashMap<>();
        List<Row> pending = new ArrayList<>();
        HashSet<String> names = new HashSet<>();
        long required = 0, total = 0;
        for (int i = 0; i < rows.size(); i++) {
            checkpoint(progress, started);
            Row row = rows.get(i);
            if (!names.add(row.name)) throw new IOException("Duplicate payload target");
            total += row.bytes;
            if (total > 4L * 1024 * 1024 * 1024) throw new IOException("Payload size exceeds profile bound");
            File path = child(root, row.name);
            boolean matches = false;
            if (path.exists()) {
                String actual = hash(path);
                matches = path.length() == row.bytes && actual.equals(row.sha256);
                if (!matches) drift.put(row.name, actual);
            }
            if (!matches) { pending.add(row); required += row.bytes; }
            progress.update("verify", i + 1, rows.size());
        }
        for (Map.Entry<String, String> row : drift.entrySet()) {
            if (accepted == null || !row.getValue().equals(accepted.get(row.getKey())))
                throw new Drift(drift);
        }
        if (source.availableBytes() < required + RESERVE + 16L * 1024 * 1024)
            throw new IOException("Insufficient free storage for preparation and reserve");
        File stage = null, backup = null;
        if (!pending.isEmpty()) {
            String attempt = UUID.randomUUID().toString();
            stage = directory(directory(root.getParentFile(), ".owner-payload-stage"), attempt);
            backup = directory(directory(root.getParentFile(), ".owner-payload-backup"), attempt);
        }
        long completed = total - required;
        progress.update("copy", completed, total);
        byte[] buffer = new byte[65536];
        for (Row row : pending) {
            checkpoint(progress, started);
            File temporary = File.createTempFile("p-" + row.name + ".", ".partial", stage);
            File destination = child(root, row.name);
            MessageDigest sha = digest();
            long written = 0, lastSpaceCheck = 0;
            try (InputStream input = source.open(row.name);
                    FileOutputStream output = new FileOutputStream(temporary)) {
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (written + count > row.bytes) throw new IOException("Packaged payload size differs");
                    if (System.nanoTime() - started > DEADLINE_NANOS) throw new IOException("Preparation deadline exceeded");
                    long now = System.nanoTime();
                    if (now - lastSpaceCheck > 250000000L) {
                        if (source.availableBytes() < RESERVE) throw new IOException("Free storage reserve reached");
                        lastSpaceCheck = now;
                    }
                    output.write(buffer, 0, count);
                    sha.update(buffer, 0, count);
                    written += count;
                    progress.update("copy", completed + written, total);
                }
                if (written != row.bytes || !hex(sha.digest()).equals(row.sha256))
                    throw new IOException("Packaged payload hash differs");
                output.getFD().sync();
            }
            if (destination.exists()) {
                String actual = hash(destination);
                if (!actual.equals(drift.get(row.name))) throw new IOException("Existing payload changed after review");
                move(destination, child(backup, row.name));
            } else if (drift.containsKey(row.name)) {
                throw new IOException("Existing payload disappeared after review");
            }
            move(temporary, destination);
            completed += row.bytes;
        }
        verify(root, rows, progress);
        Map<String, String> result = new HashMap<>();
        for (Row row : rows) result.put(row.name, row.sha256);
        progress.update("ready", total, total);
        return Collections.unmodifiableMap(result);
    }
}
