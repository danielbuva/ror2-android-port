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
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        final TextView view = new TextView(this); view.setText("Private build-tool host test");
        final Button install = new Button(this); install.setText("Install owner-built APK"); install.setEnabled(false);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); layout.addView(view); layout.addView(install); setContentView(layout);
        final Runnable ready = new Runnable() { public void run() {
            try {
                File apk=readyApk(ToolHostActivity.this);
                android.content.pm.PackageInfo info=getPackageManager().getPackageArchiveInfo(apk.getPath(),0);
                if(info==null)throw new IOException("APK manifest unavailable");
                view.setText("Owner-built APK ready: "+info.packageName+" ("+info.versionName+")"); install.setEnabled(true);
            } catch(Exception error) { view.setText("Build result: "+error.getMessage()); }
        }};
        install.setOnClickListener(new android.view.View.OnClickListener() { public void onClick(android.view.View ignored) {
            try {
                readyApk(ToolHostActivity.this);
                if(android.os.Build.VERSION.SDK_INT>=26 && !getPackageManager().canRequestPackageInstalls()) {
                    startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+getPackageName()))); return;
                }
                Intent intent=new Intent(Intent.ACTION_INSTALL_PACKAGE,Uri.parse("content://"+getPackageName()+".apk/owner.apk"));
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION); startActivity(intent);
            }catch(Exception error){view.setText("Installer unavailable: "+error.getMessage());}
        }});
        try { readyApk(this); ready.run(); }
        catch(Exception missing) {
            new Thread(new Runnable() { public void run() { new Worker(ToolHostActivity.this).executeFixture(); runOnUiThread(ready); } }).start();
        }
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
    private JSONObject child(String label, List<String> arguments, File directory, File nativeDir, File links) throws Exception {
        File output=new File(directory,label+".log");
        ProcessBuilder builder=new ProcessBuilder(arguments).directory(directory).redirectErrorStream(true).redirectOutput(output);
        Map<String,String> env=builder.environment();
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
        if(!process.waitFor(label.equals("owner-backend")?86400:90,TimeUnit.SECONDS)){
            process.destroy();
            if(!process.waitFor(15,TimeUnit.SECONDS)) process.destroyForcibly();
            throw new IOException(label+" timeout");
        }
        JSONObject result=new JSONObject(); result.put("exit",process.exitValue());result.put("log",output.getName());result.put("sha256",hash(output));
        if(process.exitValue()!=0) throw new IOException(label+" exit "+process.exitValue()+" "+text(output).substring(0,Math.min(2000,text(output).length())));
        return result;
    }
    private void executeFixture() {
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
            File ownerJob=new File(getFilesDir(),"owner-input/request.json");
            if(ownerJob.isFile()) {
                List<String> backend=Arrays.asList(new File(nativeDir,"libpythonhost.so").getPath(),new File(nativeDir,"libpython3.14.so").getPath(),new File(root,"python").getPath(),new File(root,"repo/tools/phone-build/owner-code/run_android.py").getPath(),ownerJob.getPath(),root.getPath(),nativeDir.getPath());
                report.put("ownerBackend",child("owner-backend",backend,root,nativeDir,links));
                File ready=new File(getFilesDir(),"owner-input/owner-apk-ready.json");
                JSONObject job=new JSONObject(text(ownerJob));
                if((job.has("signing")||job.has("packaging"))&&ready.isFile()) {
                    JSONObject apk=new JSONObject(text(ready)); File file=new File(apk.getString("apk")).getCanonicalFile();
                    if(!file.getPath().startsWith(getFilesDir().getCanonicalPath()+"/")||!hash(file).equals(apk.getString("sha256")))throw new IOException("owner APK output drift");
                    report.put("ownerApk",apk);
                }
                report.put("success",true);
            } else {
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
        }catch(Exception error){try{report.put("failure",error.toString());}catch(Exception ignored){}}
        try(FileOutputStream output=new FileOutputStream(new File(getFilesDir(),"tool-host-report.json"))){output.write(report.toString(2).getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){}
    }
    }
}
