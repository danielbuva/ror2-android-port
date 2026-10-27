"""Execute the session installer against an authored Android package-manager double."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/managed-host/OwnerInstaller.java"
STATE_SOURCE = SOURCE.with_name("OwnerUpdateState.java")

STUBS = {
    "dev/ror2lab/phonebuildhostfixture/OwnerBuildService.java": """package dev.ror2lab.phonebuildhostfixture;public class OwnerBuildService {public static boolean isRunning(){return false;}public static void launch(android.content.Context c,String action){OwnerInstaller.finishVerification(c);}}""",
    "dev/ror2lab/phonebuildhostfixture/OwnerAlphaInstall.java": """package dev.ror2lab.phonebuildhostfixture; public class OwnerAlphaInstall {public static final String PACKAGE="dev.ror2lab.alpha";public static boolean pending(android.content.Context c){return false;}public static void prepare(android.content.Context c,java.io.File f,String h,android.content.pm.PackageInfo n,android.content.pm.PackageInfo o){}public static void complete(android.content.Context c,android.content.pm.PackageInfo p){}public static boolean recover(android.content.Context c){return false;}}""",
    "dev/ror2lab/phonebuildhostfixture/ToolHostActivity.java": """package dev.ror2lab.phonebuildhostfixture;
public class ToolHostActivity {public static String checkpointState;public static void updateInstallCheckpoint(android.content.Context c,String state,String message){checkpointState=state;}}""",
    "android/os/Build.java": "package android.os; public class Build { public static class VERSION { public static int SDK_INT=33; } }",
    "android/content/IntentSender.java": "package android.content; public class IntentSender {}",
    "android/content/Intent.java": """package android.content; public class Intent {
        public static final String EXTRA_INTENT="intent"; public static final int FLAG_ACTIVITY_NEW_TASK=1;
        public int code=1,session=7; public Intent confirmation; public Intent(){} public Intent(Context c,Class<?> t){}
        public Intent setAction(String a){return this;} public Intent addFlags(int f){return this;}
        public int getIntExtra(String k,int d){return k.equals("session")?session:code;} public String getStringExtra(String k){return "denied";}
        public Intent getParcelableExtra(String k){return confirmation;}
    }""",
    "android/content/BroadcastReceiver.java": "package android.content; public abstract class BroadcastReceiver {public abstract void onReceive(Context c,Intent i);}",
    "android/content/Context.java": """package android.content; import android.content.pm.*;
        public class Context {public PackageManager manager=new PackageManager(); public Intent started;
        public Prefs prefs=new Prefs(); public PackageManager getPackageManager(){return manager;}
        public String getPackageName(){return "authored.tool";} public Prefs getSharedPreferences(String s,int m){return prefs;}
        public void startActivity(Intent i){started=i;} public static class Prefs {java.util.Map<String,String> values=new java.util.HashMap<>();
        public String getString(String k,String d){return values.containsKey(k)?values.get(k):d;} public Prefs edit(){return this;}
        public Prefs putString(String k,String v){values.put(k,v);return this;} public boolean commit(){return true;}}
    }""",
    "android/app/PendingIntent.java": """package android.app; import android.content.*;
        public class PendingIntent {public static final int FLAG_UPDATE_CURRENT=1,FLAG_MUTABLE=2; public static int flags;
        public static PendingIntent getBroadcast(Context c,int id,Intent i,int f){flags=f;return new PendingIntent();}
        public IntentSender getIntentSender(){return new IntentSender();}}
    """,
    "android/content/pm/PackageInfo.java": """package android.content.pm; public class PackageInfo {
        public String packageName="authored.game"; public int versionCode=2; public Signature[] signatures={new Signature("same-key")};
        public long getLongVersionCode(){return versionCode;}}
    """,
    "android/content/pm/Signature.java": """package android.content.pm; public class Signature {
        private String text; public Signature(String s){text=s;} public byte[] toByteArray(){return text.getBytes(java.nio.charset.StandardCharsets.UTF_8);}
        public boolean equals(Object x){return x instanceof Signature && text.equals(((Signature)x).text);}}
    """,
    "android/content/pm/PackageManager.java": """package android.content.pm; public class PackageManager {
        public static final int GET_SIGNATURES=64; public PackageInfo next=new PackageInfo(),current;
        public PackageInstaller installer=new PackageInstaller(); public PackageInfo getPackageArchiveInfo(String p,int f){return next;}
        public PackageInfo getPackageInfo(String p,int f) throws NameNotFoundException {if(current==null)throw new NameNotFoundException();return current;}
        public PackageInstaller getPackageInstaller(){return installer;} public static class NameNotFoundException extends Exception {}}
    """,
    "android/content/pm/PackageInstaller.java": """package android.content.pm; import java.io.*; import android.content.*;
        public class PackageInstaller {public static final String EXTRA_STATUS="status",EXTRA_STATUS_MESSAGE="message",EXTRA_SESSION_ID="session";
        public static final int STATUS_FAILURE=1,STATUS_SUCCESS=0,STATUS_PENDING_USER_ACTION=-1;
        public SessionParams params; public Session session=new Session(); public boolean abandoned,fail; public SessionInfo info=new SessionInfo();
        public SessionInfo getSessionInfo(int id){return info;}
        public static class SessionInfo {public boolean sealed=true; public boolean isSealed(){return sealed;}}
        public int createSession(SessionParams p){params=p;return 7;} public Session openSession(int id) throws IOException {
        if(fail)throw new IOException("open failed");return session;} public void abandonSession(int id){abandoned=true;}
        public static class SessionParams {public static final int MODE_FULL_INSTALL=1,USER_ACTION_NOT_REQUIRED=2;
        public int action,mode; public String name; public long size; public SessionParams(int m){mode=m;}
        public void setAppPackageName(String n){name=n;} public void setSize(long s){size=s;} public void setRequireUserAction(int a){action=a;}}
        public static class Session implements AutoCloseable {public boolean committed,synced,closed,writeFail,syncFail,commitFail;
        public ByteArrayOutputStream bytes=new ByteArrayOutputStream(); public OutputStream openWrite(String n,long o,long s) throws IOException {
        if(writeFail)throw new IOException("write failed");return bytes;}
        public void fsync(OutputStream o) throws IOException {if(syncFail)throw new IOException("sync failed");synced=true;}
        public void commit(IntentSender s){if(commitFail)throw new IllegalStateException("commit failed");committed=true;}
        public void close(){closed=true;}}
    }""",
}

HARNESS = r"""
import android.content.*;
import android.content.pm.*;
import android.os.Build;
import dev.ror2lab.phonebuildhostfixture.OwnerInstaller;
import dev.ror2lab.phonebuildhostfixture.OwnerUpdateState;
import dev.ror2lab.phonebuildhostfixture.ToolHostActivity;
import java.io.*;
import java.nio.file.*;
import java.security.*;

public class Harness {
    static void check(boolean ok) {if(!ok)throw new AssertionError();}
    static Context update() {Context c=new Context();c.manager.current=new PackageInfo();c.manager.current.versionCode=1;return c;}
    static void refusal(Context c,File apk,String hash,String expected) throws Exception {
        try {OwnerInstaller.install(c,apk,hash);throw new AssertionError("accepted "+expected);}
        catch(IOException e){check(e.getMessage().contains(expected));}
        check(!c.manager.installer.session.committed);
    }
    public static void main(String[] args) throws Exception {
        File apk=new File(args[0]); byte[] bytes="authored APK stream".getBytes("UTF-8");Files.write(apk.toPath(),bytes);
        StringBuilder digest=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))digest.append(String.format("%02x",b&255));
        String hash=digest.toString(); Context c=new Context(); OwnerInstaller.install(c,apk,hash);
        check(c.manager.installer.session.committed && c.manager.installer.session.synced && c.manager.installer.session.closed);
        check(java.util.Arrays.equals(bytes,c.manager.installer.session.bytes.toByteArray()));
        check(c.manager.installer.params.mode==PackageInstaller.SessionParams.MODE_FULL_INSTALL && c.manager.installer.params.action==0);
        c=update();OwnerInstaller.install(c,apk,hash);check(c.manager.installer.params.action==2);
        check((android.app.PendingIntent.flags&android.app.PendingIntent.FLAG_MUTABLE)!=0);
        Build.VERSION.SDK_INT=30;c=update();OwnerInstaller.install(c,apk,hash);check(c.manager.installer.params.action==0);Build.VERSION.SDK_INT=33;
        c=update();c.manager.next.versionCode=1;refusal(c,apk,hash,"version");check(c.manager.installer.params==null);
        c=update();c.manager.next.signatures=new android.content.pm.Signature[]{new android.content.pm.Signature("lost-key")};refusal(c,apk,hash,"signing key");check(c.manager.installer.params==null);
        c=new Context();refusal(c,apk,"wrong","drift");check(c.manager.installer.abandoned);
        c=new Context();c.manager.installer.fail=true;refusal(c,apk,hash,"open failed");check(c.manager.installer.abandoned);
        c=new Context();c.manager.installer.session.writeFail=true;refusal(c,apk,hash,"write failed");check(c.manager.installer.abandoned);
        c=new Context();c.manager.installer.session.syncFail=true;refusal(c,apk,hash,"sync failed");check(c.manager.installer.abandoned);
        c=new Context();c.manager.installer.session.commitFail=true;
        try {OwnerInstaller.install(c,apk,hash);throw new AssertionError();}catch(IllegalStateException expected){}
        check(c.manager.installer.abandoned && OwnerInstaller.state(c).equals("ERROR"));
        c=new Context();try {OwnerInstaller.install(c,apk,hash,"wrong.package",2);throw new AssertionError();}catch(IOException expected){}
        check(c.manager.installer.params==null);
        c=new Context();try {OwnerInstaller.install(c,apk,hash,"authored.game",3);throw new AssertionError();}catch(IOException expected){}
        check(c.manager.installer.params==null);
        OwnerInstaller.Result receiver=new OwnerInstaller.Result();c=new Context();OwnerInstaller.install(c,apk,hash,"authored.game",2);
        try {OwnerInstaller.install(c,apk,hash);throw new AssertionError();}catch(IOException expected){check(expected.getMessage().contains("already pending"));}
        Intent i=new Intent();i.code=-1;i.confirmation=new Intent();
        i.session=99;receiver.onReceive(c,i);check(c.started==null);i.session=7;
        receiver.onReceive(c,i);check(c.started==i.confirmation && OwnerInstaller.status(c).contains("Confirm"));
        check(OwnerInstaller.busy(c));c.manager.current=new PackageInfo();
        i.code=0;receiver.onReceive(c,i);check(OwnerInstaller.status(c).contains("complete"));
        check(!OwnerInstaller.busy(c) && OwnerInstaller.state(c).equals("INSTALLED"));
        c.manager.current.versionCode=1;receiver.onReceive(c,i);check(OwnerInstaller.state(c).equals("ERROR"));
        i.code=1;receiver.onReceive(c,i);check(OwnerInstaller.status(c).contains("denied"));
        OwnerInstaller.clearTerminalStatus(c);check(OwnerInstaller.state(c).equals("IDLE"));
        i.code=0;receiver.onReceive(c,i);check(OwnerInstaller.state(c).equals("IDLE"));
        c=new Context();OwnerInstaller.install(c,apk,hash);c.manager.installer.info.sealed=false;
        OwnerInstaller.reconcile(c);check(c.manager.installer.abandoned && OwnerInstaller.state(c).equals("ERROR"));
        c=new Context();OwnerInstaller.install(c,apk,hash);c.manager.installer.info=null;c.manager.current=new PackageInfo();
        OwnerInstaller.reconcile(c);check(OwnerInstaller.state(c).equals("INSTALLED"));check(ToolHostActivity.checkpointState.equals("INSTALLED"));
        c=new Context();OwnerInstaller.install(c,apk,hash);c.manager.installer.info=null;
        OwnerInstaller.reconcile(c);check(OwnerInstaller.state(c).equals("ERROR"));
        c=new Context();OwnerInstaller.install(c,apk,hash);i=new Intent();i.code=-1;
        receiver.onReceive(c,i);check(OwnerInstaller.state(c).equals("AWAITING_CONFIRMATION") && c.started==null);
        OwnerUpdateState state=new OwnerUpdateState();check(state.canCheck() && !state.canBuild() && !state.canInstall());
        state.beginCheck();check(state.busy() && !state.canCheck());
        try {state.beginCheck();throw new AssertionError();}catch(IllegalStateException expected){}
        state.observe("UP_TO_DATE","Current");check(state.canCheck() && !state.canBuild());
        state.observe("UPDATE_AVAILABLE","New");check(state.canBuild());state.beginBuild();check(state.busy());
        for(String phase:new String[]{"VERIFYING","BUILDING","SIGNING"}){state.observe(phase,phase);check(state.busy() && !state.canInstall());}
        state.observe("READY","Ready");check(state.canInstall());state.beginInstall();check(state.busy());
        state.observe("AWAITING_CONFIRMATION","Confirm");check(state.busy());state.observe("INSTALLED","Done");check(state.canCheck());
        state.observe("ERROR","Denied");check(state.canCheck());state.observe("unknown",null);check(state.phase()==OwnerUpdateState.Phase.ERROR);
        check(OwnerUpdateState.backendScript(null).endsWith("owner-code/run_android.py"));
        check(OwnerUpdateState.backendScript("release-check").endsWith("owner-apk/updates.py"));
        check(OwnerUpdateState.backendScript("release-build").endsWith("owner-apk/updates.py"));
        try {OwnerUpdateState.backendScript("install");throw new AssertionError();}catch(IllegalArgumentException expected){}
        System.out.println("session install/update/hash/key/version/callback contracts PASS");
    }
}
"""


class OwnerInstallerTests(unittest.TestCase):
    def test_activity_has_only_explicit_actions_and_observes_async_status(self):
        activity = SOURCE.with_name("ToolHostActivity.java").read_text()
        ui = activity[: activity.index("public static class Runner")]
        self.assertNotIn("executeFixture()", ui)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", ui)
        self.assertIn('startUpdate("release-check")', ui)
        self.assertIn('startUpdate("release-build")', ui)
        self.assertIn("OwnerInstaller.install(app, apk", ui)
        self.assertIn("registerOnSharedPreferenceChangeListener(installObserver)", ui)
        self.assertIn("unregisterOnSharedPreferenceChangeListener(installObserver)", ui)
        self.assertIn("handler.removeCallbacks(refresh)", ui)
        self.assertIn("OwnerInstaller.reconcile(this)", ui)
        self.assertIn("OwnerUpdateState.backendScript(updateAction)", activity)
        self.assertIn("factory.init((java.security.KeyStore) null)", activity)
        self.assertIn("getAcceptedIssuers()", activity)
        self.assertIn('env.put("SSL_CERT_FILE", systemCa.getCanonicalPath())', activity)
        self.assertIn('env.put("SSL_CERT_DIR", new File(directory, "empty-ca-directory").getCanonicalPath())', activity)
        self.assertNotIn("setDefaultHostnameVerifier", activity)
        self.assertNotIn("checkServerTrusted", activity)

    def test_session_lifecycle(self):
        home = Path("/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer/OpenJDK")
        compiler = home / "bin/javac"
        if not compiler.is_file():
            compiler = Path(os.environ.get("JAVA_HOME", "/absent")) / "bin/javac"
        if not compiler.is_file():
            found = shutil.which("javac")
            if not found:
                self.skipTest("Java compiler absent")
            compiler = Path(found)
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
            compiled = subprocess.run([str(compiler), "-d", str(root), *paths, str(SOURCE), str(STATE_SOURCE), str(harness)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run(
                [str(compiler.with_name("java")), "-cp", str(root), "Harness", str(root / "owner-stream.bin")], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("contracts PASS", result.stdout)
