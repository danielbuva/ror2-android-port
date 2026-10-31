package dev.ror2lab.phonebuildhostfixture;

import java.io.*;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.text.Normalizer;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Local, Android-free streaming import. No networking, archive extraction or source writes. */
public final class OwnerInputImport {
    /** Directory durability on Android API 24+, with a host-JVM fixture path.
     * Reflection keeps this streaming owner Android-free without linking the
     * API-26 java.nio.file classes on an API-24 device.
     */
    public static void syncDirectory(File directory) throws Exception {
        Class<?> os;
        try { os = Class.forName("android.system.Os"); }
        catch (ClassNotFoundException host) {
            Class<?> path = Class.forName("java.nio.file.Path");
            Class<?> option = Class.forName("java.nio.file.OpenOption");
            Object options = java.lang.reflect.Array.newInstance(option, 1);
            Object read = Class.forName("java.nio.file.StandardOpenOption").getField("READ").get(null);
            java.lang.reflect.Array.set(options, 0, read);
            Object target = File.class.getMethod("toPath").invoke(directory);
            try (java.nio.channels.FileChannel channel = (java.nio.channels.FileChannel)
                    java.nio.channels.FileChannel.class.getMethod("open", path, options.getClass()).invoke(null, target, options)) {
                channel.force(true);
            }
            return;
        }
        Class<?> constants = Class.forName("android.system.OsConstants");
        int flags = constants.getField("O_RDONLY").getInt(null) | constants.getField("O_DIRECTORY").getInt(null);
        FileDescriptor descriptor = (FileDescriptor) os.getMethod("open", String.class, int.class, int.class).invoke(null, directory.getPath(), flags, 0);
        try { os.getMethod("fsync", FileDescriptor.class).invoke(null, descriptor); }
        finally { os.getMethod("close", FileDescriptor.class).invoke(null, descriptor); }
    }
    public static void durableDirectory(File directory) throws Exception {
        if (!directory.getAbsoluteFile().equals(directory.getCanonicalFile())) throw new IOException("Private directory contains links");
        if (!directory.isDirectory()) {
            File parent = directory.getAbsoluteFile().getParentFile();
            durableDirectory(parent);
            if (!directory.mkdir() && !directory.isDirectory()) throw new IOException("Private directory unavailable");
            syncDirectory(parent);
        }
    }
    /** Both paths are private and on the same filesystem; never copy/delete fallback. */
    public static void publish(File temporary, File destination) throws Exception {
        if (!temporary.getAbsoluteFile().equals(temporary.getCanonicalFile()) ||
                !destination.getAbsoluteFile().equals(destination.getCanonicalFile())) throw new IOException("Private atomic file contains links");
        if (!temporary.renameTo(destination)) throw new IOException("Could not publish private file");
        syncDirectory(destination.getParentFile());
        if (!temporary.getParentFile().equals(destination.getParentFile())) syncDirectory(temporary.getParentFile());
    }
    public interface AtomicWriter { void write(FileOutputStream output) throws Exception; }
    /** Caller serializes this target. Interrupted .writing bytes are overwritten, never trusted. */
    public static void writeAtomic(File file, AtomicWriter writer) throws Exception {
        File parent = file.getParentFile(); durableDirectory(parent);
        File staged = new File(parent, file.getName() + ".writing");
        if (!staged.getAbsoluteFile().equals(staged.getCanonicalFile()) ||
                !file.getAbsoluteFile().equals(file.getCanonicalFile())) throw new IOException("Private atomic file contains links");
        try {
            try (FileOutputStream output = new FileOutputStream(staged)) { writer.write(output); output.getFD().sync(); }
            publish(staged, file);
        } finally { staged.delete(); }
    }
    public static final long MARGIN = 2L * 1024 * 1024 * 1024;
    public static final class Required {
        public final String path, sha256;
        public final long bytes;
        public Required(String path, long bytes, String sha256) throws IOException {
            safePath(path);
            if (bytes < 0 || sha256 == null || !sha256.matches("[0-9a-f]{64}")) throw new IOException("Invalid required-input identity");
            this.path = path; this.bytes = bytes; this.sha256 = sha256;
        }
    }
    public interface Source {
        Map<String, Long> inventory() throws Exception;
        InputStream open(String path) throws Exception;
    }
    public interface Observer {
        /** May wait while paused; cancellation throws InterruptedIOException. */
        void checkpoint() throws Exception;
        void progress(String path, long completed, long total) throws Exception;
    }
    public static final class Result {
        public final List<String> extra = new ArrayList<>();
        public long bytes;
    }
    public static final class Version {
        public final String name, manifestSha256;
        public final List<Required> files;
        public final boolean supported;
        public Version(String name, String manifestSha256, List<Required> files, boolean supported) throws IOException {
            if (name == null || name.isEmpty() || name.length() > 128 || !manifestSha256.matches("[0-9a-f]{64}") || files.isEmpty() || files.size() > 100000)
                throw new IOException("Invalid reviewed version inventory");
            List<String> names = new ArrayList<>(); for (Required row : files) names.add(row.path); validatePaths(names);
            this.name = name; this.manifestSha256 = manifestSha256; this.files = files; this.supported = supported;
        }
    }
    public static final class VersionRefused extends IOException {
        public final String found;
        public final List<String> supported;
        VersionRefused(String found, List<String> supported) {
            super("Found version: " + found + ". Supported versions: " + supported + ". Input refused. Select a complete, unmodified supported PC installation or ask the release maintainer to review this version. Filenames and labels are not proof.");
            this.found = found; this.supported = supported;
        }
    }
    private static Map<String, Set<Long>> wanted(List<Version> versions) throws IOException {
        if (versions.isEmpty() || versions.size() > 16) throw new IOException("Bounded reviewed version catalog required");
        Map<String, Set<Long>> result = new TreeMap<>(); Set<String> labels = new HashSet<>(); boolean supported = false;
        for (Version version : versions) {
            if (!labels.add(version.name)) throw new IOException("Duplicate reviewed version label"); supported |= version.supported;
            for (Required row : version.files) { Set<Long> sizes = result.get(row.path); if (sizes == null) { sizes = new HashSet<>(); result.put(row.path, sizes); } sizes.add(row.bytes); }
        }
        if (!supported || result.size() > 100000) throw new IOException("Supported bounded inventory required");
        return result;
    }
    private static Version select(List<Version> versions, Map<String, Required> observed) throws IOException {
        List<Version> matched = new ArrayList<>(); List<String> supported = new ArrayList<>();
        for (Version version : versions) {
            if (version.supported) supported.add(version.name); boolean equal = true;
            for (Required row : version.files) { Required found = observed.get(row.path); if (found == null || row.bytes != found.bytes || !row.sha256.equals(found.sha256)) { equal = false; break; } }
            if (equal) matched.add(version);
        }
        Collections.sort(supported);
        if (matched.size() == 1 && matched.get(0).supported) return matched.get(0);
        throw new VersionRefused(matched.isEmpty() ? "unknown (no complete reviewed fingerprint matched)" : matched.size() > 1 ? "ambiguous (multiple complete fingerprints matched)" : matched.get(0).name, supported);
    }
    private static Required fingerprint(String name, InputStream input, long maximum, Observer observer) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256"); byte[] buffer = new byte[65536]; long size = 0;
        while (true) { observer.checkpoint(); int limit = size == maximum ? 1 : (int)Math.min(buffer.length, maximum - size); int count = input.read(buffer, 0, limit); if (count < 0) break;
            if (count > maximum - size) return null; size += count; hash.update(buffer, 0, count); }
        return new Required(name, size, hex(hash.digest()));
    }
    public static Version identifyTree(Source source, List<Version> versions, Observer observer) throws Exception {
        Map<String, Set<Long>> wanted = wanted(versions); Map<String, Long> inventory = source.inventory(); validatePaths(inventory.keySet());
        Map<String, Required> observed = new HashMap<>();
        for (Map.Entry<String, Set<Long>> row : wanted.entrySet()) { observer.checkpoint(); Long size = inventory.get(row.getKey());
            if (size != null && (size < 0 || row.getValue().contains(size))) try (InputStream input = source.open(row.getKey())) {
                if (input == null) throw new IOException("Selected input unavailable"); Required value = fingerprint(row.getKey(), input, Collections.max(row.getValue()), observer); if (value != null) observed.put(row.getKey(), value);
            }
            observer.progress("Checking version: " + row.getKey(), 0, 0);
        }
        return select(versions, observed);
    }
    private static final class ZipNames {
        final Set<String> seen = new HashSet<>(), files = new HashSet<>(), directories = new HashSet<>();
        final Map<String, String> nodes = new HashMap<>();
        String accept(ZipEntry entry) throws IOException {
            String name = entry.getName(), normalized = entry.isDirectory() && name.endsWith("/") ? name.substring(0, name.length()-1) : name;
            safePath(normalized); if (!seen.add(name) || seen.size() > 100000) throw new IOException("Duplicate or excessive ZIP entries");
            String key = pathKey(normalized), node = "";
            for (String part : normalized.split("/")) { node = node.isEmpty() ? part : node + "/" + part;
                String old = nodes.put(pathKey(node), node); if (old != null && !old.equals(node)) throw new IOException("Case-aliased ZIP entry");
                if (!node.equals(normalized)) { if (files.contains(pathKey(node))) throw new IOException("ZIP file/directory collision"); directories.add(pathKey(node)); }
            }
            if (entry.isDirectory()) { if (files.contains(key)) throw new IOException("ZIP file/directory collision"); directories.add(key); }
            else if (!files.add(key) || directories.contains(key)) throw new IOException("Duplicate or file/directory ZIP entry");
            return name;
        }
    }
    public static Version identifyZip(InputStream source, List<Version> versions, Observer observer) throws Exception {
        Map<String, Set<Long>> wanted = wanted(versions); Map<String, Required> observed = new HashMap<>();
        long budget = MARGIN; for (Set<Long> sizes : wanted.values()) budget = Math.addExact(budget, Collections.max(sizes));
        long consumed = 0; ZipNames names = new ZipNames(); byte[] buffer = new byte[65536];
        try (ZipInputStream zip = new ZipInputStream(source)) { ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) { observer.checkpoint(); String name = names.accept(entry);
                if (entry.isDirectory()) { if (zip.read() != -1) throw new IOException("ZIP directory contains unexpected data"); zip.closeEntry(); continue; }
                Set<Long> sizes = wanted.get(name); long count = 0; MessageDigest hash = sizes == null ? null : MessageDigest.getInstance("SHA-256"); int length;
                while ((length = zip.read(buffer)) != -1) { observer.checkpoint(); consumed = Math.addExact(consumed, length); count = Math.addExact(count, length);
                    if (consumed > budget) throw new IOException("ZIP data exceeds safe version-check budget; choose the game folder instead");
                    if (hash != null) hash.update(buffer, 0, length);
                }
                if (sizes != null && sizes.contains(count)) observed.put(name, new Required(name, count, hex(hash.digest())));
                zip.closeEntry(); observer.progress("Checking version: " + name, 0, 0);
            }
        }
        return select(versions, observed);
    }

    private final File root;
    private final LinkedHashMap<String, Required> required = new LinkedHashMap<>();
    private final long total, workspace;
    private final Observer observer;
    private long completed, remainingBytes;
    public OwnerInputImport(File root, List<Required> manifest, long workspace, Observer observer) throws Exception {
        if (workspace < 0 || manifest.isEmpty()) throw new IOException("A verified required-input manifest is required");
        this.root = root.getCanonicalFile(); this.workspace = workspace; this.observer = observer;
        if (!root.getAbsoluteFile().equals(this.root)) throw new IOException("Import root must not contain links");
        long size = 0;
        for (Required row : manifest) {
            if (required.put(row.path, row) != null) throw new IOException("Duplicate required input: " + row.path);
            size = Math.addExact(size, row.bytes);
        }
        validatePaths(required.keySet());
        for (String path : required.keySet()) {
            for (int slash = path.indexOf('/'); slash >= 0; slash = path.indexOf('/', slash + 1))
                if (required.containsKey(path.substring(0, slash))) throw new IOException("Input file/directory collision");
        }
        total = size;
    }
    public static void safePath(String path) throws IOException {
        if (path == null || path.isEmpty() || path.startsWith("/") || path.contains("\\") || path.contains(":") || path.getBytes(StandardCharsets.UTF_8).length > 4096 || !Normalizer.isNormalized(path, Normalizer.Form.NFC))
            throw new IOException("Unsafe input path");
        for (int i = 0; i < path.length(); i++) if (path.charAt(i) < 32 || path.charAt(i) == 127) throw new IOException("Unsafe input path");
        for (String part : path.split("/", -1)) if (part.isEmpty() || part.equals(".") || part.equals("..")) throw new IOException("Unsafe input path");
    }
    private static String pathKey(String path) { return path.toUpperCase(Locale.ROOT).toLowerCase(Locale.ROOT); }
    private static void validatePaths(Collection<String> paths) throws IOException {
        Set<String> files = new HashSet<>(); Map<String, String> nodes = new HashMap<>();
        for (String path : paths) {
            safePath(path); if (!files.add(pathKey(path))) throw new IOException("Duplicate or case-aliased input path");
            String node = "";
            for (String part : path.split("/")) {
                node = node.isEmpty() ? part : node + "/" + part;
                String old = nodes.put(pathKey(node), node);
                if (old != null && !old.equals(node)) throw new IOException("Case-aliased input directory");
            }
        }
        for (String file : files) for (int slash = file.indexOf('/'); slash >= 0; slash = file.indexOf('/', slash + 1))
            if (files.contains(file.substring(0, slash))) throw new IOException("Input file/directory collision");
    }
    private File target(String path) throws Exception {
        File file = new File(new File(root, "files"), path);
        if (!file.getCanonicalFile().equals(file.getAbsoluteFile()) || !file.getCanonicalPath().startsWith(root.getPath() + File.separator))
            throw new IOException("Private import path contains links");
        return file;
    }
    public static String digest(File file) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(file)) {
            byte[] data = new byte[65536]; int count;
            while ((count = input.read(data)) != -1) hash.update(data, 0, count);
        }
        return hex(hash.digest());
    }
    private static String hex(byte[] digest) {
        StringBuilder value = new StringBuilder();
        for (byte b : digest) value.append(String.format(Locale.ROOT, "%02x", b & 255));
        return value.toString();
    }
    private boolean reusable(Required row) throws Exception {
        File file = target(row.path);
        if (!file.isFile() || file.length() != row.bytes) return false;
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new FileInputStream(file)) {
            byte[] data = new byte[65536]; int count;
            while ((count = input.read(data)) != -1) { observer.checkpoint(); hash.update(data, 0, count); }
        }
        return hex(hash.digest()).equals(row.sha256);
    }
    private void capacity() throws Exception {
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Private import directory unavailable");
        // Remove only deterministic incomplete files owned by this exact manifest.
        File staging = new File(root, "native-staging");
        if (!staging.getCanonicalFile().equals(staging.getAbsoluteFile())) throw new IOException("Private staging contains links");
        for (Required row : required.values()) {
            File partial = new File(staging, hex(MessageDigest.getInstance("SHA-256").digest(row.path.getBytes(StandardCharsets.UTF_8))) + ".part");
            if (!partial.getCanonicalFile().equals(partial.getAbsoluteFile()) || (partial.exists() && !partial.isFile())) throw new IOException("Private partial input is not a regular file");
            if (partial.exists() && !partial.delete()) throw new IOException("Could not discard interrupted partial input");
        }
        long remaining = 0;
        for (Required row : required.values()) { observer.checkpoint(); if (!reusable(row)) remaining = Math.addExact(remaining, row.bytes); }
        remainingBytes = remaining;
        ensureSpace(remaining);
    }
    private void ensureSpace(long remaining) throws Exception {
        // Same estimate as game_import.py: remaining + workspace + 2 GiB + ceil(remaining * 5%).
        long margin = Math.addExact(MARGIN, remaining / 20 + (remaining % 20 == 0 ? 0 : 1));
        long needed = Math.addExact(Math.addExact(remaining, workspace), margin);
        if (root.getUsableSpace() < needed) throw new IOException("Not enough private storage: need " + needed + " bytes including reconstruction and safety margin");
    }
    private void copy(Required row, InputStream input) throws Exception {
        observer.checkpoint();
        File file = target(row.path), temporary = new File(new File(root, "native-staging"), hex(MessageDigest.getInstance("SHA-256").digest(row.path.getBytes(StandardCharsets.UTF_8))) + ".part");
        durableDirectory(temporary.getParentFile());
        boolean reuse = reusable(row);
        ensureSpace(remainingBytes);
        if (!temporary.getCanonicalFile().equals(temporary.getAbsoluteFile())) throw new IOException("Private temporary input contains links");
        durableDirectory(file.getParentFile());
        MessageDigest hash = MessageDigest.getInstance("SHA-256"); long copied = 0;
        try (FileOutputStream output = reuse ? null : new FileOutputStream(temporary)) {
            byte[] bytes = new byte[65536]; int count;
            while ((count = input.read(bytes)) != -1) {
                observer.checkpoint();
                if (count > row.bytes - copied) throw new IOException("Version mismatch (size): " + row.path);
                if (output != null) output.write(bytes, 0, count); hash.update(bytes, 0, count); copied += count;
                observer.progress(row.path, completed + copied, total);
            }
            if (copied != row.bytes || !hex(hash.digest()).equals(row.sha256)) throw new IOException("Version mismatch (size/hash): " + row.path);
            if (output != null) output.getFD().sync();
        } catch (Exception error) { temporary.delete(); throw error; }
        if (!reuse) {
            try { publish(temporary, file); }
            finally { temporary.delete(); }
        }
        if (!reuse) remainingBytes -= copied;
        completed += copied; observer.progress(row.path, completed, total);
    }
    public Result tree(Source source) throws Exception {
        Map<String, Long> inventory = source.inventory(); validatePaths(inventory.keySet()); Result result = new Result(); List<String> missing = new ArrayList<>();
        for (String path : inventory.keySet()) { safePath(path); if (!required.containsKey(path)) result.extra.add(path); }
        for (Required row : required.values()) {
            Long size = inventory.get(row.path);
            if (size == null) missing.add(row.path);
            else if (size >= 0 && size != row.bytes) throw new IOException("Version mismatch (size): " + row.path);
        }
        if (!missing.isEmpty()) throw new IOException("Missing required inputs: " + missing);
        capacity();
        for (Required row : required.values()) {
            observer.checkpoint();
            if (reusable(row)) { completed += row.bytes; observer.progress(row.path, completed, total); }
            else try (InputStream input = source.open(row.path)) { if (input == null) throw new IOException("Selected input unavailable: " + row.path); copy(row, input); }
        }
        result.bytes = completed; return result;
    }
    /** Stream a provider ZIP once, directly to verified private files (no archive-sized copy). */
    public Result zip(InputStream source) throws Exception {
        capacity(); Result result = new Result(); Set<String> seen = new HashSet<>();
        long skipped = 0; final long maximumSkipped = Math.max(total, MARGIN);
        ZipNames names = new ZipNames();
        try (ZipInputStream zip = new ZipInputStream(source)) {
            ZipEntry entry; byte[] scratch = new byte[65536];
            while ((entry = zip.getNextEntry()) != null) {
                observer.checkpoint(); String name = names.accept(entry);
                if (entry.isDirectory()) {
                    if (zip.read() != -1) throw new IOException("ZIP directory contains unexpected data");
                    zip.closeEntry(); continue;
                }
                seen.add(name);
                Required row = required.get(name);
                if (row != null) {
                    if (entry.getSize() >= 0 && entry.getSize() != row.bytes) throw new IOException("Version mismatch (size): " + name);
                    // Re-read every ZIP member to verify its provider bytes and CRC, even on resume.
                    copy(row, zip);
                } else {
                    result.extra.add(name); int count;
                    while ((count = zip.read(scratch)) != -1) { observer.checkpoint(); skipped = Math.addExact(skipped, count); if (skipped > maximumSkipped) throw new IOException("ZIP extra data exceeds safe import budget; choose the game folder instead"); }
                }
                zip.closeEntry();
            }
        }
        List<String> missing = new ArrayList<>(); for (String path : required.keySet()) if (!seen.contains(path)) missing.add(path);
        if (!missing.isEmpty()) throw new IOException("Missing required inputs: " + missing);
        result.bytes = completed; return result;
    }
}
