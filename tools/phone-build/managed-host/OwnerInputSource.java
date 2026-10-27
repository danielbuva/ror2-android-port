package dev.ror2lab.phonebuildhostfixture;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.*;
import java.util.*;
import org.json.*;

/** SAF is a read-only provider boundary; source URIs are never sent to Python or the network. */
final class OwnerInputSource implements OwnerInputImport.Source {
    static final class Access {
        final android.os.CancellationSignal signal = new android.os.CancellationSignal();
        private final Set<Closeable> opened = new HashSet<>();
        InputStream open(Context app, Uri uri) throws Exception {
            signal.throwIfCanceled();
            android.content.res.AssetFileDescriptor descriptor = app.getContentResolver().openAssetFileDescriptor(uri, "r", signal);
            if (descriptor == null) throw new IOException("Selected document unavailable");
            // Do not hold our lock across provider I/O; CancellationSignal interrupts opening.
            try {
                signal.throwIfCanceled();
                final InputStream stream = descriptor.createInputStream();
                synchronized (this) { signal.throwIfCanceled(); opened.add(stream); }
                return new FilterInputStream(stream) { public void close() throws IOException {
                    synchronized (Access.this) { opened.remove(stream); }
                    super.close();
                } };
            } catch (Exception error) { descriptor.close(); throw error; }
        }
        void cancel() {
            signal.cancel();
            Closeable[] streams;
            synchronized (this) { streams = opened.toArray(new Closeable[0]); opened.clear(); }
            for (Closeable stream : streams) try { stream.close(); } catch (IOException ignored) { }
        }
    }
    private final Access access;
    private final Context app;
    private final Uri tree;
    private final OwnerInputImport.Observer observer;
    private final Map<String, Uri> documents = new LinkedHashMap<>();
    private final Map<String, Long> sizes = new LinkedHashMap<>();
    private final Set<String> visited = new HashSet<>();
    private boolean inventoried;
    OwnerInputSource(Context app, Uri tree, OwnerInputImport.Observer observer, Access access) { this.app = app; this.tree = tree; this.observer = observer; this.access = access; }
    private void walk(String documentId, String prefix, int depth) throws Exception {
        observer.checkpoint();
        if (depth > 64 || !visited.add(documentId) || visited.size() > 100000) throw new IOException("Selected folder is cyclic or too large");
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, documentId);
        String[] projection = { DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_SIZE };
        try (Cursor cursor = app.getContentResolver().query(children, projection, null, null, null, access.signal)) {
            if (cursor == null) throw new IOException("Selected folder permission is unavailable; pick it again");
            while (cursor.moveToNext()) {
                observer.checkpoint(); String id = cursor.getString(0), name = cursor.getString(1);
                OwnerInputImport.safePath(name); if (name.contains("/")) throw new IOException("Invalid provider filename");
                String path = prefix + name;
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2))) walk(id, path + "/", depth + 1);
                else {
                    if (documents.put(path, DocumentsContract.buildDocumentUriUsingTree(tree, id)) != null || documents.size() > 100000)
                        throw new IOException("Duplicate or excessive provider entries");
                    sizes.put(path, cursor.isNull(3) ? -1L : cursor.getLong(3));
                }
            }
        }
    }
    public Map<String, Long> inventory() throws Exception { if (!inventoried) { walk(DocumentsContract.getTreeDocumentId(tree), "", 0); inventoried = true; } return sizes; }
    public InputStream open(String path) throws Exception { return access.open(app, documents.get(path)); }
    static void run(Context app, OwnerInputImport.Observer observer, Access access) throws Exception {
        JSONObject plan = ToolHostActivity.readJson(new File(app.getFilesDir(), "owner-input/install-inputs.json"));
        if (plan.getInt("schema") != 1 || !"import".equals(plan.getString("import_root"))) throw new IOException("Check a signed install release first");
        List<OwnerInputImport.Version> versions = new ArrayList<>();
        for (String field : new String[]{"supported_versions", "recognized_versions"}) {
            JSONArray candidates = plan.optJSONArray(field);
            if (candidates == null) { if (field.equals("recognized_versions")) continue; candidates = new JSONArray().put(new JSONObject().put("manifest", plan.getJSONObject("manifest")).put("manifest_sha256", plan.getString("manifest_sha256"))); }
            for (int i = 0; i < candidates.length(); i++) {
                JSONObject candidate = candidates.getJSONObject(i), manifest = candidate.getJSONObject("manifest");
                if (manifest.getInt("schema") != 1) throw new IOException("Reviewed input manifest required");
                List<OwnerInputImport.Required> rows = new ArrayList<>(); JSONArray files = manifest.getJSONArray("files");
                for (int n = 0; n < files.length(); n++) { JSONObject row = files.getJSONObject(n); rows.add(new OwnerInputImport.Required(row.getString("path"), row.getLong("bytes"), row.getString("sha256"))); }
                versions.add(new OwnerInputImport.Version(manifest.getString("game_version"), candidate.getString("manifest_sha256"), rows, field.equals("supported_versions")));
            }
        }
        android.content.SharedPreferences settings = app.getSharedPreferences(OwnerBuildService.PREFERENCES, 0);
        String selected = settings.getString("source_uri", ""), kind = settings.getString("source_kind", "");
        if (selected.isEmpty()) throw new IOException("Choose your game folder or ZIP first");
        Uri uri = Uri.parse(selected); boolean retained = false;
        for (android.content.UriPermission permission : app.getContentResolver().getPersistedUriPermissions())
            if (permission.isReadPermission() && permission.getUri().equals(uri)) retained = true;
        if (!retained) throw new IOException("Selected-file permission was revoked. Pick the folder or ZIP again to resume");
        // Identify before creating/modifying private import files. Labels alone never admit a version.
        OwnerInputSource treeSource = null; OwnerInputImport.Version selectedVersion;
        if ("tree".equals(kind)) { treeSource = new OwnerInputSource(app, uri, observer, access); selectedVersion = OwnerInputImport.identifyTree(treeSource, versions, observer); }
        else if ("zip".equals(kind)) { try (InputStream input = access.open(app, uri)) { selectedVersion = OwnerInputImport.identifyZip(input, versions, observer); } }
        else throw new IOException("Unsupported private input source");
        File root = new File(app.getFilesDir().getCanonicalFile(), "owner-input/import");
        if (!root.getCanonicalFile().equals(root.getAbsoluteFile())) throw new IOException("Private import root contains links");
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Private input root unavailable");
        String identity = selectedVersion.manifestSha256;
        if (!identity.matches("[0-9a-f]{64}")) throw new IOException("Verified manifest identity unavailable");
        File marker = new File(root, "native-manifest.json"), previousFiles = new File(root, "files");
        String previous = marker.isFile() ? ToolHostActivity.readJson(marker).getString("manifest_sha256") : "unbound";
        if (!previous.equals("unbound") && !previous.matches("[0-9a-f]{64}")) throw new IOException("Private import identity is invalid");
        if (!identity.equals(previous)) {
            if (!previousFiles.getCanonicalFile().equals(previousFiles.getAbsoluteFile())) throw new IOException("Private input files contain links");
            if (previousFiles.exists() && !previousFiles.renameTo(new File(root, "previous-import-" + previous + "-" + System.nanoTime())))
                throw new IOException("Could not retain previous imported files before switching versions");
            ToolHostActivity.writeJson(marker, new JSONObject().put("schema", 1).put("manifest_sha256", identity));
        }
        OwnerInputImport importer = new OwnerInputImport(root, selectedVersion.files, plan.getLong("workspace_bytes"), observer);
        OwnerInputImport.Result result;
        if ("tree".equals(kind)) result = importer.tree(treeSource);
        else if ("zip".equals(kind)) {
            try (InputStream input = access.open(app, uri)) {
                if (input == null) throw new IOException("Selected ZIP is unavailable"); result = importer.zip(input);
            }
        } else throw new IOException("Unsupported private input source");
        JSONObject receipt = new JSONObject().put("schema", 1).put("state", "IMPORTED").put("manifest_sha256", selectedVersion.manifestSha256)
            .put("game_version", selectedVersion.name).put("completed", result.bytes).put("total", result.bytes)
            .put("extra", new JSONArray(result.extra)).put("message", "Imported verified game files locally. Extra files ignored: " + result.extra.size());
        ToolHostActivity.writeJson(new File(app.getFilesDir(), "owner-input/import-state.json"), receipt);
    }
}
