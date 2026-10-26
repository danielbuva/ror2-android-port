package dev.ror2lab.phonebuildhostfixture;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.system.Os;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.json.*;

public final class ToolHostActivity extends Activity {
    private static final Object JOB_LOCK = new Object();
    private static volatile boolean running;
    private final OwnerUpdateState model = new OwnerUpdateState();
    private final android.os.Handler handler = new android.os.Handler(android.os.Looper.getMainLooper());
    private TextView statusView;
    private Button checkButton, buildButton, installButton;
    private final Runnable refresh = new Runnable() { public void run() { refreshStatus(); handler.postDelayed(this, 500); } };
    private final android.content.SharedPreferences.OnSharedPreferenceChangeListener installObserver =
        new android.content.SharedPreferences.OnSharedPreferenceChangeListener() {
            public void onSharedPreferenceChanged(android.content.SharedPreferences preferences, String key) {
                handler.post(new Runnable() { public void run() { refreshStatus(); } });
            }
        };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        statusView = new TextView(this); layout.addView(statusView);
        checkButton = new Button(this); checkButton.setText("Check for updates"); layout.addView(checkButton);
        buildButton = new Button(this); buildButton.setText("Download and rebuild update"); layout.addView(buildButton);
        installButton = new Button(this); installButton.setText("Install owner-built update"); layout.addView(installButton);
        setContentView(layout);
        checkButton.setOnClickListener(new android.view.View.OnClickListener() { public void onClick(android.view.View ignored) { startUpdate("release-check"); } });
        buildButton.setOnClickListener(new android.view.View.OnClickListener() { public void onClick(android.view.View ignored) { startUpdate("release-build"); } });
        installButton.setOnClickListener(new android.view.View.OnClickListener() { public void onClick(android.view.View ignored) { installReady(); } });
        // Opening the installer is observational: never launch the old fixture or an install implicitly.
        refreshStatus();
    }
    @Override public void onResume() {
        super.onResume();
        getSharedPreferences(OwnerInstaller.STATUS, 0).registerOnSharedPreferenceChangeListener(installObserver);
        handler.removeCallbacks(refresh); handler.post(refresh);
    }
    @Override public void onPause() {
        handler.removeCallbacks(refresh);
        getSharedPreferences(OwnerInstaller.STATUS, 0).unregisterOnSharedPreferenceChangeListener(installObserver);
        super.onPause();
    }
    private static JSONObject readJson(File file) throws Exception {
        if (file.length() > 4 * 1024 * 1024) throw new IOException("Private status is too large");
        try (InputStream input = new FileInputStream(file)) { return readJson(input); }
    }
    private static JSONObject readJson(InputStream input) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(); byte[] buffer = new byte[8192]; int count;
        while ((count = input.read(buffer)) != -1) {
            if (bytes.size() + count > 4 * 1024 * 1024) throw new IOException("Private metadata is too large");
            bytes.write(buffer, 0, count);
        }
        return new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8));
    }
    private static void writeJson(File file, JSONObject value) throws Exception {
        File parent = file.getParentFile(); if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("Private owner directory unavailable");
        File staged = new File(parent, file.getName() + ".writing");
        try (FileOutputStream output = new FileOutputStream(staged)) { output.write(value.toString().getBytes(StandardCharsets.UTF_8)); output.getFD().sync(); }
        if (!staged.renameTo(file)) throw new IOException("Could not publish private status");
    }
    private static void updateStatus(Context app, String phase, String message) {
        try { writeJson(new File(app.getFilesDir(), "owner-input/update-state.json"), new JSONObject().put("state", phase).put("message", message)); }
        catch (Exception ignored) { /* Worker report retains the underlying failure if storage is unavailable. */ }
    }
    private JSONObject installedRequest(String action) throws Exception {
        JSONObject trust;
        try (InputStream input = getAssets().open("release-trust.json")) { trust = readJson(input); }
        String packageName = trust.getString("application_id");
        long installed = 0;
        try { installed = OwnerInstaller.version(getPackageManager().getPackageInfo(packageName, 0)); }
        catch (android.content.pm.PackageManager.NameNotFoundException absent) { /* first install */ }
        long installer = OwnerInstaller.version(getPackageManager().getPackageInfo(getPackageName(), 0));
        return new JSONObject().put("action", action).put("application_id", packageName)
            .put("installed_version", installed).put("installer_version", installer);
    }
    private void startUpdate(final String action) {
        final Context app = getApplicationContext();
        synchronized (JOB_LOCK) {
            if (running || OwnerInstaller.busy(app)) return;
            try {
                if ("release-check".equals(action)) model.beginCheck(); else model.beginBuild();
                recordInstalledRelease();
                OwnerInstaller.clearTerminalStatus(app);
                writeJson(new File(getFilesDir(), "owner-input/update-request.json"), installedRequest(action));
                updateStatus(app, model.phase().toString(), model.message());
                running = true;
            } catch (Exception error) { updateStatus(app, "ERROR", error.getMessage()); refreshStatus(); return; }
        }
        render();
        new Thread(new Runnable() { public void run() {
            try { new Worker(app).executeUpdate(action); }
            finally { synchronized (JOB_LOCK) { running = false; } }
        } }, "owner-release-update").start();
    }
    private void installReady() {
        final Context app = getApplicationContext();
        synchronized (JOB_LOCK) {
            if (running || OwnerInstaller.busy(app)) return;
            try {
                if (!model.canInstall()) throw new IOException("Check and rebuild a verified release first");
                if (android.os.Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
                    startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()))); return;
                }
                model.beginInstall(); running = true;
            } catch (Exception error) { updateStatus(app, "ERROR", error.getMessage()); refreshStatus(); return; }
        }
        render();
        new Thread(new Runnable() { public void run() {
            try {
                JSONObject ready = readJson(new File(app.getFilesDir(), "owner-input/owner-apk-ready.json"));
                JSONObject request = installedRequest("release-build");
                if (!ready.getString("application_id").equals(request.getString("application_id"))) throw new IOException("Ready package differs from trusted release configuration");
                File apk = new File(ready.getString("apk")).getCanonicalFile();
                if (!apk.getPath().startsWith(app.getFilesDir().getCanonicalPath() + "/") || !apk.isFile()) throw new IOException("Private owner APK required");
                OwnerInstaller.install(app, apk, ready.getString("sha256"), ready.getString("application_id"), ready.getLong("version_code"));
            } catch (Exception error) { updateStatus(app, "ERROR", "Installer unavailable: " + error.getMessage()); }
            finally { synchronized (JOB_LOCK) { running = false; } }
        } }, "owner-package-install").start();
    }
    private void recordInstalledRelease() throws Exception {
        if (!"INSTALLED".equals(OwnerInstaller.state(this))) return;
        File readyFile = new File(getFilesDir(), "owner-input/owner-apk-ready.json");
        if (!readyFile.isFile()) return;
        JSONObject ready = readJson(readyFile);
        if (!ready.has("release")) return;
        android.content.pm.PackageInfo actual = getPackageManager().getPackageInfo(ready.getString("application_id"), android.content.pm.PackageManager.GET_SIGNATURES);
        if (OwnerInstaller.version(actual) != ready.getLong("version_code") ||
            !OwnerInstaller.signer(actual).equals(getSharedPreferences(OwnerInstaller.STATUS, 0).getString("signer", ""))) return;
        JSONObject release = ready.getJSONObject("release");
        File receiptFile = new File(getFilesDir(), "owner-input/installed-release.json");
        if (receiptFile.isFile()) {
            JSONObject previous = readJson(receiptFile);
            if (previous.optLong("version_code") == OwnerInstaller.version(actual) &&
                previous.optString("application_id").equals(actual.packageName) &&
                previous.optString("bundle_sha256").equals(release.getString("bundle_sha256")) &&
                previous.optString("signer_sha256").equals(OwnerInstaller.signer(actual))) return;
        }
        writeJson(receiptFile, new JSONObject()
            .put("application_id", actual.packageName).put("version_code", OwnerInstaller.version(actual))
            .put("bundle_sha256", release.getString("bundle_sha256")).put("release", release).put("signer_sha256", OwnerInstaller.signer(actual)));
    }
    private void refreshStatus() {
        if (statusView == null) return;
        try {
            File progress = new File(getFilesDir(), "owner-input/update-state.json");
            if (progress.isFile()) {
                JSONObject value = readJson(progress); String detail = value.optString("message");
                if (value.has("release")) {
                    JSONObject release = value.getJSONObject("release");
                    detail += "\nRelease " + release.optString("version") + " (" + release.optLong("version_code") + ")";
                }
                if (value.has("changed_entries")) detail += "\nChanged outputs: " + value.getJSONArray("changed_entries").length();
                if (value.has("rebuilt")) detail += "\nRebuilt: " + value.getJSONArray("rebuilt").length() + "; reused: " + value.getJSONArray("reused").length();
                model.observe(value.getString("state"), detail);
            }
            String installation = OwnerInstaller.state(this);
            if (!running && OwnerInstaller.busy(this)) { OwnerInstaller.reconcile(this); installation = OwnerInstaller.state(this); }
            if (OwnerInstaller.busy(this)) model.observe(installation, OwnerInstaller.status(this));
            else if (!running && (model.phase() == OwnerUpdateState.Phase.READY || model.phase() == OwnerUpdateState.Phase.INSTALLING || model.phase() == OwnerUpdateState.Phase.AWAITING_CONFIRMATION)) {
                if ("INSTALLED".equals(installation)) { recordInstalledRelease(); model.observe(installation, OwnerInstaller.status(this)); }
                else if ("ERROR".equals(installation)) model.observe("ERROR", OwnerInstaller.status(this));
            }
            // A killed worker is not still running. Rechecking safely rediscovers the release/cache.
            if (!running && model.busy() && !OwnerInstaller.busy(this)) model.observe("ERROR", "Update work was interrupted. Check for updates to resume from retained outputs.");
        } catch (Exception error) { model.observe("ERROR", error.getMessage()); }
        render();
    }
    private void render() {
        String phase = model.phase() == OwnerUpdateState.Phase.ERROR ? "FAILED" : model.phase().toString().replace('_', ' ');
        statusView.setText(phase + "\n" + model.message());
        checkButton.setEnabled(!running && model.canCheck());
        buildButton.setEnabled(!running && model.canBuild());
        installButton.setEnabled(!running && model.canInstall());
    }
    private static File readyApk(Context app) throws Exception {
        File report=new File(app.getFilesDir(),"tool-host-report.json");
        byte[] bytes=new byte[(int)report.length()];
        try(DataInputStream in=new DataInputStream(new FileInputStream(report))){in.readFully(bytes);}
        JSONObject value=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        if(!value.getBoolean("success"))throw new IOException("successful owner build required");
        File apk=new File(value.getJSONObject("ownerApk").getString("apk")).getCanonicalFile();
        if(!apk.getPath().startsWith(app.getFilesDir().getCanonicalPath()+"/")||!apk.isFile())throw new IOException("private owner APK required");
        return apk;
    }
    public static final class ApkProvider extends ContentProvider {
        public boolean onCreate(){return true;}
        private File selected(Uri uri) throws FileNotFoundException {
            if(!"/owner.apk".equals(uri.getPath()))throw new FileNotFoundException("unknown owner APK");
            try{return readyApk(getContext());}catch(Exception error){throw new FileNotFoundException(error.toString());}
        }
        public String getType(Uri uri){return "application/vnd.android.package-archive";}
        public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
            if(!"r".equals(mode))throw new FileNotFoundException("read-only owner APK");
            return ParcelFileDescriptor.open(selected(uri),ParcelFileDescriptor.MODE_READ_ONLY);
        }
        public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort) {
            try { File apk=selected(uri);MatrixCursor cursor=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});cursor.addRow(new Object[]{"owner-built.apk",apk.length()});return cursor; }
            catch(FileNotFoundException error){return null;}
        }
        public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
        public int update(Uri uri,ContentValues values,String where,String[] args){throw new UnsupportedOperationException();}
        public int delete(Uri uri,String where,String[] args){throw new UnsupportedOperationException();}
    }
    public static class Runner extends Instrumentation {
        public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
        public void onStart() {
            new Worker(getTargetContext()).executeFixture();
            finish(Activity.RESULT_OK, new Bundle());
        }
    }
    private static class Worker {
    private final Context app;
    private File hostfxr;
    Worker(Context app) { this.app=app; }
    private android.content.res.AssetManager getAssets() { return app.getAssets(); }
    private File getFilesDir() { return app.getFilesDir(); }
    private File getCacheDir() { return app.getCacheDir(); }
    private android.content.pm.ApplicationInfo getApplicationInfo() { return app.getApplicationInfo(); }
    private void copyAssets(String name, File destination) throws Exception {
        String[] children = getAssets().list(name);
        if (children.length > 0) {
            if (!destination.mkdirs() && !destination.isDirectory()) throw new IOException("asset directory");
            for (String child : children) copyAssets(name.isEmpty() ? child : name + "/" + child, new File(destination, child));
        } else {
            try (InputStream source=getAssets().open(name); OutputStream output=new FileOutputStream(destination)) {
                byte[] bytes=new byte[65536]; int n; while ((n=source.read(bytes))!=-1) output.write(bytes,0,n);
            }
        }
    }
    private String text(File file) throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try (InputStream source=new FileInputStream(file)) { byte[] b=new byte[65536]; int n; while ((n=source.read(b))!=-1) bytes.write(b,0,n); }
        return new String(bytes.toByteArray(),StandardCharsets.UTF_8);
    }
    private String hash(File file) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try (InputStream source=new FileInputStream(file)) {byte[] b=new byte[65536]; int n; while((n=source.read(b))!=-1) digest.update(b,0,n);}
        StringBuilder s=new StringBuilder(); for(byte b:digest.digest()) s.append(String.format(Locale.ROOT,"%02x",b&255)); return s.toString();
    }
    private void systemTrust(File directory) throws Exception {
        // Use this Android app's default TLS trust, not the embedded OpenSSL
        // build's host-specific CA path. Publisher signature trust is separate.
        javax.net.ssl.TrustManagerFactory factory = javax.net.ssl.TrustManagerFactory.getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());
        factory.init((java.security.KeyStore) null);
        File bundle = new File(directory, "system-ca.pem"); int count = 0;
        try (FileOutputStream output = new FileOutputStream(bundle)) {
            for (javax.net.ssl.TrustManager manager : factory.getTrustManagers()) {
                if (!(manager instanceof javax.net.ssl.X509TrustManager)) continue;
                for (java.security.cert.X509Certificate certificate : ((javax.net.ssl.X509TrustManager) manager).getAcceptedIssuers()) {
                    String encoded = android.util.Base64.encodeToString(certificate.getEncoded(), android.util.Base64.NO_WRAP);
                    output.write(("-----BEGIN CERTIFICATE-----\n" + encoded + "\n-----END CERTIFICATE-----\n").getBytes(StandardCharsets.US_ASCII));
                    count++;
                }
            }
            output.getFD().sync();
        }
        if (count == 0 || !bundle.setReadOnly()) throw new IOException("Android system TLS trust unavailable");
        File empty = new File(directory, "empty-ca-directory");
        if (!empty.mkdir() || !empty.setReadOnly()) throw new IOException("Private TLS CA directory unavailable");
    }
    private JSONObject child(String label, List<String> arguments, File directory, File nativeDir, File links) throws Exception {
        File output=new File(directory,label+".log");
        // Pin before interpreter/JVM startup; a periodic watcher can miss its short heat spike.
        List<String> command=new ArrayList<>(Arrays.asList("/system/bin/taskset","1"));
        File thermalReceipt=new File(directory,label+"-thermal.json");
        if(label.equals("owner-backend") || label.equals("public-profile")) {
            command.addAll(Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),
                new File(nativeDir,"libpython3.14.so").getPath(),new File(directory,"python").getPath(),
                new File(directory,"repo/tools/phone-build/accepted-output/phone_runner.py").getPath(),
                "--receipt",thermalReceipt.getPath(),"--timeout","86400","--"));
        }
        command.addAll(arguments);
        ProcessBuilder builder=new ProcessBuilder(command).directory(directory).redirectErrorStream(true).redirectOutput(output);
        Map<String,String> env=builder.environment();
        File systemCa = new File(directory, "system-ca.pem");
        if (systemCa.isFile()) {
            env.put("SSL_CERT_FILE", systemCa.getCanonicalPath());
            env.put("SSL_CERT_DIR", new File(directory, "empty-ca-directory").getCanonicalPath());
        }
        for(String key:new ArrayList<>(env.keySet())) if(key.startsWith("DOTNET_") || key.startsWith("MONO_") || key.startsWith("CORECLR_") || key.startsWith("COMPlus_")) env.remove(key);
        env.put("LD_LIBRARY_PATH",nativeDir.getCanonicalPath()+":"+links.getCanonicalPath());
        env.put("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT","1"); env.put("DOTNET_MULTILEVEL_LOOKUP","0");
        env.put("DOTNET_CLI_TELEMETRY_OPTOUT","1"); env.put("DOTNET_CLI_HOME",new File(directory,"home").getPath());
        env.put("TMPDIR",getCacheDir().getPath());
        env.put("ROR2LAB_BUILD_DOTNET_ROOT",new File(directory,"dotnet").getPath());
        env.put("ROR2LAB_BUILD_HOSTFXR",hostfxr.getPath());
        env.put("ROR2LAB_BUILD_DOTNET_LAUNCHER",new File(nativeDir,"libdotnetmuxer.so").getPath());
        for(String key:new String[]{"JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","_JAVA_OPTIONS","JAVA_HOME","CLASSPATH"})env.remove(key);
        if(new File(nativeDir,"libjvm.so").isFile()) {
            env.put("ROR2LAB_BUILD_JVM",new File(nativeDir,"libjvm.so").getPath());
            env.put("ROR2LAB_BUILD_JAVA_HOME",new File(directory,"java").getPath());
        }
        java.lang.Process process=builder.start();
        if(!process.waitFor((label.equals("owner-backend") || label.equals("public-profile"))?86400:90,TimeUnit.SECONDS)){
            process.destroy();
            if(!process.waitFor(15,TimeUnit.SECONDS)) process.destroyForcibly();
            throw new IOException(label+" timeout");
        }
        JSONObject result=new JSONObject(); result.put("exit",process.exitValue());result.put("log",output.getName());result.put("sha256",hash(output));
        if(thermalReceipt.isFile()) result.put("thermal",new JSONObject(text(thermalReceipt)));
        if(process.exitValue()!=0) throw new IOException(label+" exit "+process.exitValue()+" "+text(output).substring(0,Math.min(2000,text(output).length())));
        return result;
    }
    private void executeFixture() { execute(null); }
    private void executeUpdate(String action) { execute(action); }
    private void execute(String updateAction) {
        JSONObject report=new JSONObject();
        try {
            report.put("schema",1);report.put("success",false);report.put("securityQualified",false);report.put("gameRuntimeChanged",false);
            report.put("selfContext",text(new File("/proc/self/attr/current")).trim());report.put("deviceApi",android.os.Build.VERSION.SDK_INT);report.put("targetSdk",getApplicationInfo().targetSdkVersion);
            File root=new File(getFilesDir(),"fixture-"+System.nanoTime()); if(root.exists())throw new IOException("fresh data directory required");
            copyAssets("",root);
            report.put("dataDirectory",root.getPath());
            JSONObject dataHashes=new JSONObject(text(new File(root,"data-hashes.json")));
            Iterator<String> dataNames=dataHashes.keys();int dataCount=0;
            while(dataNames.hasNext()) {String name=dataNames.next();File file=new File(root,name).getCanonicalFile();if(!file.getPath().startsWith(root.getCanonicalPath()+"/")||!file.isFile()||!hash(file).equals(dataHashes.getString(name)))throw new IOException("asset data drift "+name);dataCount++;}
            report.put("dataFilesVerified",dataCount);
            File nativeDir=new File(getApplicationInfo().nativeLibraryDir).getCanonicalFile();
            File runtime=new File(root,"dotnet");File framework=new File(runtime,"shared/Microsoft.NETCore.App/8.0.32");File links=new File(root,"native-links");links.mkdir();
            JSONObject hashes=new JSONObject(text(new File(root,"native-hashes.json")));
            JSONArray verified=new JSONArray();Iterator<String> names=hashes.keys();
            while(names.hasNext()){
                String name=names.next();File file=new File(nativeDir,name).getCanonicalFile();
                if(!file.getParentFile().equals(nativeDir)||!file.isFile()||file.canWrite()||!hash(file).equals(hashes.getString(name)))throw new IOException("native identity/read-only failure "+name);
                verified.put(name);
            }
            report.put("nativeVerified",verified);report.put("nativeDirectory",nativeDir.getPath());report.put("appUid",android.os.Process.myUid());
            hostfxr=new File(nativeDir,hashes.has("libhostfxr10.so")?"libhostfxr10.so":"libhostfxr.so");
            for(String name:new String[]{"libcoreclr.so","libhostpolicy.so","libSystem.Native.so","libSystem.Globalization.Native.so","libSystem.IO.Compression.Native.so","libSystem.Net.Security.Native.so","libSystem.Security.Cryptography.Native.Android.so","libSystem.Security.Cryptography.Native.OpenSsl.so"}) Os.symlink(new File(nativeDir,name).getPath(),new File(framework,name).getPath());
            Os.symlink(new File(nativeDir,"libcrypto.so").getPath(),new File(links,"libcrypto.so.3").getPath());
            Os.symlink(new File(nativeDir,"libssl.so").getPath(),new File(links,"libssl.so.3").getPath());
            JSONObject pythonLinks=new JSONObject(text(new File(root,"python-links.json")));
            Iterator<String> pythonNames=pythonLinks.keys();
            while(pythonNames.hasNext()){
                String name=pythonNames.next();File link=new File(root,name);File target=new File(nativeDir,pythonLinks.getString(name)).getCanonicalFile();
                if(name.startsWith("/") || name.contains("..") || !link.getParentFile().getCanonicalPath().startsWith(root.getCanonicalPath()+"/") || !target.getParentFile().equals(nativeDir) || !hashes.has(target.getName()))throw new IOException("native link boundary");
                link.getParentFile().mkdirs();
                if(link.exists()){if(!link.getCanonicalFile().equals(target))throw new IOException("existing native link differs");}
                else Os.symlink(target.getPath(),link.getPath());
            }
            if (updateAction != null) systemTrust(root);
            File ownerJob=new File(getFilesDir(), updateAction == null ? "owner-input/request.json" : "owner-input/update-request.json");
            if(ownerJob.isFile()) {
                List<String> backend=Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),new File(nativeDir,"libpython3.14.so").getPath(),new File(root,"python").getPath(),new File(root, OwnerUpdateState.backendScript(updateAction)).getPath(),ownerJob.getPath(),root.getPath(),nativeDir.getPath());
                report.put("ownerBackend",child("owner-backend",backend,root,nativeDir,links));
                File ready=new File(getFilesDir(),"owner-input/owner-apk-ready.json");
                JSONObject job=new JSONObject(text(ownerJob));
                if((job.has("signing")||job.has("packaging")||"release-build".equals(updateAction))&&ready.isFile()) {
                    JSONObject apk=new JSONObject(text(ready)); File file=new File(apk.getString("apk")).getCanonicalFile();
                    if(!file.getPath().startsWith(getFilesDir().getCanonicalPath()+"/")||!hash(file).equals(apk.getString("sha256")))throw new IOException("owner APK output drift");
                    report.put("ownerApk",apk);
                }
                report.put("success",true);
            } else {
            if (updateAction != null) throw new IOException("Explicit update request required");
            List<String> prefix=Arrays.asList(new File(nativeDir,"libtoolhost.so").getPath(),new File(nativeDir,"libhostfxr.so").getPath(),runtime.getPath());
            List<String> version=new ArrayList<>(prefix);version.add(new File(root,"compiler/csc.dll").getPath());version.add("-version");
            report.put("compilerVersion",child("version",version,root,nativeDir,links));
            List<String> compile=new ArrayList<>(prefix);compile.add(new File(root,"compiler/csc.dll").getPath());compile.addAll(Arrays.asList("/nologo","/noconfig","/nostdlib+","/target:exe","/out:"+new File(root,"Hello.dll").getPath()));
            File[] refs=new File(root,"refs").listFiles();Arrays.sort(refs);
            for(File reference:refs) if(reference.getName().endsWith(".dll"))compile.add("/r:"+reference.getPath());
            compile.add(new File(root,"Hello.cs").getPath());report.put("compile",child("compile",compile,root,nativeDir,links));
            List<String> run=new ArrayList<>(prefix);run.add(new File(root,"Hello.dll").getPath());report.put("run",child("run",run,root,nativeDir,links));
            if(!text(new File(root,"run.log")).contains("PHONE_TOOL_HOST_OK 8.0.32 "))throw new IOException("managed output marker missing");
            report.put("helloSha256",hash(new File(root,"Hello.dll")));report.put("success",true);
            report.put("success",false);
            List<String> python=Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),new File(nativeDir,"libpython3.14.so").getPath(),new File(root,"python").getPath(),new File(root,"run_profile.py").getPath(),root.getPath());
            report.put("publicProfileChild",child("public-profile",python,root,nativeDir,links));
            JSONObject pythonReport=new JSONObject(text(new File(root,"python-profile-report.json")));
            JSONObject publicReceipt=new JSONObject(text(new File(root,"repo/work/rebuild/app-component-v1/public-tools-receipt.json")));
            if(!pythonReport.getBoolean("success") || !publicReceipt.getBoolean("success") || publicReceipt.getBoolean("game_assemblies_executed"))throw new IOException("public producer contract differs");
            report.put("pythonProfile",pythonReport);report.put("publicReceipt",publicReceipt);report.put("success",true);
            }
        }catch(Exception error){
            try{report.put("failure",error.toString());}catch(Exception ignored){}
            if (updateAction != null) updateStatus(app, "ERROR", error.toString());
        }
        try {
            writeJson(new File(getFilesDir(), updateAction == null ? "tool-host-report.json" : "update-tool-report.json"), report);
            if ("release-build".equals(updateAction) && report.getBoolean("success") && report.has("ownerApk"))
                writeJson(new File(getFilesDir(), "tool-host-report.json"), report);
        } catch(Exception error) { if (updateAction != null) updateStatus(app, "ERROR", "Could not retain build result: " + error.getMessage()); }
    }
    }
}
