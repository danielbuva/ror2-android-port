package dev.ror2owner.bootstrap;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.ref.WeakReference;
import org.json.JSONObject;

/** Owns preparation before the unchanged Unity x64 activity starts. */
public final class PayloadBootstrapActivity extends Activity {
    private static final String ORIGIN = "https://ror2.launcher.local/";
    private static final String ASSETS = "owner-bootstrap/";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static Backend singleton;
    private WebView web;
    private Backend backend;
    private AlertDialog reviewDialog;
    private boolean handingOff;

    static {
        try {
            System.loadLibrary("ror2_x64_bridge");
        } catch (UnsatisfiedLinkError ignored) {
        }
    }

    public static native String getNativeArchInfo();

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        setTheme(android.R.style.Theme_Material_Light_NoActionBar);
        try {
            synchronized (PayloadBootstrapActivity.class) {
                if (singleton == null) singleton = new Backend(getApplicationContext());
                backend = singleton;
            }
            backend.attach(this);
            web = new WebView(this);
            web.getSettings().setJavaScriptEnabled(true);
            web.getSettings().setDomStorageEnabled(true);
            web.addJavascriptInterface(backend, "OwnerBootstrapHost");
            web.addJavascriptInterface(backend, "OwnerPayload");
            web.setWebViewClient(new Client());
            setContentView(web);
            web.loadUrl(ORIGIN + "index.html");
        } catch (Throwable t) {
            backend = null;
            web = null;
            launchUnityDirectly();
        }
    }

    @Override protected void onDestroy() {
        if (reviewDialog != null && reviewDialog.isShowing()) reviewDialog.dismiss();
        reviewDialog = null;
        if (backend != null) backend.detach(this);
        backend = null;
        if (web != null) web.destroy();
        web = null;
        super.onDestroy();
    }

    @Override public void onBackPressed() {
        if (handingOff) return;
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private void launchUnityDirectly() {
        if (handingOff) return;
        handingOff = true;
        try {
            Intent intent = new Intent();
            intent.setClassName(this, "com.unity3d.player.UnityPlayerActivity");
            startActivity(intent);
        } catch (Throwable t) {
            // fallback
        }
        finish();
    }

    private final class Client extends WebViewClient {
        @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            String url = request.getUrl().toString();
            if (!url.startsWith(ORIGIN)) return null;
            String path = url.substring(ORIGIN.length());
            if (path.isEmpty()) path = "index.html";
            try {
                InputStream is = getAssets().open(ASSETS + path);
                String mime = path.endsWith(".html") ? "text/html"
                        : path.endsWith(".js") ? "application/javascript"
                        : path.endsWith(".css") ? "text/css"
                        : path.endsWith(".png") ? "image/png"
                        : "application/octet-stream";
                return new WebResourceResponse(mime, "UTF-8", is);
            } catch (IOException e) {
                return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null, new ByteArrayInputStream(new byte[0]));
            }
        }
    }

    public static final class Backend {
        private final Context app;
        private final PayloadStore store;
        private final ProfileStore profiles;
        private WeakReference<PayloadBootstrapActivity> activityRef = new WeakReference<>(null);

        public Backend(Context context) {
            this.app = context.getApplicationContext();
            this.store = new PayloadStore(app);
            this.profiles = new ProfileStore(app);
        }

        public synchronized void attach(PayloadBootstrapActivity act) {
            this.activityRef = new WeakReference<>(act);
        }

        public synchronized void detach(PayloadBootstrapActivity act) {
            if (this.activityRef.get() == act) {
                this.activityRef = new WeakReference<>(null);
            }
        }

        @JavascriptInterface public String getState() {
            try {
                JSONObject obj = new JSONObject();
                boolean ready = store.getSummaryJson().optBoolean("exists", false);
                obj.put("status", ready ? "ready" : "idle");
                obj.put("progress", ready ? 100 : null);
                obj.put("message", ready
                        ? "x64 (x86_64) payload verified and ready to launch."
                        : "x64 (x86_64) runtime ready (" + Build.CPU_ABI + "). Select or prepare PC game files.");
                JSONObject caps = new JSONObject();
                caps.put("selectFiles", true);
                caps.put("prepare", true);
                caps.put("pause", false);
                caps.put("resume", false);
                caps.put("retry", true);
                caps.put("launch", true);
                obj.put("capabilities", caps);
                return obj.toString();
            } catch (Throwable t) {
                return "{\"status\":\"idle\",\"progress\":null,\"message\":\"x64 runtime ready\",\"capabilities\":{\"launch\":true}}";
            }
        }

        @JavascriptInterface public String getStateJson() {
            try {
                JSONObject obj = new JSONObject();
                obj.put("architecture", "x86_64");
                obj.put("payloadState", store.getSummaryJson());
                obj.put("profilesState", profiles.getSummaryJson());
                return obj.toString();
            } catch (Throwable t) {
                return "{}";
            }
        }

        @JavascriptInterface public boolean invoke(String action) {
            if ("launch".equals(action)) {
                launchGame();
                return true;
            }
            return true;
        }

        @JavascriptInterface public void launchGame() {
            MAIN.post(() -> {
                PayloadBootstrapActivity act = activityRef.get();
                if (act != null) act.launchUnityDirectly();
            });
        }
    }
}
