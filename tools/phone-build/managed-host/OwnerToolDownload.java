package dev.ror2lab.phonebuildhostfixture;

import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;

/** HTTPS transport for a file URL admitted by the signed tool inventory. */
final class OwnerToolDownload {
    static InputStream skip(InputStream input, long offset, OwnerInputImport.Observer observer) throws Exception {
        try {
            while (offset > 0) {
                observer.checkpoint();
                long skipped = input.skip(Math.min(offset, 1024 * 1024));
                if (skipped == 0) {
                    if (input.read() == -1) throw new IOException("Source ended before the saved tool offset");
                    skipped = 1;
                }
                offset -= skipped;
            }
            return input;
        } catch (Exception error) {
            input.close();
            throw error;
        }
    }
    static InputStream open(String url, OwnerInputImport.Required row, long offset, OwnerInputImport.Observer observer) throws Exception {
        HttpsURLConnection connection = (HttpsURLConnection)new URL(url).openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(10000);
        connection.setRequestProperty("Accept-Encoding", "identity");
        if (offset > 0) connection.setRequestProperty("Range", "bytes=" + offset + "-");
        try {
            int status = connection.getResponseCode();
            String encoding = connection.getContentEncoding();
            if (encoding != null && !"identity".equalsIgnoreCase(encoding))
                throw new IOException("Tool source did not serve the original bytes: " + row.path);
            if (status == 206 && offset > 0) {
                String expected = "bytes " + offset + "-" + (row.bytes - 1) + "/" + row.bytes;
                if (!expected.equals(connection.getHeaderField("Content-Range")))
                    throw new IOException("Tool source did not serve the requested range: " + row.path);
            } else if (status != 200) throw new IOException("Tool source unavailable (HTTP " + status + "): " + row.path);
            InputStream stream = new FilterInputStream(connection.getInputStream()) {
                @Override public void close() throws IOException {
                    try { super.close(); } finally { connection.disconnect(); }
                }
            };
            return status == 200 ? skip(stream, offset, observer) : stream;
        } catch (Exception error) {
            connection.disconnect();
            throw error;
        }
    }
}
