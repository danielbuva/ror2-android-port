package dev.ror2owner.bootstrap;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileNotFoundException;

public final class ProfileRetentionProvider extends ContentProvider {
    @Override public boolean onCreate() {
        return true;
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override public String getType(Uri uri) {
        return "application/octet-stream";
    }

    @Override public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        File file = new File(getContext().getFilesDir(), uri.getPath());
        if (!file.exists()) throw new FileNotFoundException(uri.getPath());
        int pmode = ParcelFileDescriptor.MODE_READ_ONLY;
        if (mode.contains("w")) pmode |= ParcelFileDescriptor.MODE_WRITE_ONLY;
        return ParcelFileDescriptor.open(file, pmode);
    }
}
