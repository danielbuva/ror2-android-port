package dev.ror2lab.phonebuildhostfixture;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsProvider;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

/** In the disposable installer, return an Android document result from a runner-owned fixture. */
public final class AcquisitionFixture {
    private static final String PACKAGE = "dev.ror2lab.installertest";
    private static final String AUTHORITY = PACKAGE + ".acquisition";
    private static final String[] COLUMNS = {
        Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_MIME_TYPE, Document.COLUMN_SIZE
    };

    private static boolean enabled(Context app) {
        return PACKAGE.equals(app.getPackageName()) && (app.getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
    }

    static Intent selection(Context app) throws Exception {
        if (!enabled(app)) return null;
        File request = new File(app.getFilesDir(), "owner-input/acquisition-selection.json");
        if (!request.isFile()) return null;
        String id = ToolHostActivity.readJson(request).getString("document");
        if (!request.delete()) throw new IOException("Could not consume the lab document selection");
        if (!id.matches("LabAcquisition-[0-9a-f]{16}/(Supported|Older|Supported\\.zip)"))
            throw new IOException("Invalid lab document selection");
        return new Intent(app, Result.class).putExtra("document", id);
    }

    public static final class Result extends Activity {
        @Override public void onCreate(Bundle state) {
            super.onCreate(state);
            if (enabled(this)) {
                String id = getIntent().getStringExtra("document");
                if (id != null) {
                    boolean tree = !id.endsWith(".zip");
                    Uri uri = tree ? DocumentsContract.buildTreeDocumentUri(AUTHORITY, id)
                        : DocumentsContract.buildDocumentUri(AUTHORITY, id);
                    Intent result = new Intent().setData(uri)
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                    if (tree) result.addFlags(Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
                    setResult(RESULT_OK, result);
                }
            }
            finish();
        }
    }

    public static final class Provider extends DocumentsProvider {
        @Override public boolean onCreate() { return enabled(getContext()); }

        private File document(String id) throws FileNotFoundException {
            File external = getContext().getExternalFilesDir(null);
            if (!enabled(getContext()) || external == null ||
                !id.matches("LabAcquisition-[0-9a-f]{16}/(Supported(?:/.*)?|Older(?:/.*)?|Supported\\.zip)"))
                throw new FileNotFoundException("Unknown lab document");
            try {
                File file = new File(external.getCanonicalFile(), id);
                if (file.equals(file.getCanonicalFile()) && (file.isFile() || file.isDirectory())) return file;
            } catch (IOException ignored) { }
            throw new FileNotFoundException("Unknown lab document");
        }

        private void row(MatrixCursor cursor, File file, String id) {
            MatrixCursor.RowBuilder row = cursor.newRow();
            for (String column : cursor.getColumnNames()) {
                switch (column) {
                    case Document.COLUMN_DOCUMENT_ID: row.add(id); break;
                    case Document.COLUMN_DISPLAY_NAME: row.add(file.getName()); break;
                    case Document.COLUMN_MIME_TYPE:
                        row.add(file.isDirectory() ? Document.MIME_TYPE_DIR : id.endsWith(".zip") ? "application/zip" : "application/octet-stream"); break;
                    case Document.COLUMN_SIZE: row.add(file.isDirectory() ? null : file.length()); break;
                    default: row.add(null);
                }
            }
        }

        @Override public Cursor queryRoots(String[] projection) {
            return new MatrixCursor(projection == null ? new String[]{DocumentsContract.Root.COLUMN_ROOT_ID} : projection);
        }

        @Override public Cursor queryDocument(String id, String[] projection) throws FileNotFoundException {
            MatrixCursor cursor = new MatrixCursor(projection == null ? COLUMNS : projection);
            row(cursor, document(id), id);
            return cursor;
        }

        @Override public Cursor queryChildDocuments(String parent, String[] projection, String sort) throws FileNotFoundException {
            File[] children = document(parent).listFiles();
            if (children == null) throw new FileNotFoundException("Lab directory unavailable");
            MatrixCursor cursor = new MatrixCursor(projection == null ? COLUMNS : projection);
            for (File child : children) {
                String id = parent + "/" + child.getName();
                row(cursor, document(id), id);
            }
            return cursor;
        }

        @Override public boolean isChildDocument(String parent, String id) {
            return id.startsWith(parent + "/");
        }

        @Override public ParcelFileDescriptor openDocument(String id, String mode, CancellationSignal signal) throws FileNotFoundException {
            File file = document(id);
            if (!"r".equals(mode) || !file.isFile()) throw new FileNotFoundException("Read-only lab file required");
            if (signal != null) signal.throwIfCanceled();
            return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
        }
    }
}
