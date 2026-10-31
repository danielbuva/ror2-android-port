package dev.ror2owner.bootstrap;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.res.AssetManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import android.util.AtomicFile;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.ref.WeakReference;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** Owns preparation before the unchanged Unity activity starts. */
public final class PayloadBootstrapActivity extends Activity {
    private static final String ORIGIN = "https://ror2.launcher.local/";
    private static final String ASSETS = "owner-bootstrap/";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static Backend singleton;
    private WebView web;
    private Backend backend;
    private AlertDialog reviewDialog;
    private boolean handingOff;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        setTheme(android.R.style.Theme_Material_Light_NoActionBar);
        try {
            synchronized (PayloadBootstrapActivity.class) {
                if (singleton == null) singleton = new Backend(getApplicationContext());
                backend = singleton;
            }
        } catch (Exception error) {
            android.widget.TextView failure = new android.widget.TextView(this);
            failure.setText("The owner-built preparation package is incomplete. Recreate the APK from its verified inputs.");
            setContentView(failure);
            return;
        }
        // A normal launcher re-entry in the same process resumes the already
        // prepared Unity activity, without rebuilding a second WebView or
        // writing data while the game may still be using it.
        if (backend.unityRequested && backend.status.equals("ready")) {
            try {
                ProfileRetentionProvider.beforeUnityLaunch(getApplicationContext());
                handingOff = true;
                startActivity(new Intent().setClassName(getPackageName(), "com.unity3d.player.UnityPlayerActivity"));
                finish();
                return;
            } catch (Exception failure) { handingOff = false; }
        }
        web = new WebView(this);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setBlockNetworkLoads(true);
        web.getSettings().setDomStorageEnabled(false);
        web.addJavascriptInterface(new Bridge(), "OwnerPayload");
        web.setWebViewClient(new LocalAssetClient(getAssets()));
        setContentView(web);
        web.loadUrl(ORIGIN + "index.html#setup");
        if (backend.status.equals("idle")) backend.start(backend.previous);
    }

    // Named static adapters avoid anonymous InnerClasses entries with a null
    // inner_name in the pinned on-device D8 graph reader.
    private static final class LocalAssetClient extends WebViewClient {
        private final AssetManager assets;
        LocalAssetClient(AssetManager assets) { this.assets = assets; }
        @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            return !request.getUrl().toString().startsWith(ORIGIN);
        }
        @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            String url = request.getUrl().toString();
            String name = request.getUrl().getPath();
            if (!url.startsWith(ORIGIN) || name == null || !name.matches("/(index.html|style.css|app.js|controller.js|background.png|owner-host.js)"))
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            try {
                String mime = name.endsWith(".js") ? "text/javascript" : name.endsWith(".css") ? "text/css" : name.endsWith(".png") ? "image/png" : "text/html";
                Map<String, String> headers = new HashMap<>();
                headers.put("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; frame-src 'none'; base-uri 'none'");
                headers.put("X-Content-Type-Options", "nosniff");
                return new WebResourceResponse(mime, "UTF-8", 200, "OK", headers, assets.open(ASSETS + "ui" + name));
            } catch (IOException error) {
                return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
            }
        }
    }

    private static final class AssetPayloadSource implements PayloadStore.Source {
        private final AssetManager assets;
        private final File root;
        AssetPayloadSource(AssetManager assets, File root) { this.assets = assets; this.root = root; }
        public InputStream open(String name) throws IOException { return assets.open(ASSETS + "data/" + name); }
        public long availableBytes() { return new StatFs(root.toString()).getAvailableBytes(); }
    }

    private void releaseWebView() {
        if (web != null) {
            web.removeJavascriptInterface("OwnerPayload");
            web.stopLoading();
            web.destroy();
            web = null;
        }
    }

    @Override protected void onPause() {
        if (handingOff) releaseWebView();
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (reviewDialog != null) reviewDialog.dismiss();
        releaseWebView();
        super.onDestroy();
    }

    private void reviewUpdate(Map<String, String> observed) {
        if (isFinishing() || isDestroyed()) { backend.reviewPending = false; return; }
        reviewDialog = new AlertDialog.Builder(this).setTitle("Update prepared game files?")
                .setMessage(observed.size() + " prepared files differ from this version. Their existing contents will be retained in an app-owned backup. Game saves and settings are outside this update.")
                .setPositiveButton("Update files", (dialog, which) -> {
                    backend.reviewPending = false;
                    backend.start(observed);
                }).setNegativeButton("Keep files", (dialog, which) -> backend.reviewPending = false)
                .setOnCancelListener(dialog -> backend.reviewPending = false).create();
        reviewDialog.setOnDismissListener(dialog -> backend.reviewPending = false);
        reviewDialog.show();
    }

    private final class Bridge {
        @JavascriptInterface public String getState() { return backend.snapshot(); }
        @JavascriptInterface public boolean invoke(String action) {
            if ("pause".equals(action)) return backend.pause();
            if ("resume".equals(action)) return backend.resume();
            if ("retry".equals(action)) {
                Map<String, String> observed;
                synchronized (backend) {
                    if (!backend.status.equals("error") || backend.reviewPending || backend.unityRequested) return false;
                    observed = backend.drift;
                    if (observed != null) backend.reviewPending = true;
                }
                if (observed == null) return backend.retry();
                MAIN.post(() -> reviewUpdate(observed));
                return true;
            }
            if ("launch".equals(action)) return backend.launch(new WeakReference<>(PayloadBootstrapActivity.this));
            return false;
        }
    }

    private static byte[] readBounded(InputStream input) throws IOException {
        try (InputStream source = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = source.read(buffer)) != -1) {
                if (output.size() + count > 1024 * 1024) throw new IOException("Preparation metadata exceeds bound");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private static final class Backend implements PayloadStore.Progress {
        final Context context;
        final File root;
        final List<PayloadStore.Row> rows = new ArrayList<>();
        final String profile;
        final AtomicFile receipt;
        Map<String, String> previous = Collections.emptyMap();
        Map<String, String> accepted = Collections.emptyMap();
        Map<String, String> drift;
        volatile String status = "idle";
        volatile boolean reviewPending;
        volatile boolean pause;
        volatile boolean unityRequested;
        String message = "Checking prepared game files.";
        Integer percent;
        boolean copied;
        boolean running;
        boolean launching;
        Thread worker;

        Backend(Context context) throws Exception {
            this.context = context;
            JSONObject metadata = new JSONObject(new String(readBounded(context.getAssets().open(ASSETS + "payload-index.json")), StandardCharsets.UTF_8));
            profile = metadata.getString("profile");
            if (metadata.getInt("schema") != 1 || !profile.matches("[0-9a-f]{64}")) throw new IOException("Invalid preparation profile");
            JSONArray files = metadata.getJSONArray("files");
            if (files.length() == 0 || files.length() > 512) throw new IOException("Invalid payload count");
            for (int i = 0; i < files.length(); i++) {
                JSONObject row = files.getJSONObject(i);
                rows.add(new PayloadStore.Row(row.getString("name"), row.getLong("bytes"), row.getString("sha256")));
            }
            File external = context.getExternalFilesDir(null);
            if (external == null) throw new IOException("App-specific storage unavailable");
            File payload = new File(external.getCanonicalFile(), "payload");
            if (!payload.exists() && !payload.mkdir()) throw new IOException("Payload directory unavailable");
            if (!payload.getAbsoluteFile().equals(payload.getCanonicalFile())) throw new IOException("Payload symlink refused");
            root = payload.getCanonicalFile();
            receipt = new AtomicFile(new File(context.getFilesDir(), "owner-payload-receipt.json"));
            if (receipt.getBaseFile().isFile()) {
                try (FileInputStream source = receipt.openRead()) {
                    JSONObject saved = new JSONObject(new String(readBounded(source), StandardCharsets.UTF_8));
                    if (saved.getInt("schema") == 1 && context.getPackageName().equals(saved.getString("package"))) {
                        JSONObject hashes = saved.getJSONObject("files");
                        HashMap<String, String> known = new HashMap<>();
                        java.util.Iterator<String> keys = hashes.keys();
                        while (keys.hasNext()) {
                            String name = keys.next(), hash = hashes.getString(name);
                            if (hash.matches("[0-9a-f]{64}")) known.put(name, hash);
                        }
                        previous = Collections.unmodifiableMap(known);
                    }
                } catch (Exception ignored) { previous = Collections.emptyMap(); }
            }
        }

        synchronized String snapshot() {
            try {
                JSONObject caps = new JSONObject();
                caps.put("pause", status.equals("preparing") && running && !launching && !pause);
                caps.put("resume", status.equals("paused"));
                caps.put("retry", status.equals("error") && !reviewPending && !unityRequested);
                caps.put("launch", status.equals("ready"));
                JSONObject value = new JSONObject();
                value.put("status", status).put("progress", percent == null ? JSONObject.NULL : percent)
                        .put("message", message).put("capabilities", caps);
                return value.toString();
            } catch (Exception error) { return "{\"status\":\"unavailable\",\"progress\":null,\"message\":\"Preparation state unavailable.\",\"capabilities\":{}}"; }
        }

        synchronized void start(Map<String, String> reviewed) {
            if (running || unityRequested) return;
            running = true;
            launching = false;
            accepted = reviewed;
            drift = null;
            pause = false;
            copied = false;
            status = "preparing";
            percent = null;
            message = "Checking prepared game files.";
            worker = new Thread(() -> {
                try {
                    Map<String, String> hashes = PayloadStore.install(root, rows, new AssetPayloadSource(context.getAssets(), root), this, accepted);
                    JSONObject saved = new JSONObject();
                    saved.put("schema", 1).put("package", context.getPackageName()).put("profile", profile).put("files", new JSONObject(hashes));
                    FileOutputStream out = null;
                    try {
                        out = receipt.startWrite();
                        out.write(saved.toString().getBytes(StandardCharsets.UTF_8));
                        receipt.finishWrite(out);
                    } catch (Exception error) { if (out != null) receipt.failWrite(out); throw error; }
                    synchronized (this) { previous = hashes; running = false; status = "ready"; percent = 100; message = "Game files are ready."; }
                } catch (PayloadStore.Paused paused) {
                    synchronized (this) { running = false; status = "paused"; message = "Preparation paused. Completed files are retained."; }
                } catch (PayloadStore.Drift changed) {
                    synchronized (this) { running = false; drift = changed.observed; status = "error"; percent = null; message = "Existing prepared files differ. Choose Retry to review the update."; }
                } catch (Exception error) {
                    synchronized (this) { running = false; status = "error"; percent = null; message = "Preparation stopped. Check free storage and retry."; }
                    android.util.Log.e("OwnerPayload", "preparation_failed_" + error.getClass().getSimpleName());
                }
            }, "OwnerPayloadPreparation");
            worker.start();
        }

        public synchronized void update(String phase, long done, long total) {
            if (phase.equals("copy")) copied = true;
            int fraction = total == 0 ? 100 : (int) Math.min(100, done * 100 / total);
            percent = phase.equals("ready") ? 99 : phase.equals("copy") ? 20 + fraction * 70 / 100 : copied ? 90 + fraction * 9 / 100 : fraction / 5;
            message = pause ? "Pausing after the current file." : phase.equals("copy") ? "Preparing game files." : "Checking prepared game files.";
        }
        public boolean pauseRequested() { return pause; }
        synchronized boolean pause() {
            if (!status.equals("preparing") || pause || launching) return false;
            pause = true;
            message = "Pausing after the current file.";
            return true;
        }
        synchronized boolean resume() { if (!status.equals("paused")) return false; start(accepted); return true; }
        synchronized boolean retry() { if (!status.equals("error") || drift != null || unityRequested) return false; start(accepted); return true; }
        synchronized boolean launch(WeakReference<PayloadBootstrapActivity> activity) {
            if (!status.equals("ready") || running) return false;
            running = true; launching = true;
            status = "preparing"; percent = null; pause = false;
            message = "Checking game files before launch.";
            worker = new Thread(() -> {
                try {
                    PayloadStore.verify(root, rows, this);
                    MAIN.post(() -> {
                        PayloadBootstrapActivity target = activity.get();
                        if (target == null || target.isFinishing() || target.isDestroyed()) {
                            synchronized (this) { running = false; status = "ready"; percent = 100; message = "Game files are ready."; }
                            return;
                        }
                        boolean hadGame = unityRequested;
                        try {
                            Intent intent = new Intent().setClassName(context.getPackageName(), "com.unity3d.player.UnityPlayerActivity");
                            ProfileRetentionProvider.beforeUnityLaunch(context);
                            unityRequested = true;
                            target.handingOff = true;
                            target.startActivity(intent);
                            synchronized (this) { running = false; status = "ready"; percent = 100; message = "Game files are ready."; }
                            target.finish();
                        } catch (Exception failure) {
                            unityRequested = hadGame;
                            target.handingOff = false;
                            synchronized (this) {
                                running = false; status = "error"; percent = null;
                                message = failure instanceof IOException ? "Local profile recovery is pending or unavailable. Open the installer and retry recovery before launching."
                                        : hadGame ? "The game could not be resumed. Exit and restart it." : "The game could not be started. Retry preparation.";
                            }
                        }
                    });
                } catch (Exception failure) {
                    synchronized (this) { running = false; status = "error"; percent = null; message = unityRequested ? "Prepared files changed. Exit and restart the game before preparing them." : "Prepared files changed. Retry preparation."; }
                }
            }, "OwnerPayloadLaunchCheck");
            worker.start();
            return true;
        }
    }
}
