"""Execute the session installer against an authored Android package-manager double."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/managed-host/OwnerInstaller.java"

STUBS = {
    "android/os/Build.java": "package android.os; public class Build { public static class VERSION { public static int SDK_INT=33; } }",
    "android/content/IntentSender.java": "package android.content; public class IntentSender {}",
    "android/content/Intent.java": """package android.content; public class Intent {
        public static final String EXTRA_INTENT="intent"; public static final int FLAG_ACTIVITY_NEW_TASK=1;
        public int code=1; public Intent confirmation; public Intent(){} public Intent(Context c,Class<?> t){}
        public Intent setAction(String a){return this;} public Intent addFlags(int f){return this;}
        public int getIntExtra(String k,int d){return code;} public String getStringExtra(String k){return "denied";}
        public Intent getParcelableExtra(String k){return confirmation;}
    }""",
    "android/content/BroadcastReceiver.java": "package android.content; public abstract class BroadcastReceiver {public abstract void onReceive(Context c,Intent i);}",
    "android/content/Context.java": """package android.content; import android.content.pm.*;
        public class Context {public PackageManager manager=new PackageManager(); public Intent started;
        public Prefs prefs=new Prefs(); public PackageManager getPackageManager(){return manager;}
        public String getPackageName(){return "authored.tool";} public Prefs getSharedPreferences(String s,int m){return prefs;}
        public void startActivity(Intent i){started=i;} public static class Prefs {String text="";
        public String getString(String k,String d){return text;} public Prefs edit(){return this;}
        public Prefs putString(String k,String v){text=v;return this;} public boolean commit(){return true;}}
    }""",
    "android/app/PendingIntent.java": """package android.app; import android.content.*;
        public class PendingIntent {public static final int FLAG_UPDATE_CURRENT=1,FLAG_MUTABLE=2; public static int flags;
        public static PendingIntent getBroadcast(Context c,int id,Intent i,int f){flags=f;return new PendingIntent();}
        public IntentSender getIntentSender(){return new IntentSender();}}
    """,
    "android/content/pm/PackageInfo.java": """package android.content.pm; public class PackageInfo {
        public String packageName="authored.game"; public int versionCode=2; public String[] signatures={"same-key"};
        public long getLongVersionCode(){return versionCode;}}
    """,
    "android/content/pm/PackageManager.java": """package android.content.pm; public class PackageManager {
        public static final int GET_SIGNATURES=64; public PackageInfo next=new PackageInfo(),current;
        public PackageInstaller installer=new PackageInstaller(); public PackageInfo getPackageArchiveInfo(String p,int f){return next;}
        public PackageInfo getPackageInfo(String p,int f) throws NameNotFoundException {if(current==null)throw new NameNotFoundException();return current;}
        public PackageInstaller getPackageInstaller(){return installer;} public static class NameNotFoundException extends Exception {}}
    """,
    "android/content/pm/PackageInstaller.java": """package android.content.pm; import java.io.*; import android.content.*;
        public class PackageInstaller {public static final String EXTRA_STATUS="status",EXTRA_STATUS_MESSAGE="message";
        public static final int STATUS_FAILURE=1,STATUS_SUCCESS=0,STATUS_PENDING_USER_ACTION=-1;
        public SessionParams params; public Session session=new Session(); public boolean abandoned,fail;
        public int createSession(SessionParams p){params=p;return 7;} public Session openSession(int id) throws IOException {
        if(fail)throw new IOException("open failed");return session;} public void abandonSession(int id){abandoned=true;}
        public static class SessionParams {public static final int MODE_FULL_INSTALL=1,USER_ACTION_NOT_REQUIRED=2;
        public int action,mode; public String name; public long size; public SessionParams(int m){mode=m;}
        public void setAppPackageName(String n){name=n;} public void setSize(long s){size=s;} public void setRequireUserAction(int a){action=a;}}
        public static class Session implements AutoCloseable {public boolean committed,synced,closed;
        public ByteArrayOutputStream bytes=new ByteArrayOutputStream(); public OutputStream openWrite(String n,long o,long s){return bytes;}
        public void fsync(OutputStream o){synced=true;} public void commit(IntentSender s){committed=true;}
        public void close(){closed=true;}}
    }""",
}

HARNESS = r"""
import android.content.*;
import android.content.pm.*;
import android.os.Build;
import dev.ror2lab.phonebuildhostfixture.OwnerInstaller;
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
        c=update();c.manager.next.signatures=new String[]{"lost-key"};refusal(c,apk,hash,"signing key");check(c.manager.installer.params==null);
        c=new Context();refusal(c,apk,"wrong","drift");check(c.manager.installer.abandoned);
        c=new Context();c.manager.installer.fail=true;refusal(c,apk,hash,"open failed");check(c.manager.installer.abandoned);
        OwnerInstaller.Result receiver=new OwnerInstaller.Result();c=new Context();Intent i=new Intent();i.code=-1;i.confirmation=new Intent();
        receiver.onReceive(c,i);check(c.started==i.confirmation && OwnerInstaller.status(c).contains("Confirm"));
        i.code=0;receiver.onReceive(c,i);check(OwnerInstaller.status(c).contains("complete"));
        i.code=1;receiver.onReceive(c,i);check(OwnerInstaller.status(c).contains("denied"));
        System.out.println("session install/update/hash/key/version/callback contracts PASS");
    }
}
"""


class OwnerInstallerTests(unittest.TestCase):
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
            subprocess.run([str(compiler), "-d", str(root), *paths, str(SOURCE), str(harness)], check=True, capture_output=True)
            result = subprocess.run([str(compiler.with_name("java")), "-cp", str(root), "Harness", str(root / "owner.apk")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("contracts PASS", result.stdout)
