"""Execute the bootstrap's named adapters with synthetic Android API doubles."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/owner-apk/PayloadBootstrapActivity.java"


class PayloadBootstrapAdapterTests(unittest.TestCase):
    def test_named_adapters_preserve_asset_policy_and_payload_source(self):
        homes = [Path(os.environ.get("JAVA_HOME", "/absent")), Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/OpenJDK")]
        compiler = next((home / "bin/javac" for home in homes if (home / "bin/javac").is_file()), None)
        if compiler is None and shutil.which("javac"):
            compiler = Path(shutil.which("javac"))
        if compiler is None:
            self.skipTest("Java compiler absent; bootstrap adapters not host-qualified")
        activity = SOURCE.read_text()
        self.assertIn("new LocalAssetClient(getAssets())", activity)
        self.assertIn("new AssetPayloadSource(context.getAssets(), root)", activity)
        self.assertNotRegex(activity, r"new\s+(?:WebViewClient|PayloadStore\.Source)\s*\(\s*\)\s*\{")
        # Compile the unmodified adapter declarations, not a translated model.
        adapters = activity[activity.index("    private static final class LocalAssetClient") : activity.index("    private void releaseWebView()")]
        constants = "\n".join(re.findall(r"    private static final String (?:ORIGIN|ASSETS) = .*;", activity))
        harness = r"""
import java.io.*;
import java.net.URI;
import java.util.*;
import java.lang.reflect.Modifier;
public final class PayloadBootstrapActivity {
CONSTANTS
ADAPTERS
    static final class AssetManager {
        final Map<String, byte[]> files = new HashMap<>();
        String opened;
        InputStream open(String path) throws IOException {
            opened = path;
            if (!files.containsKey(path)) throw new IOException("synthetic missing asset");
            return new ByteArrayInputStream(files.get(path));
        }
    }
    static final class StatFs {
        static String observed;
        StatFs(String path) { observed = path; }
        long getAvailableBytes() { return 123456789L; }
    }
    static final class PayloadStore {
        interface Source { InputStream open(String name) throws IOException; long availableBytes(); }
    }
    static final class WebView {}
    static final class WebResourceRequest {
        final URI uri;
        WebResourceRequest(String uri) { this.uri = URI.create(uri); }
        URI getUrl() { return uri; }
    }
    static class WebViewClient {
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) { return false; }
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) { return null; }
    }
    static final class WebResourceResponse {
        final String mime;
        final int code;
        final Map<String, String> headers;
        final InputStream data;
        WebResourceResponse(String mime, String encoding, int code, String reason, Map<String, String> headers, InputStream data) {
            this.mime = mime; this.code = code; this.headers = headers; this.data = data;
        }
    }
    static void require(boolean condition) { if (!condition) throw new AssertionError(); }
    public static void main(String[] args) throws Exception {
        for (Class<?> type : new Class<?>[] {LocalAssetClient.class, AssetPayloadSource.class}) {
            require(!type.isAnonymousClass() && !type.getSimpleName().isEmpty());
            require(type.getEnclosingMethod() == null && Modifier.isStatic(type.getModifiers()));
        }
        AssetManager assets = new AssetManager();
        LocalAssetClient client = new LocalAssetClient(assets);
        String[] names = {"index.html", "style.css", "app.js", "controller.js", "background.png", "owner-host.js"};
        String[] mimes = {"text/html", "text/css", "text/javascript", "text/javascript", "image/png", "text/javascript"};
        for (int i = 0; i < names.length; i++) {
            String path = ASSETS + "ui/" + names[i];
            assets.files.put(path, new byte[] {42});
            WebResourceRequest request = new WebResourceRequest(ORIGIN + names[i]);
            require(!client.shouldOverrideUrlLoading(null, request));
            WebResourceResponse response = client.shouldInterceptRequest(null, request);
            require(response.code == 200 && response.mime.equals(mimes[i]) && response.data.read() == 42);
            require(assets.opened.equals(path));
            require(response.headers.get("X-Content-Type-Options").equals("nosniff"));
            require(response.headers.get("Content-Security-Policy").contains("connect-src 'none'"));
        }
        for (String uri : new String[] {"https://example.invalid/app.js", "file:///app.js", "https://ror2.launcher.local.evil/app.js", ORIGIN + "../secret", ORIGIN + "unknown"}) {
            assets.opened = null;
            WebResourceRequest request = new WebResourceRequest(uri);
            require(client.shouldOverrideUrlLoading(null, request) == !uri.startsWith(ORIGIN));
            require(client.shouldInterceptRequest(null, request).code == 403 && assets.opened == null);
        }
        assets.files.clear();
        require(client.shouldInterceptRequest(null, new WebResourceRequest(ORIGIN + "index.html")).code == 404);
        File root = new File("synthetic-payload-root");
        AssetPayloadSource source = new AssetPayloadSource(assets, root);
        assets.files.put(ASSETS + "data/authored.bin", new byte[] {17});
        require(source.open("authored.bin").read() == 17);
        require(assets.opened.equals(ASSETS + "data/authored.bin"));
        require(source.availableBytes() == 123456789L && StatFs.observed.equals(root.toString()));
        try { source.open("missing.bin"); throw new AssertionError(); } catch (IOException expected) {}
        System.out.println("named-adapter-contracts-passed");
    }
}
""".replace("CONSTANTS", constants).replace("ADAPTERS", adapters)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / SOURCE.name
            source.write_text(harness)
            classes = base / "classes"
            classes.mkdir()
            compiled = subprocess.run(
                [str(compiler), "-source", "8", "-target", "8", "-d", str(classes), str(source)], capture_output=True, text=True, timeout=60
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for path in classes.glob("*.class"):
                self.assertEqual(int.from_bytes(path.read_bytes()[6:8], "big"), 52)
                self.assertNotRegex(path.name, r"\$[0-9]+\.class$")
            result = subprocess.run([str(compiler.with_name("java")), "-cp", str(classes), SOURCE.stem], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("named-adapter-contracts-passed", result.stdout)
