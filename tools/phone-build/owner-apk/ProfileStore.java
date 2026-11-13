package dev.ror2owner.bootstrap;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Opaque, local-only retention for the existing Android persistence owners.
 * No serializer, PC/cloud import, filesystem export or run-resume protocol.
 * Caller must exclude Unity for the whole operation and gate startup on frozen().
 */
public final class ProfileStore {
    public static final int DATA_SCHEMA = 1;
    public static final int MAX_FILES = 512;
    public static final long MAX_FILE_BYTES = 16L * 1024 * 1024;
    public static final long MAX_BYTES = 64L * 1024 * 1024;
    private static final long RESERVE = 16L * 1024 * 1024;
    private static final String[] ROOTS = {"android-profile-v1", "offline-settings-v1", "offline-run-results-v1"};
    public interface Environment {
        long availableBytes(File directory);
        void syncDirectory(File directory) throws IOException;
        void checkpoint(String stage) throws IOException;
    }
    public static final class Snapshot {
        public final String token;
        public final int schema, files;
        public final long bytes;
        Snapshot(String token, int schema, List<Row> rows) {
            this.token = token; this.schema = schema; files = rows.size();
            long count = 0; for (Row row : rows) count += row.size; bytes = count;
        }
    }
    private static final class Row {
        final String path, hash; final long size;
        Row(String path, long size, String hash) { this.path = path; this.size = size; this.hash = hash; }
    }
    private static final class Manifest {
        final int schema; final List<Row> rows;
        Manifest(int schema, List<Row> rows) { this.schema = schema; this.rows = rows; }
    }
    private final File live, vault;
    private final Environment env;
    public ProfileStore(File liveRoot, File backupRoot, Environment environment) throws IOException {
        File checkedLive = checked(liveRoot), checkedVault = checked(backupRoot);
        if (checkedLive.equals(checkedVault) || under(checkedLive, checkedVault) || under(checkedVault, checkedLive)) throw new IOException("Retention roots overlap");
        live = directory(checkedLive, false); vault = directory(checkedVault, true); env = environment;
    }
    private static boolean under(File child, File parent) { return child.toString().startsWith(parent + File.separator); }
    private static File checked(File value) throws IOException {
        File absolute = value.getAbsoluteFile();
        if (!absolute.equals(absolute.getCanonicalFile())) throw new IOException("Retention symlink/path refused");
        return absolute;
    }
    private static File directory(File value, boolean create) throws IOException {
        value = checked(value);
        if (!value.exists() && create && !value.mkdirs()) throw new IOException("Retention directory unavailable");
        if (!value.isDirectory()) throw new IOException("Retention directory unavailable");
        return checked(value);
    }
    /** Names are derived from AndroidOfflineProfile, AndroidOfflineSettings and
     * IntegratedResultsBoundary. Rejected diagnostics and all other roots excluded. */
    public static boolean allowed(String path) {
        if (path == null) return false;
        if (path.matches("android-profile-v1/profile\\.json(?:\\.backup|\\.pending|\\.backup\\.pending|\\.recovering)?")) return true;
        if (path.matches("offline-settings-v1/preferences\\.json(?:\\.backup|\\.pending)?")) return true;
        return path.matches("offline-run-results-v1/(?:profile\\.json(?:\\.backup|\\.pending)?|run-[0-9a-f]{32}(?:\\.xml|\\.debug\\.json))");
    }
    private File child(File root, String path) throws IOException {
        if (!allowed(path)) throw new IOException("Retention path not allowed");
        File target = checked(new File(root, path));
        if (!under(target, root)) throw new IOException("Retention path escaped");
        return target;
    }
    private List<Row> scan(File root) throws IOException {
        checked(root);
        List<Row> rows = new ArrayList<>(); long total = 0;
        for (String name : ROOTS) {
            File folder = checked(new File(root, name));
            if (!folder.exists()) continue;
            directory(folder, false);
            String[] names = folder.list();
            if (names == null || names.length > 4096) throw new IOException("Retention directory exceeds bound");
            Arrays.sort(names);
            for (String leaf : names) {
                String path = name + "/" + leaf;
                if (!allowed(path)) continue;
                File file = child(root, path);
                if (!file.isFile() || file.length() > MAX_FILE_BYTES) throw new IOException("Retention file exceeds bound");
                long size = file.length(); total += size;
                if (rows.size() >= MAX_FILES || total > MAX_BYTES) throw new IOException("Retention exceeds bound");
                rows.add(new Row(path, size, hash(file, MAX_FILE_BYTES)));
                if (file.length() != size) throw new IOException("Profile changed during snapshot");
            }
        }
        Collections.sort(rows, (a, b) -> a.path.compareTo(b.path));
        return rows;
    }
    private static boolean same(List<Row> first, List<Row> second) {
        if (first.size() != second.size()) return false;
        for (int i = 0; i < first.size(); i++) {
            Row a = first.get(i), b = second.get(i);
            if (!a.path.equals(b.path) || a.size != b.size || !a.hash.equals(b.hash)) return false;
        }
        return true;
    }
    public static final class Status {
        public final String state, token;
        public final int schema;
        Status(String state, String token, int schema) { this.state = state; this.token = token; this.schema = schema; }
    }
    private Status journal() throws IOException {
        File file = checked(new File(vault, "active"));
        if (!file.exists()) return null;
        try (DataInputStream in = new DataInputStream(new ByteArrayInputStream(read(file, 160)))) {
            if (!in.readUTF().equals("local-retention-lease-v1")) throw new IOException("Retention journal invalid");
            String state = in.readUTF(); int schema = in.readInt(); String token = in.readUTF();
            if (!(state.equals("active") || state.equals("released")) || schema <= 0 || !token.matches("[0-9a-f]{64}") || in.read() != -1)
                throw new IOException("Retention journal invalid");
            // A prior rename whose directory sync failed must not unfreeze a
            // launch until the released receipt is known durable on this filesystem.
            if (state.equals("released")) env.syncDirectory(vault);
            return new Status(state, token, schema);
        }
    }
    private void journal(String state, String token, int schema) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (DataOutputStream out = new DataOutputStream(bytes)) {
            out.writeUTF("local-retention-lease-v1"); out.writeUTF(state); out.writeInt(schema); out.writeUTF(token);
        }
        writeAtomic(new File(vault, "active"), bytes.toByteArray());
    }
    public boolean frozen() throws IOException {
        Status lease = journal();
        return (lease != null && lease.state.equals("active")) || checked(new File(vault, "restoring")).exists();
    }
    private String active() throws IOException {
        Status lease = journal(); return lease == null || lease.state.equals("released") ? null : lease.token;
    }
    private void requireActive(String token) throws IOException {
        if (token == null || !token.matches("[0-9a-f]{64}") || !token.equals(active())) throw new IOException("Retention lease differs");
    }
    private static void compatible(int schema, int[] readable) throws IOException {
        if (schema <= 0 || readable == null) throw new IOException("Retention schema unavailable");
        for (int value : readable) if (value == schema) return;
        throw new IOException("Incompatible local profile schema");
    }
    /** Metadata-only proof of a prior verified release. Never reads or replaces
     * live profiles, which may legitimately change after launch was unfrozen. */
    public Status status(String token, int schema, int[] readable) throws IOException {
        compatible(schema, readable);
        Status lease = journal();
        if (lease == null || token == null || !token.equals(lease.token) || schema != lease.schema)
            throw new IOException("Retention journal identity differs");
        if (lease.state.equals("released") && checked(new File(vault, "restoring")).exists())
            throw new IOException("Retention release/recovery state differs");
        return lease;
    }
    private File archive(String token) throws IOException {
        if (token == null || !token.matches("[0-9a-f]{64}")) throw new IOException("Retention token invalid");
        return directory(new File(vault, "snapshot-" + token), false);
    }
    private Manifest manifest(String token, int schema, int[] readable) throws IOException {
        compatible(schema, readable);
        File root = archive(token), path = checked(new File(root, "manifest"));
        byte[] encoded = read(path, 256 * 1024);
        if (!digest(encoded).equals(token)) throw new IOException("Retention manifest digest differs");
        List<Row> rows = new ArrayList<>(); long total = 0;
        try (DataInputStream in = new DataInputStream(new ByteArrayInputStream(encoded))) {
            if (!in.readUTF().equals("android-local-retention-v1") || in.readInt() != schema) throw new IOException("Retention schema differs");
            int count = in.readInt();
            if (count < 0 || count > MAX_FILES) throw new IOException("Retention count exceeds bound");
            String previous = "";
            for (int i = 0; i < count; i++) {
                String name = in.readUTF(); long size = in.readLong(); String hash = in.readUTF();
                if (!allowed(name) || name.compareTo(previous) <= 0 || size < 0 || size > MAX_FILE_BYTES || !hash.matches("[0-9a-f]{64}")) throw new IOException("Retention manifest invalid");
                total += size; if (total > MAX_BYTES) throw new IOException("Retention bytes exceed bound");
                rows.add(new Row(name, size, hash)); previous = name;
            }
            if (in.read() != -1) throw new IOException("Trailing retention manifest data");
        }
        if (!same(rows, scan(root))) throw new IOException("Retention archive bytes differ");
        return new Manifest(schema, rows);
    }
    public Snapshot snapshot(int schema) throws IOException {
        if (schema <= 0) throw new IOException("Retention schema unavailable");
        String prior = active();
        if (prior != null) return verify(prior, schema, new int[] {schema});
        if (frozen()) throw new IOException("Interrupted restore requires recovery");
        List<Row> rows = scan(live);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (DataOutputStream out = new DataOutputStream(bytes)) {
            out.writeUTF("android-local-retention-v1"); out.writeInt(schema); out.writeInt(rows.size());
            for (Row row : rows) { out.writeUTF(row.path); out.writeLong(row.size); out.writeUTF(row.hash); }
        }
        byte[] encoded = bytes.toByteArray(); String token = digest(encoded);
        File complete = checked(new File(vault, "snapshot-" + token));
        if (!complete.exists()) {
            long needed = RESERVE; for (Row row : rows) needed += row.size;
            space(vault, needed);
            File pending = new File(vault, "building");
            if (pending.exists()) removeOwnedTree(pending);
            directory(pending, true);
            for (Row row : rows) {
                File target = child(pending, row.path); directory(target.getParentFile(), true);
                copy(child(live, row.path), target, row); env.checkpoint("snapshot-file");
            }
            write(new File(pending, "manifest"), encoded);
            if (!same(rows, scan(pending)) || !same(rows, scan(live))) throw new IOException("Profile changed during snapshot");
            rename(pending, complete); env.checkpoint("snapshot-published");
        }
        Manifest saved = manifest(token, schema, new int[] {schema});
        if (!same(saved.rows, scan(live))) throw new IOException("Profile changed during snapshot");
        journal("active", token, schema);
        env.checkpoint("snapshot-frozen");
        prune(token);
        return new Snapshot(token, schema, rows);
    }
    public Snapshot verify(String token, int schema, int[] readable) throws IOException {
        status(token, schema, readable);
        Manifest saved = manifest(token, schema, readable);
        if (checked(new File(vault, "restoring")).exists()) throw new IOException("Interrupted restore requires recovery");
        if (!same(saved.rows, scan(live))) throw new IOException("Live profile/settings differ from backup");
        return new Snapshot(token, schema, saved.rows);
    }
    public Snapshot restore(String token, int schema, int[] readable) throws IOException {
        requireActive(token);
        Manifest saved = manifest(token, schema, readable); // Validate ALL bytes before touching live data.
        long needed = RESERVE; for (Row row : saved.rows) needed += row.size;
        space(live, needed);
        File marker = checked(new File(vault, "restoring"));
        if (marker.exists() && !new String(read(marker, 64), StandardCharsets.US_ASCII).equals(token)) throw new IOException("Restore journal differs");
        writeAtomic(marker, token.getBytes(StandardCharsets.US_ASCII));
        env.checkpoint("restore-journal");
        File source = archive(token);
        Set<String> keep = new HashSet<>();
        // A durable lease excludes the game from observing this multi-file transaction.
        // Replaying every verified row is idempotent after interruption at any rename.
        for (Row row : saved.rows) {
            keep.add(row.path); File target = child(live, row.path); directory(target.getParentFile(), true);
            File staged = checked(new File(target.getParentFile(), target.getName() + ".owner-restore"));
            copy(child(source, row.path), staged, row); rename(staged, target);
            env.checkpoint("restore-file");
        }
        for (Row row : scan(live)) if (!keep.contains(row.path)) {
            File target = child(live, row.path);
            if (!target.delete()) throw new IOException("Stale retained file could not be removed");
            env.syncDirectory(target.getParentFile()); env.checkpoint("restore-remove");
        }
        if (!same(saved.rows, scan(live))) throw new IOException("Restored profile verification failed");
        if (!marker.delete()) throw new IOException("Restore journal could not be completed");
        env.syncDirectory(vault); env.checkpoint("restore-verified");
        return verify(token, schema, readable);
    }
    public void release(String token, int schema, int[] readable) throws IOException {
        if (status(token, schema, readable).state.equals("released")) return;
        verify(token, schema, readable);
        env.checkpoint("release-verified");
        // One atomic journal transition is both the launch-unfreeze and the
        // bounded historical proof. No receipt/delete split permits stale restore.
        journal("released", token, schema);
        env.checkpoint("release-recorded");
    }
    private void space(File root, long needed) throws IOException {
        if (env.availableBytes(root) < needed) throw new IOException("Insufficient space for verified local retention");
    }
    private void rename(File source, File target) throws IOException {
        checked(source); checked(target);
        if (target.exists() && !target.isFile()) throw new IOException("Retention replacement is not a file");
        if (!source.renameTo(target)) throw new IOException("Atomic retention rename failed");
        env.syncDirectory(target.getParentFile());
    }
    private void writeAtomic(File target, byte[] bytes) throws IOException {
        File pending = checked(new File(target.getParentFile(), target.getName() + ".pending"));
        write(pending, bytes); rename(pending, target);
    }
    private void write(File target, byte[] bytes) throws IOException {
        checked(target);
        if (target.exists() && !target.isFile()) throw new IOException("Retention metadata target invalid");
        try (FileOutputStream out = new FileOutputStream(target)) { out.write(bytes); out.getFD().sync(); }
        env.syncDirectory(target.getParentFile());
    }
    private void copy(File source, File target, Row expected) throws IOException {
        checked(source); checked(target);
        if (!source.isFile() || (target.exists() && !target.isFile())) throw new IOException("Retention copy requires regular files");
        long count = 0;
        try (InputStream in = new FileInputStream(source); FileOutputStream out = new FileOutputStream(target)) {
            byte[] buffer = new byte[8192]; int length;
            while ((length = in.read(buffer)) != -1) {
                count += length; if (count > expected.size || count > MAX_FILE_BYTES) throw new IOException("Retention source changed");
                out.write(buffer, 0, length);
            }
            out.getFD().sync();
        }
        if (count != expected.size || !hash(target, MAX_FILE_BYTES).equals(expected.hash)) throw new IOException("Retention copy digest differs");
        env.syncDirectory(target.getParentFile());
    }
    private static byte[] read(File file, long maximum) throws IOException {
        checked(file);
        if (!file.isFile() || file.length() > maximum) throw new IOException("Retention metadata exceeds bound");
        try (InputStream in = new FileInputStream(file); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int count;
            while ((count = in.read(buffer)) != -1) { if (out.size() + count > maximum) throw new IOException("Retention metadata exceeds bound"); out.write(buffer, 0, count); }
            return out.toByteArray();
        }
    }
    public static String digest(byte[] bytes) throws IOException {
        try { return hex(MessageDigest.getInstance("SHA-256").digest(bytes)); } catch (Exception error) { throw new IOException("SHA-256 unavailable", error); }
    }
    private static String hash(File path, long maximum) throws IOException {
        checked(path);
        try (InputStream in = new FileInputStream(path)) {
            MessageDigest hash = MessageDigest.getInstance("SHA-256"); byte[] buffer = new byte[8192]; int count; long total = 0;
            while ((count = in.read(buffer)) != -1) { total += count; if (total > maximum) throw new IOException("Retention file exceeds bound"); hash.update(buffer, 0, count); }
            return hex(hash.digest());
        } catch (java.security.NoSuchAlgorithmException error) { throw new IOException("SHA-256 unavailable", error); }
    }
    /** Pin the present signer, not a caller-supplied hash or historical rotation certificate. */
    public static boolean authorized(String expectedPackage, String expectedCertificate, String[] packages, byte[][] certificates) throws IOException {
        return expectedPackage != null && expectedCertificate != null && expectedCertificate.matches("[0-9a-f]{64}") &&
            packages != null && packages.length == 1 && expectedPackage.equals(packages[0]) &&
            certificates != null && certificates.length == 1 && certificates[0] != null &&
            expectedCertificate.equals(digest(certificates[0]));
    }
    private static String hex(byte[] bytes) { StringBuilder out = new StringBuilder(); for (byte b : bytes) out.append(String.format(Locale.ROOT, "%02x", b & 255)); return out.toString(); }
    private void removeOwnedTree(File root) throws IOException {
        removeOwnedTree(root, 0);
    }
    private void removeOwnedTree(File root, int depth) throws IOException {
        if (depth > 1) throw new IOException("Retention cleanup depth exceeds bound");
        directory(root, false);
        File[] files = root.listFiles(); if (files == null || files.length > 4096) throw new IOException("Retention cleanup exceeds bound");
        for (File child : files) {
            checked(child);
            if (child.isDirectory()) removeOwnedTree(child, depth + 1);
            else if (!child.isFile() || !child.delete()) throw new IOException("Retention cleanup failed");
        }
        if (!root.delete()) throw new IOException("Retention cleanup failed");
        env.syncDirectory(root.getParentFile());
    }
    private void prune(String current) throws IOException {
        File[] children = vault.listFiles(); if (children == null || children.length > 32) throw new IOException("Retention vault exceeds bound");
        List<File> previous = new ArrayList<>();
        for (File child : children) if (child.getName().matches("snapshot-[0-9a-f]{64}") && !child.getName().equals("snapshot-" + current)) previous.add(checked(child));
        Collections.sort(previous, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));
        // Keep one previous archive as well as the current pre-update snapshot.
        for (int i = 1; i < previous.size(); i++) removeOwnedTree(previous.get(i));
    }
}
