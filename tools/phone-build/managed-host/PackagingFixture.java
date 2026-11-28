package dev.ror2lab.phonebuildhostfixture;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.pm.ApplicationInfo;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;

/** File transport for the disposable synthetic packaging acceptance only. */
public final class PackagingFixture extends ContentProvider {
    private FutureTask<String> pendingWrite;

    @Override public boolean onCreate() { return true; }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (Binder.getCallingUid() != 2000 || !"dev.ror2lab.installertest".equals(getContext().getPackageName())
                || (getContext().getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) == 0)
            throw new SecurityException("Synthetic packaging fixture requires the Android shell");

        String path = uri.getPath();
        if (path == null) throw new FileNotFoundException("Missing synthetic operation");
        File root = checked(getContext().getFilesDir(), "owner-input");
        if (path.startsWith("/write/") && "w".equals(mode)) {
            String name = path.substring("/write/".length());
            if (!(name.equals("debug-release-source.json") || name.equals("import-state.json") || name.equals("update-state.json")
                    || name.matches("import/files/(?:apk|payload)/[A-Za-z0-9_. /+-]+")))
                throw new FileNotFoundException("Unknown synthetic input");
            File target = checked(root, name);
            File parent = target.getParentFile();
            if (!parent.isDirectory() && !parent.mkdirs()) throw new FileNotFoundException("Synthetic input directory");
            return startWrite(target);
        }
        if (!"r".equals(mode)) throw new FileNotFoundException("Unknown synthetic operation");
        if (path.equals("/write-result")) {
            FutureTask<String> task;
            synchronized (this) { task = pendingWrite; }
            try { return result(task.get(30, TimeUnit.SECONDS)); }
            catch (Exception error) { throw new FileNotFoundException("Synthetic write unavailable"); }
        }
        if (path.equals("/producer-attempts")) {
            File jobs = checked(root, "work/releases/jobs");
            int count = 0;
            String[] attempts = jobs.list();
            if (attempts != null) for (String attempt : attempts) {
                if (attempt.matches("[0-9a-f]{16}-[A-Za-z0-9_-]+") && checked(jobs, attempt + "/producer.log").isFile()) count++;
            }
            return result(Integer.toString(count));
        }
        File source;
        if (path.equals("/check-diagnostic")) source = checked(getContext().getDataDir(), "shared_prefs/owner-check-diagnostic.xml");
        else {
            if (!path.matches("/read/(?:update-(?:state|request)|install-(?:checkpoint|diagnostic)|(?:previous-)?installed-release|owner-apk-ready)\\.json"
                    + "|/read/work/releases/issued-versions\\.json"))
                throw new FileNotFoundException("Unknown synthetic output");
            source = checked(root, path.substring("/read/".length()));
        }
        if (!source.isFile()) return result("");
        return openPipeHelper(uri, "application/octet-stream", null, source, new PipeDataWriter<File>() {
            @Override public void writeDataToPipe(ParcelFileDescriptor descriptor, Uri ignored, String mimeType, Bundle options, File file) {
                try (InputStream input = new FileInputStream(file)) {
                    transfer(input, new FileOutputStream(descriptor.getFileDescriptor()), null);
                } catch (IOException error) { throw new java.io.UncheckedIOException(error); }
            }
        });
    }

    private synchronized ParcelFileDescriptor startWrite(File target) throws FileNotFoundException {
        if (pendingWrite != null && !pendingWrite.isDone()) throw new FileNotFoundException("Synthetic write already running");
        try {
            ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createPipe();
            pendingWrite = new FutureTask<>(new Callable<String>() {
                @Override public String call() throws Exception {
                    return receive(pipe[0], target);
                }
            });
            new Thread(pendingWrite, "packaging-fixture-write").start();
            return pipe[1];
        } catch (IOException error) { throw new FileNotFoundException("Synthetic input unavailable"); }
    }

    private static String receive(ParcelFileDescriptor descriptor, File target) throws Exception {
        try (InputStream input = new ParcelFileDescriptor.AutoCloseInputStream(descriptor)) {
            File temporary = File.createTempFile("packaging-", ".tmp", target.getParentFile());
            try {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                try (FileOutputStream output = new FileOutputStream(temporary)) {
                    transfer(input, output, digest);
                    output.getFD().sync();
                }
                if (!temporary.renameTo(target)) throw new IOException("Synthetic input publish failed");
                StringBuilder hex = new StringBuilder();
                for (byte value : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
                return hex.toString();
            } finally { temporary.delete(); }
        }
    }

    private static void transfer(InputStream input, OutputStream output, MessageDigest digest) throws IOException {
        byte[] buffer = new byte[16384];
        int size, total = 0;
        while ((size = input.read(buffer)) != -1) {
            total += size;
            if (total > 16 * 1024 * 1024) throw new IOException("Synthetic fixture size limit");
            output.write(buffer, 0, size);
            if (digest != null) digest.update(buffer, 0, size);
        }
    }

    private static File checked(File root, String name) throws FileNotFoundException {
        try {
            File canonicalRoot = root.getCanonicalFile();
            File file = new File(canonicalRoot, name);
            if (!file.equals(file.getCanonicalFile()) || !file.getPath().startsWith(canonicalRoot.getPath() + File.separator))
                throw new FileNotFoundException("Synthetic path escapes its root");
            return file;
        } catch (IOException error) { throw new FileNotFoundException("Synthetic path unavailable"); }
    }

    private static ParcelFileDescriptor result(String value) throws FileNotFoundException {
        try {
            ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createPipe();
            try (ParcelFileDescriptor.AutoCloseOutputStream output = new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1])) {
                output.write(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            } catch (IOException error) {
                pipe[0].close();
                throw error;
            }
            return pipe[0];
        } catch (IOException error) { throw new FileNotFoundException("Synthetic result unavailable"); }
    }

    @Override public String getType(Uri uri) { return null; }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) { throw new UnsupportedOperationException(); }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
}
