package dev.ror2lab.phonehostfixture;

import android.app.Activity;
import android.os.Bundle;
import android.os.Process;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;

/** A build-tool location experiment; no game or interpreter is hosted here. */
public final class HostProbeActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView text = new TextView(this);
        text.setText("Running authored native host checks");
        setContentView(text);
        new Thread(new Runnable() {
          @Override public void run() {
            JSONObject report = new JSONObject();
            try {
                File installed = new File(getApplicationInfo().nativeLibraryDir, "libtoolprobe.so");
                File writable = new File(getFilesDir(), "writable-probe");
                report.put("targetSdk", getApplicationInfo().targetSdkVersion);
                report.put("uid", Process.myUid());
                report.put("installedExists", installed.isFile());
                report.put("installedWritable", installed.canWrite());
                JSONObject positive = execute(installed);
                report.put("installed", positive);
                try (InputStream input = getAssets().open("control.bin");
                     FileOutputStream output = new FileOutputStream(writable)) {
                    byte[] buffer = new byte[4096];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                }
                report.put("writableMarkedExecutable", writable.setExecutable(true, true));
                JSONObject negative = execute(writable);
                report.put("writable", negative);
                JSONObject child = new JSONObject(positive.optString("output", "{}"));
                boolean passed = positive.optInt("exit", -1) == 0
                    && child.optInt("uid", -1) == Process.myUid()
                    && child.optInt("answer", -1) == 42
                    && "authored-phone-host-v1".equals(child.optString("marker"))
                    && !installed.canWrite()
                    && negative.optString("error").contains("error=13");
                report.put("success", passed);
            } catch (Exception error) {
                try { report.put("failure", error.toString()); report.put("success", false); }
                catch (Exception ignored) { }
            }
            try (FileOutputStream output = new FileOutputStream(new File(getFilesDir(), "host-report.json"))) {
                output.write(report.toString(2).getBytes(StandardCharsets.UTF_8));
            } catch (Exception error) {
                android.util.Log.e("PhoneHostFixture", "Report write failed", error);
            }
            runOnUiThread(new Runnable() {
                @Override public void run() { text.setText("Host fixture complete"); }
            });
          }
        }, "phone-host-fixture").start();
    }

    private static JSONObject execute(File binary) throws Exception {
        JSONObject result = new JSONObject();
        try {
            java.lang.Process process = new ProcessBuilder(binary.getAbsolutePath()).redirectErrorStream(true).start();
            if (!process.waitFor(10, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                throw new IllegalStateException("Authored child timed out");
            }
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int count;
            try (InputStream input = process.getInputStream()) {
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            }
            result.put("exit", process.exitValue());
            result.put("output", new String(output.toByteArray(), StandardCharsets.UTF_8));
        } catch (java.io.IOException error) {
            result.put("error", error.toString());
        }
        return result;
    }
}
