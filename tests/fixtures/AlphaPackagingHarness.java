package dev.ror2lab.phonebuildhostfixture;

import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

/** Authored bytes only. Executes the real importer on both JVM and Android ART. */
public final class AlphaPackagingHarness {
    private static final String MEMBER = "authored/content.bin";
    private static final String MANIFEST = repeat('a', 64);
    private static final int SIZE = 196625;

    private static String repeat(char value, int count) {
        char[] result = new char[count]; Arrays.fill(result, value); return new String(result);
    }
    private static void require(boolean condition) throws IOException {
        if (!condition) throw new IOException("synthetic-contract-failed");
    }
    private static void pass(String name) { System.out.println("PASS " + name); }
    private static void write(File path, byte[] bytes) throws Exception {
        require(path.getParentFile().isDirectory() || path.getParentFile().mkdirs());
        try (FileOutputStream output = new FileOutputStream(path)) { output.write(bytes); output.getFD().sync(); }
    }
    private static final class Tree implements OwnerInputImport.Source {
        final File root;
        final long reportedSize;
        Tree(File root, long reportedSize) { this.root = root; this.reportedSize = reportedSize; }
        public Map<String, Long> inventory() {
            Map<String, Long> result = new TreeMap<>(); result.put(MEMBER, reportedSize); return result;
        }
        public InputStream open(String path) throws Exception { require(MEMBER.equals(path)); return new FileInputStream(new File(root, path)); }
    }
    private static final class Progress implements OwnerInputImport.Observer {
        final boolean cancel;
        long last, total;
        int indeterminate, copying;
        boolean cancelled;
        Progress(boolean cancel) { this.cancel = cancel; }
        public void checkpoint() throws Exception {
            if (cancel && last > 0) { cancelled = true; throw new InterruptedIOException("synthetic-cancel"); }
        }
        public void progress(String path, long done, long maximum) throws Exception {
            if (path.startsWith("Checking version: ")) {
                require(done == 0 && maximum == 0); indeterminate++; return;
            }
            require(done >= last && maximum == SIZE && done <= maximum);
            last = done; total = maximum; copying++;
        }
    }
    private static byte[] zip(String member, byte[] bytes) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream archive = new ZipOutputStream(buffer)) {
            archive.putNextEntry(new ZipEntry(member)); archive.write(bytes); archive.closeEntry();
        }
        return buffer.toByteArray();
    }
    private static List<OwnerInputImport.Version> catalog(OwnerInputImport.Required row) throws Exception {
        return Arrays.asList(new OwnerInputImport.Version("synthetic-supported", MANIFEST, Arrays.asList(row), true));
    }
    private static void absentPartials(File root) throws Exception {
        if (!root.exists()) return;
        File[] entries = root.listFiles(); require(entries != null);
        for (File file : entries) { require(!file.getName().endsWith(".part")); if (file.isDirectory()) absentPartials(file); }
    }
    private static void importCase(File root, Tree source, byte[] zipped, OwnerInputImport.Required row, boolean archive, boolean cancel) throws Exception {
        Progress progress = new Progress(cancel);
        OwnerInputImport importer = new OwnerInputImport(root, Arrays.asList(row), 0, progress);
        boolean completed = false;
        try {
            OwnerInputImport.Result result = archive ? importer.zip(new ByteArrayInputStream(zipped)) : importer.tree(source);
            require(result.bytes == SIZE); completed = true;
        } catch (InterruptedIOException expected) { require(cancel && progress.cancelled); }
        File destination = new File(new File(root, "files"), MEMBER);
        if (cancel) {
            require(!completed && !destination.exists() && progress.last > 0 && progress.last < SIZE);
            absentPartials(root);
        } else {
            require(completed && progress.last == SIZE && progress.total == SIZE && progress.copying > 1);
            require(OwnerInputImport.digest(destination).equals(row.sha256));
        }
    }
    private static void refused(Tree source, byte[] zipped, List<OwnerInputImport.Version> versions, boolean archive, String expected) throws Exception {
        Progress progress = new Progress(false);
        try {
            if (archive) OwnerInputImport.identifyZip(new ByteArrayInputStream(zipped), versions, progress);
            else OwnerInputImport.identifyTree(source, versions, progress);
            throw new IOException("unexpected-input-admission");
        } catch (OwnerInputImport.VersionRefused refusal) {
            require(refusal.found.startsWith(expected));
            require(refusal.supported.equals(Arrays.asList("synthetic-supported")));
            require(refusal.getMessage().contains("Filenames and labels are not proof."));
        }
        require(progress.indeterminate > 0 && progress.copying == 0);
    }
    public static void main(String[] args) {
        try { run(args); }
        catch (Throwable error) { System.out.println("FAIL importer-contract"); System.exit(1); }
    }
    private static void run(String[] args) throws Exception {
        require(args.length == 2 && (args[1].equals("--host") || args[1].equals("--android")));
        if (args[1].equals("--android")) {
            Class<?> process = Class.forName("android.os.Process");
            require(((Integer)process.getMethod("myUid").invoke(null)).intValue() >= 10000);
        }
        File root = new File(args[0]).getAbsoluteFile();
        require(root.equals(root.getCanonicalFile()) && !root.exists() && root.mkdir());
        File sourceRoot = new File(root, "source");
        byte[] bytes = new byte[SIZE]; for (int i = 0; i < bytes.length; i++) bytes[i] = (byte)(i * 17 + 3);
        File sourceFile = new File(sourceRoot, MEMBER); write(sourceFile, bytes);
        String before = OwnerInputImport.digest(sourceFile);
        OwnerInputImport.Required row = new OwnerInputImport.Required(MEMBER, SIZE, before);
        Tree source = new Tree(sourceRoot, SIZE);
        Tree unknownSize = new Tree(sourceRoot, -1);
        byte[] archive = zip(MEMBER, bytes);
        File sourceZip = new File(root, "source.zip"); write(sourceZip, archive);
        String zipBefore = OwnerInputImport.digest(sourceZip);
        List<OwnerInputImport.Version> versions = catalog(row);
        for (boolean zipped : new boolean[]{false, true}) {
            Progress identifying = new Progress(false);
            OwnerInputImport.Version selected = zipped
                ? OwnerInputImport.identifyZip(new FileInputStream(sourceZip), versions, identifying)
                : OwnerInputImport.identifyTree(unknownSize, versions, identifying);
            require(selected == versions.get(0) && identifying.indeterminate > 0 && identifying.copying == 0);
            String kind = zipped ? "zip" : "folder";
            importCase(new File(root, kind), source, archive, row, zipped, false);
            pass(kind + "-validated");
            importCase(new File(root, kind + "-cancelled"), source, archive, row, zipped, true);
            pass(kind + "-cancelled-without-accepted-output");
            OwnerInputImport.Required other = new OwnerInputImport.Required(MEMBER, SIZE, repeat('b', 64));
            refused(source, archive, catalog(other), zipped, "unknown");
            pass(kind + "-unknown-refused");
            List<OwnerInputImport.Version> unsupported = Arrays.asList(
                new OwnerInputImport.Version("synthetic-supported", MANIFEST, Arrays.asList(other), true),
                new OwnerInputImport.Version("synthetic-older", MANIFEST, Arrays.asList(row), false));
            refused(source, archive, unsupported, zipped, "synthetic-older");
            pass(kind + "-unsupported-refused");
        }
        try {
            OwnerInputImport.identifyZip(new ByteArrayInputStream(zip("../outside", bytes)), versions, new Progress(false));
            throw new IllegalStateException("unsafe-archive-admitted");
        } catch (IOException expected) { require(expected.getMessage().equals("Unsafe input path")); }
        pass("zip-traversal-refused");
        require(before.equals(OwnerInputImport.digest(sourceFile)) && zipBefore.equals(OwnerInputImport.digest(sourceZip)));
        pass("source-unchanged");
        pass("honest-progress");
    }
}
