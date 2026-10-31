import dev.ror2lab.phonebuildhostfixture.OwnerInputImport;
import java.io.*;
import java.util.Arrays;

/** Authored bytes only. A filled logical quota injects ENOSPC; never fills a volume. */
public final class InstallerQuotaHarness {
    private static final int QUOTA = 65536;
    private static void check(boolean value) { if (!value) throw new AssertionError("atomic quota contract"); }
    private static byte[] read(File file) throws Exception {
        try (FileInputStream input = new FileInputStream(file); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[4096]; int size;
            while ((size = input.read(chunk)) != -1) out.write(chunk, 0, size);
            return out.toByteArray();
        }
    }
    private static final class QuotaStream extends FilterOutputStream {
        private long remaining;
        QuotaStream(OutputStream output, File scratch) throws Exception {
            super(output); long used = 0;
            for (File file : scratch.listFiles()) if (file.isFile()) used += file.length();
            remaining = QUOTA - used;
        }
        @Override public void write(byte[] value, int offset, int count) throws IOException {
            int accepted = (int) Math.max(0, Math.min(count, remaining));
            if (accepted > 0) out.write(value, offset, accepted);
            remaining -= accepted;
            if (accepted != count) throw new IOException("ENOSPC: injected scratch quota");
        }
        @Override public void write(int value) throws IOException { write(new byte[]{(byte) value}, 0, 1); }
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("fresh scratch required");
        File root = new File(args[0]).getCanonicalFile();
        if (!root.mkdir()) throw new IOException("fresh scratch required");
        File target = new File(root, "receipt.json"), filler = new File(root, "quota-fill.bin");
        byte[] previous = "verified previous receipt\n".getBytes("UTF-8");
        OwnerInputImport.writeAtomic(target, output -> output.write(previous));
        // Fill only this logical quota, leaving 1 KiB for a real partial write.
        try (FileOutputStream output = new FileOutputStream(filler)) { output.write(new byte[QUOTA - previous.length - 1024]); output.getFD().sync(); }
        boolean failed = false;
        try {
            OwnerInputImport.writeAtomic(target, output -> new QuotaStream(output, root).write(new byte[4096]));
        } catch (IOException error) { check(error.getMessage().contains("ENOSPC")); failed = true; }
        check(failed && Arrays.equals(previous, read(target)) && !new File(root, "receipt.json.writing").exists());
        check(filler.delete());
        byte[] complete = "verified resumed receipt\n".getBytes("UTF-8");
        OwnerInputImport.writeAtomic(target, output -> output.write(complete));
        check(Arrays.equals(complete, read(target)));
        // A killed writer's deterministic partial is never appended/promoted.
        try (FileOutputStream output = new FileOutputStream(new File(root, "receipt.json.writing"))) { output.write(new byte[4096]); }
        OwnerInputImport.writeAtomic(target, output -> output.write(previous));
        check(Arrays.equals(previous, read(target)) && !new File(root, "receipt.json.writing").exists());
        System.out.println("PASS bounded-quota-enospc-preserves-receipt");
        System.out.println("PASS quota-cleanup-and-resume");
        System.out.println("PASS abandoned-partial-replaced");
    }
}
