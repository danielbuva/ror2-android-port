package dev.ror2owner.bootstrap;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** All data is independently authored; no game or Android runtime is required. */
public final class PayloadStoreHarness {
    private static int checks;
    private static void check(boolean value, String reason) {
        checks++;
        if (!value) throw new AssertionError(reason);
    }
    private static String hash(byte[] value) throws Exception {
        StringBuilder result = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(value)) result.append(String.format("%02x", b & 255));
        return result.toString();
    }
    private static File root(File base, String name) throws IOException {
        File parent = new File(base, name);
        check(parent.mkdir(), "fixture parent");
        File payload = new File(parent, "payload");
        check(payload.mkdir(), "fixture payload");
        return payload.getCanonicalFile();
    }
    private static final class Source implements PayloadStore.Source {
        final Map<String, byte[]> files = new HashMap<>();
        int opens;
        long available = Long.MAX_VALUE / 4;
        Runnable beforeOpen;
        public InputStream open(String name) throws IOException {
            opens++;
            if (beforeOpen != null) beforeOpen.run();
            if (!files.containsKey(name)) throw new IOException("missing authored fixture");
            return new ByteArrayInputStream(files.get(name));
        }
        public long availableBytes() { return available; }
    }
    private static class Progress implements PayloadStore.Progress {
        boolean pause;
        long pauseAfter = Long.MAX_VALUE;
        public void update(String phase, long done, long total) {
            if (phase.equals("copy") && done >= pauseAfter) pause = true;
        }
        public boolean pauseRequested() { return pause; }
    }

    public static void main(String[] args) throws Exception {
        File base = new File(args[0]).getCanonicalFile();
        byte[] content = new byte[131103];
        for (int i = 0; i < content.length; i++) content[i] = (byte) ((i * 37 + 11) % 251);
        PayloadStore.Row row = new PayloadStore.Row("authored.bundle", content.length, hash(content));
        List<PayloadStore.Row> rows = Collections.singletonList(row);
        Source source = new Source();
        source.files.put(row.name, content);
        File fresh = root(base, "fresh");
        File save = new File(fresh.getParentFile(), "profile.json");
        Files.write(save.toPath(), new byte[]{4, 2});
        Map<String, String> receipt = PayloadStore.install(fresh, rows, source, new Progress(), null);
        check(Arrays.equals(Files.readAllBytes(new File(fresh, row.name).toPath()), content), "streamed bytes");
        check(receipt.get(row.name).equals(hash(content)), "verified receipt");
        check(Arrays.equals(Files.readAllBytes(save.toPath()), new byte[]{4, 2}), "save preserved");
        int previousOpens = source.opens;
        PayloadStore.install(fresh, rows, source, new Progress(), null);
        check(source.opens == previousOpens, "verified files reused without source recopy");

        File changed = root(base, "changed");
        byte[] old = new byte[]{9, 8, 7};
        File destination = new File(changed, row.name);
        Files.write(destination.toPath(), old);
        Map<String, String> reviewed = null;
        try { PayloadStore.install(changed, rows, source, new Progress(), null); throw new AssertionError("unknown drift accepted"); }
        catch (PayloadStore.Drift drift) { reviewed = drift.observed; }
        check(Arrays.equals(Files.readAllBytes(destination.toPath()), old), "unreviewed old file preserved");
        check(reviewed.get(row.name).equals(hash(old)), "exact review hash");
        PayloadStore.install(changed, rows, source, new Progress(), reviewed);
        check(Arrays.equals(Files.readAllBytes(destination.toPath()), content), "reviewed update");
        File backups = new File(changed.getParentFile(), ".owner-payload-backup");
        File[] attempts = backups.listFiles();
        check(attempts != null && attempts.length == 1, "one retained backup attempt");
        check(Arrays.equals(Files.readAllBytes(new File(attempts[0], row.name).toPath()), old), "exact old backup retained");

        File corrupt = root(base, "corrupt");
        File prior = new File(corrupt, row.name);
        Files.write(prior.toPath(), old);
        Source damaged = new Source();
        damaged.files.put(row.name, new byte[]{1, 2});
        try { PayloadStore.install(corrupt, rows, damaged, new Progress(), Collections.singletonMap(row.name, hash(old))); throw new AssertionError("damaged source accepted"); }
        catch (IOException expected) { check(Arrays.equals(Files.readAllBytes(prior.toPath()), old), "bad source never publishes over old data"); }
        File[] failed = new File(corrupt.getParentFile(), ".owner-payload-stage").listFiles();
        check(failed != null && failed.length == 1 && failed[0].listFiles().length == 1, "failed partial retained");

        File race = root(base, "race");
        File racing = new File(race, row.name);
        Files.write(racing.toPath(), old);
        Source raced = new Source();
        raced.files.put(row.name, content);
        raced.beforeOpen = () -> {
            try { Files.write(racing.toPath(), new byte[]{5}); }
            catch (IOException failure) { throw new RuntimeException(failure); }
        };
        try { PayloadStore.install(race, rows, raced, new Progress(), Collections.singletonMap(row.name, hash(old))); throw new AssertionError("changed review accepted"); }
        catch (IOException expected) { check(Arrays.equals(Files.readAllBytes(racing.toPath()), new byte[]{5}), "post-review drift never overwritten"); }

        File space = root(base, "space");
        Source full = new Source();
        full.files.put(row.name, content);
        full.available = 0;
        try { PayloadStore.install(space, rows, full, new Progress(), null); throw new AssertionError("zero space accepted for copy"); }
        catch (IOException expected) { check(full.opens == 0 && space.listFiles().length == 0, "capacity refused before source/output copy"); }

        File paused = root(base, "pause");
        byte[] secondData = new byte[]{3, 1, 4};
        PayloadStore.Row second = new PayloadStore.Row("second.bundle", secondData.length, hash(secondData));
        Source resumable = new Source();
        resumable.files.put(row.name, content);
        resumable.files.put(second.name, secondData);
        Progress control = new Progress();
        control.pauseAfter = row.bytes;
        try { PayloadStore.install(paused, Arrays.asList(row, second), resumable, control, null); throw new AssertionError("pause ignored"); }
        catch (PayloadStore.Paused expected) {
            check(new File(paused, row.name).isFile(), "pause retains complete first file");
            check(!new File(paused, second.name).exists(), "pause occurs before second file");
        }
        int openedAtPause = resumable.opens;
        PayloadStore.install(paused, Arrays.asList(row, second), resumable, new Progress(), null);
        check(resumable.opens == openedAtPause + 1, "resume reuses completed file");

        File outside = new File(base, "outside");
        check(outside.mkdir(), "outside fixture");
        File sentinel = new File(outside, "sentinel");
        Files.write(sentinel.toPath(), old);
        File linked = root(base, "symlink");
        Files.createSymbolicLink(new File(linked, row.name).toPath(), sentinel.toPath());
        try { PayloadStore.install(linked, rows, source, new Progress(), null); throw new AssertionError("symlink accepted"); }
        catch (IOException expected) { check(Arrays.equals(Files.readAllBytes(sentinel.toPath()), old), "external sentinel preserved"); }
        for (String name : Arrays.asList("..", ".", "../profile.json", "/absolute", "a/b")) {
            try { new PayloadStore.Row(name, 1, hash(old)); throw new AssertionError("unsafe row accepted"); }
            catch (IllegalArgumentException expected) { checks++; }
        }
        File duplicate = root(base, "duplicate");
        try { PayloadStore.install(duplicate, Arrays.asList(row, row), source, new Progress(), null); throw new AssertionError("duplicate target accepted"); }
        catch (IOException expected) { check(duplicate.listFiles().length == 0, "duplicate targets refuse before writes"); }

        // A completed dataset needs no payload allocation. Low remaining space
        // must not force an unnecessary rewrite or invalidate verified content.
        source.available = 0;
        PayloadStore.install(fresh, rows, source, new Progress(), null);
        check(source.opens == previousOpens + 1, "reuse remains read-only at low space");
        System.out.println("{\"success\":true,\"checks\":" + checks + "}");
    }
}
