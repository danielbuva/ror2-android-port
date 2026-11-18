"""Run the actual foreground-service owner with synthetic Android lifecycle doubles."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/managed-host/OwnerBuildService.java"
PACKAGE = "dev/ror2lab/phonebuildhostfixture/"
STUBS = {
    "android/R.java": "package android; public class R { public static class drawable {public static int stat_sys_download=1;} }",
    "android/os/IBinder.java": "package android.os; public interface IBinder {}",
    "android/os/Build.java": "package android.os; public class Build {public static class VERSION {public static int SDK_INT=33;}}",
    "android/os/Looper.java": "package android.os; public class Looper {public static Looper getMainLooper(){return new Looper();}}",
    "android/os/Handler.java": """package android.os; import java.util.concurrent.*; public class Handler {
public static final BlockingQueue<Runnable> queue=new LinkedBlockingQueue<>(); public Handler(Looper l){}
public boolean post(Runnable r){queue.add(r);return true;} public boolean postDelayed(Runnable r,long n){return true;}
public void removeCallbacks(Runnable r){queue.remove(r);} }""",
    "android/os/SystemClock.java": "package android.os; public class SystemClock {public static long elapsedRealtime(){return 0;}}",
    "android/os/BatteryManager.java": """package android.os; public class BatteryManager {public static String EXTRA_TEMPERATURE="temperature",EXTRA_LEVEL="level",EXTRA_SCALE="scale",EXTRA_STATUS="status";public static int BATTERY_STATUS_CHARGING=2;}""",
    "android/os/PowerManager.java": """package android.os; public class PowerManager {public static int PARTIAL_WAKE_LOCK=1; public final WakeLock lock=new WakeLock(); public WakeLock newWakeLock(int n,String s){return lock;} public static class WakeLock {public boolean held; public void acquire(){held=true;}public boolean isHeld(){return held;}public void release(){held=false;}}}""",
    "android/content/IntentFilter.java": "package android.content;public class IntentFilter {public IntentFilter(String s){}}",
    "android/content/Intent.java": """package android.content;public class Intent {public static String ACTION_BATTERY_CHANGED="battery";String action;public Intent(){}public Intent(Context c,Class<?> k){}public Intent setAction(String a){action=a;return this;}public String getAction(){return action;}public int getIntExtra(String k,int d){return k.equals("temperature")?250:k.equals("level")?50:k.equals("scale")?100:3;}}""",
    "android/content/SharedPreferences.java": """package android.content;import java.util.*;public class SharedPreferences {public Map<String,Object> data=new HashMap<>();public String getString(String k,String d){return (String)data.getOrDefault(k,d);}public Editor edit(){return new Editor();}public class Editor {public Editor putString(String k,String v){data.put(k,v);return this;}public Editor putBoolean(String k,boolean v){data.put(k,v);return this;}public boolean commit(){return true;}}}""",
    "android/content/pm/PackageManager.java": "package android.content.pm;public class PackageManager {public boolean canRequestPackageInstalls(){return true;}}",
    "android/content/Context.java": """package android.content;import java.io.*;import android.app.*;import android.os.*;public class Context {
public static String NOTIFICATION_SERVICE="notification",POWER_SERVICE="power";public static File root;public static int starts;public static boolean launchFail;
public static SharedPreferences prefs=new SharedPreferences();public final PowerManager power=new PowerManager();
public SharedPreferences getSharedPreferences(String n,int m){return prefs;}public Object getSystemService(String n){return n.equals(POWER_SERVICE)?power:new NotificationManager();}
public void startService(Intent i){if(launchFail)throw new IllegalStateException("launch failed");starts++;}public void startForegroundService(Intent i){startService(i);}
public File getFilesDir(){return root;}public String getPackageName(){return "synthetic";}public Context getApplicationContext(){return this;}
public android.content.pm.PackageManager getPackageManager(){return new android.content.pm.PackageManager();}public Intent registerReceiver(Object o,IntentFilter f){return new Intent();}}""",
    "android/app/Service.java": """package android.app;import android.content.*;import android.os.*;public class Service extends Context {public static int START_NOT_STICKY=2;public int stops;public boolean foreground,foregroundFail;
public IBinder onBind(Intent i){return null;}public void onCreate(){}public void onDestroy(){}public int onStartCommand(Intent i,int f,int id){return 2;}
public void startForeground(int id,Notification n){if(foregroundFail)throw new IllegalStateException("foreground failed");foreground=true;}public void stopForeground(boolean b){foreground=false;}public void stopSelf(){stops++;}public void stopSelf(int n){stops++;}}""",
    "android/app/NotificationChannel.java": "package android.app;public class NotificationChannel {public NotificationChannel(String a,String b,int c){}}",
    "android/app/NotificationManager.java": "package android.app;public class NotificationManager {public static int IMPORTANCE_LOW=1;public void notify(int n,Notification x){}public void createNotificationChannel(NotificationChannel c){}}",
    "android/app/PendingIntent.java": """package android.app;import android.content.*;public class PendingIntent {public static int FLAG_UPDATE_CURRENT=1,FLAG_IMMUTABLE=2;public static PendingIntent getService(Context c,int n,Intent i,int f){return new PendingIntent();}public static PendingIntent getActivity(Context c,int n,Intent i,int f){return new PendingIntent();}}""",
    "android/app/Notification.java": """package android.app;import android.content.*;public class Notification {public static class Builder {public Builder(Context c){}public Builder(Context c,String s){}public Builder setSmallIcon(int x){return this;}public Builder setContentTitle(String s){return this;}public Builder setContentText(String s){return this;}public Builder setContentIntent(PendingIntent p){return this;}public Builder setOngoing(boolean b){return this;}public Builder setOnlyAlertOnce(boolean b){return this;}public Builder addAction(Action a){return this;}public Notification build(){return new Notification();}}public static class Action {public static class Builder {public Builder(Object a,String b,PendingIntent c){}public Action build(){return new Action();}}}}""",
    "org/json/JSONObject.java": """package org.json;import java.util.*;public class JSONObject {Map<String,Object> data=new HashMap<>();public JSONObject put(String k,Object v){data.put(k,v);return this;}public String optString(String k){return optString(k,"");}public String optString(String k,String d){return String.valueOf(data.getOrDefault(k,d));}}""",
    PACKAGE
    + "OwnerInstaller.java": """package dev.ror2lab.phonebuildhostfixture;import android.content.*;public class OwnerInstaller {public static boolean busy;public static int verifies;public static boolean busy(Context c){return busy;}public static String state(Context c){return "AWAITING_CONFIRMATION";}public static void finishVerification(Context c){verifies++;busy=false;}public static void recoverProfiles(Context c){verifies++;OwnerAlphaInstall.pending=false;}}""",
    PACKAGE
    + "OwnerAlphaInstall.java": "package dev.ror2lab.phonebuildhostfixture;import android.content.*;public class OwnerAlphaInstall {public static boolean pending;public static boolean pending(Context c){return pending;}}",
    PACKAGE
    + "OwnerInputImport.java": "package dev.ror2lab.phonebuildhostfixture;public class OwnerInputImport {public interface Observer {void checkpoint() throws Exception;void progress(String p,long c,long t) throws Exception;}}",
    PACKAGE
    + "OwnerInputSource.java": """package dev.ror2lab.phonebuildhostfixture;import android.content.*;public class OwnerInputSource {public static class Access {public void cancel(){}}public static void run(Context c,OwnerInputImport.Observer o,Access a)throws Exception{o.checkpoint();}}""",
    PACKAGE
    + "ToolHostActivity.java": """package dev.ror2lab.phonebuildhostfixture;import android.content.*;import java.io.*;import java.util.concurrent.*;import org.json.*;public class ToolHostActivity {
public static String status;public static int controls,installs;public static JSONObject readJson(File f){return new JSONObject().put("state",status);}public static void writeJson(Context c,File f,JSONObject j){controls++;}public static void updateStatus(Context c,String s,String m){status=s;}public static void installPrepared(Context c){installs++;}
public static class Worker {public static volatile int executions,cancels;public static CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);Context context;public Worker(Context c){context=c;}public void executeUpdate(String a)throws Exception {executions++;entered.countDown();release.await();if("release-build".equals(a)){File f=new File(context.getFilesDir(),"owner-input/update-state.json");f.getParentFile().mkdirs();f.createNewFile();status="READY";}}public void cancel(){cancels++;}}}""",
}
HARNESS = r"""
import dev.ror2lab.phonebuildhostfixture.*;import android.content.*;import android.os.*;import java.io.*;import java.util.concurrent.*;
public class Harness {
static void check(boolean b){if(!b)throw new AssertionError();}
static Intent action(String s){return new Intent().setAction(s);}
static void finish()throws Exception{long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);while(OwnerBuildService.isRunning()&&System.nanoTime()<end){Runnable r=Handler.queue.poll(50,TimeUnit.MILLISECONDS);if(r!=null)r.run();}check(!OwnerBuildService.isRunning());}
public static void main(String[] args)throws Exception {
Context.root=new File(args[0]);Context.root.mkdirs();Context c=new Context();
Context.launchFail=true;try{OwnerBuildService.launch(c,"release-check");throw new AssertionError();}catch(IllegalStateException ok){}check(!OwnerBuildService.isRunning());Context.launchFail=false;
OwnerBuildService.launch(c,"release-check");OwnerBuildService.launch(c,"release-check");check(Context.starts==1&&OwnerBuildService.isRunning());
OwnerBuildService service=new OwnerBuildService();service.onCreate();service.onStartCommand(action("release-check"),0,1);check(ToolHostActivity.Worker.entered.await(5,TimeUnit.SECONDS));
service.onStartCommand(action("release-check"),0,2);OwnerBuildService.launch(c,"release-build");check(ToolHostActivity.Worker.executions==1&&Context.starts==1);
OwnerInstaller.busy=true;service.onStartCommand(action("control-cancel"),0,3);check(ToolHostActivity.Worker.cancels==0&&ToolHostActivity.controls==0);OwnerInstaller.busy=false;
service.onStartCommand(action("control-cancel"),0,4);check(ToolHostActivity.Worker.cancels==1);service.onDestroy();check(!service.power.lock.isHeld());
ToolHostActivity.Worker.release.countDown();finish();check(!service.foreground);check(Boolean.TRUE.equals(Context.prefs.data.get("interrupted")));
OwnerBuildService recreated=new OwnerBuildService();recreated.onCreate();recreated.onStartCommand(null,0,5);check(!OwnerBuildService.isRunning()&&ToolHostActivity.Worker.executions==1);
OwnerAlphaInstall.pending=true;recreated.onStartCommand(action("release-build"),0,6);check(!OwnerBuildService.isRunning()&&ToolHostActivity.Worker.executions==1);
recreated.onStartCommand(action("profile-recover"),0,7);finish();check(OwnerInstaller.verifies==1&&!OwnerAlphaInstall.pending);
OwnerBuildService failed=new OwnerBuildService();failed.foregroundFail=true;try{failed.onStartCommand(action("release-check"),0,8);}catch(IllegalStateException ok){}check(!OwnerBuildService.isRunning());check(!failed.power.lock.isHeld());
OwnerBuildService.launch(c,"release-check");OwnerBuildService retry=new OwnerBuildService();retry.onStartCommand(action("release-check"),0,9);finish();check(ToolHostActivity.Worker.executions==2);
ToolHostActivity.Worker.entered=new CountDownLatch(1);ToolHostActivity.Worker.release=new CountDownLatch(1);
OwnerBuildService late=new OwnerBuildService();late.onStartCommand(action("release-build"),0,10);check(ToolHostActivity.Worker.entered.await(5,TimeUnit.SECONDS));
late.onStartCommand(action("control-cancel"),0,11);ToolHostActivity.Worker.release.countDown();finish();
check("CANCELLED".equals(ToolHostActivity.status)&&ToolHostActivity.installs==0);
OwnerBuildService resumed=new OwnerBuildService();resumed.onStartCommand(action("release-build"),0,12);finish();check(ToolHostActivity.installs==1);
System.out.println("single-flight lifecycle PASS");
}}
"""


class OwnerBuildServiceTests(unittest.TestCase):
    def test_actual_service_lifecycle(self):
        java = shutil.which("java")
        compiler = shutil.which("javac")
        if not java:
            self.skipTest("Java runtime absent")
        compile_command = [compiler] if compiler else [java, "com.sun.tools.javac.Main"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for name, text in STUBS.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                paths.append(str(path))
            harness = root / "Harness.java"
            harness.write_text(HARNESS)
            compiled = subprocess.run([*compile_command, "-d", str(root), *paths, str(SOURCE), str(harness)], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            run = subprocess.run([java, "-cp", str(root), "Harness", str(root / "files")], capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("single-flight lifecycle PASS", run.stdout)
