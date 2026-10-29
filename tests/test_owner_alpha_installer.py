"""Execute real alpha admission/receipt/provider orchestration using synthetic data only."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_owner_installer import STUBS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/managed-host"

EXTRA = {
    "org/json/JSONObject.java": """package org.json; import java.util.*; public class JSONObject {
        private Map<String,Object> values=new HashMap<>(); public JSONObject put(String k,Object v){values.put(k,v);return this;}
        public Object get(String k){if(!values.containsKey(k))throw new IllegalArgumentException("missing "+k);return values.get(k);}
        public boolean getBoolean(String k){return (Boolean)get(k);} public String getString(String k){return (String)get(k);} public long getLong(String k){return ((Number)get(k)).longValue();}
        public long optLong(String k,long d){return has(k)?getLong(k):d;} public int getInt(String k){return ((Number)get(k)).intValue();} public JSONObject getJSONObject(String k){return (JSONObject)get(k);}
        public JSONArray getJSONArray(String k){return (JSONArray)get(k);} public boolean has(String k){return values.containsKey(k);}
        public String optString(String k){return optString(k,"");} public String optString(String k,String d){return has(k)?getString(k):d;}
    }""",
    "org/json/JSONArray.java": """package org.json; public class JSONArray {private java.util.List<Integer> values=new java.util.ArrayList<>();
        public JSONArray put(int v){values.add(v);return this;} public int length(){return values.size();} public int getInt(int i){return values.get(i);}}""",
    "android/net/Uri.java": """package android.net; public class Uri {public String text;public static Uri parse(String v){Uri u=new Uri();u.text=v;return u;}}""",
    "android/os/Bundle.java": """package android.os; public class Bundle {private java.util.Map<String,Object> values=new java.util.HashMap<>();
        public void putBoolean(String k,boolean v){values.put(k,v);} public void putInt(String k,int v){values.put(k,v);} public void putString(String k,String v){values.put(k,v);}
        public long getLong(String k,long d){return values.containsKey(k)?((Number)values.get(k)).longValue():d;} public String getString(String k){return (String)values.get(k);} public int getInt(String k,int d){return values.containsKey(k)?(Integer)values.get(k):d;}}""",
    "android/content/ContentResolver.java": """package android.content; import android.os.Bundle; import android.net.Uri;
        public class ContentResolver {public java.util.List<String> calls=new java.util.ArrayList<>();public boolean mismatch,restoreFail,snapshotFail,released;
        public Bundle call(Uri uri,String method,String arg,Bundle extras){
            if(!uri.text.equals("content://dev.ror2lab.alpha.retention"))throw new AssertionError();calls.add(method);
            if((method.equals("verify")&&mismatch)||(method.equals("restore")&&restoreFail)||(method.equals("snapshot")&&snapshotFail))throw new IllegalStateException("synthetic refusal");
            if(method.equals("restore")&&released)throw new IllegalStateException("inactive lease");
            if(method.equals("snapshot"))released=false;
            if(method.equals("release"))released=true;
            if(method.equals("restore"))mismatch=false;Bundle b=new Bundle();b.putString("status","verified");if(method.equals("status"))b.putString("state",released?"released":"active");b.putInt("data_schema",extras.getInt("expected_schema",-1));
            b.putString("snapshot","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");return b;}}""",
    "android/content/pm/ApplicationInfo.java": """package android.content.pm; public class ApplicationInfo {public String sourceDir;}""",
    "dev/ror2lab/phonebuildhostfixture/ToolHostActivity.java": """package dev.ror2lab.phonebuildhostfixture;
        import org.json.JSONObject;import java.io.*;public class ToolHostActivity {
        static java.util.Map<String,JSONObject> values=new java.util.HashMap<>();public static String checkpointState;
        public static void updateInstallCheckpoint(android.content.Context c,String s,String m){checkpointState=s;}
        public static JSONObject readJson(File f)throws Exception{if(!f.isFile())throw new IOException("absent "+f);return values.get(f.getCanonicalPath());}
        public static void writeJson(File f,JSONObject v)throws Exception{f.getParentFile().mkdirs();try(FileOutputStream o=new FileOutputStream(f)){o.write(1);}values.put(f.getCanonicalPath(),v);}}
    """,
}

HARNESS = r"""
import android.content.*; import android.content.pm.*; import dev.ror2lab.phonebuildhostfixture.*;
import org.json.*; import java.io.*; import java.nio.file.*; import java.security.*;
public class AlphaHarness {
    static int checks; static File base; static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
    interface Action {void run()throws Exception;} static void refuse(String word,Action a)throws Exception{
        try{a.run();throw new AssertionError("accepted "+word);}catch(Exception e){if(!e.getMessage().contains(word))throw e;checks++;}}
    static String hash(File f)throws Exception{StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(f.toPath())))s.append(String.format("%02x",b&255));return s.toString();}
    static void put(Context c,String n,JSONObject v)throws Exception{ToolHostActivity.writeJson(new File(c.getFilesDir(),"owner-input/"+n),v);}
    static JSONObject get(Context c,String n)throws Exception{return ToolHostActivity.readJson(new File(c.getFilesDir(),"owner-input/"+n));}
    static File stream(Context c,String n)throws Exception{File f=new File(c.getFilesDir(),"owner-input/work/releases/"+n);f.getParentFile().mkdirs();Files.write(f.toPath(),("synthetic stream "+n).getBytes("UTF-8"));return f;}
    static JSONObject ready(Context c,int code,File f)throws Exception {
        JSONObject r=new JSONObject().put("application_id",OwnerAlphaInstall.PACKAGE).put("version_code",code).put("apk",f.getPath()).put("sha256",hash(f)).put("bytes",f.length())
            .put("signer_sha256",OwnerInstaller.signer(c.manager.next)).put("release",new JSONObject().put("version","authored-"+code).put("version_code",code)
            .put("data_schema",new JSONObject().put("writes",1).put("reads",new JSONArray().put(1))));
        for(String key:new String[]{"source_sha256","input_sha256","toolchain_sha256","payload_sha256"})r.put(key,"synthetic-binding-"+key);
        return r;
    }
    static Context context()throws Exception{Context c=new Context();c.root=Files.createTempDirectory(base.toPath(),"case-").toFile();c.manager.next.packageName=OwnerAlphaInstall.PACKAGE;return c;}
    static JSONObject issued(JSONObject r)throws Exception {
        JSONObject i=new JSONObject().put("status","signed").put("publisher_version_code",r.getJSONObject("release").getLong("version_code")).put("apk_sha256",r.getString("sha256")).put("signer_sha256",r.getString("signer_sha256"));
        for(String key:new String[]{"source_sha256","input_sha256","toolchain_sha256","payload_sha256"})i.put(key,r.getString(key));return i;
    }
    static File issue(Context c)throws Exception{File f=stream(c,"new-stream.bin");JSONObject r=ready(c,2,f);put(c,"owner-apk-ready.json",r);
        JSONObject rows=new JSONObject().put("2",issued(r));
        if(c.manager.current!=null)rows.put("1",issued(get(c,"installed-release.json")));
        put(c,"work/releases/issued-versions.json",new JSONObject().put("schema",1).put("application_id",OwnerAlphaInstall.PACKAGE).put("last_issued",2).put("issues",rows));return f;}
    static Context update()throws Exception{Context c=context();c.manager.current=new PackageInfo();c.manager.current.packageName=OwnerAlphaInstall.PACKAGE;c.manager.current.versionCode=1;
        File old=stream(c,"old-stream.bin");c.manager.current.applicationInfo.sourceDir=old.getPath();put(c,"installed-release.json",ready(c,1,old).put("installed_readback_verified",true));return c;}
    static void install(Context c,File f)throws Exception{OwnerInstaller.install(c,f,hash(f),OwnerAlphaInstall.PACKAGE,2);}
    static void success(Context c,File f){c.manager.current=c.manager.next;c.manager.current.applicationInfo.sourceDir=f.getPath();Intent i=new Intent();i.code=0;new OwnerInstaller.Result().onReceive(c,i);}
    public static void main(String[] args)throws Exception{base=new File(args[0]);base.mkdirs();
        Context first=context();File f=issue(first);install(first,f);success(first,f);check("INSTALLED".equals(OwnerInstaller.state(first)));check(first.resolver.calls.isEmpty());
        check(get(first,"installed-release.json").getLong("version_code")==2);check(!OwnerAlphaInstall.pending(first));
        Context good=update();f=issue(good);install(good,f);check(good.resolver.calls.toString().equals("[snapshot]"));success(good,f);
        check(good.resolver.calls.toString().equals("[snapshot, status, verify, release]"));check(get(good,"previous-installed-release.json").getLong("version_code")==1);
        check(get(good,"installed-release.json").getLong("version_code")==2);check(OwnerAlphaInstall.canRollback(good));
        Context changed=update();f=issue(changed);install(changed,f);changed.resolver.mismatch=true;success(changed,f);
        check(changed.resolver.calls.toString().equals("[snapshot, status, verify, restore, verify, release]"));check("INSTALLED".equals(OwnerInstaller.state(changed)));
        Context broken=update();f=issue(broken);install(broken,f);broken.resolver.mismatch=true;broken.resolver.restoreFail=true;success(broken,f);
        check("RECOVERY_REQUIRED".equals(OwnerInstaller.state(broken)));check(OwnerAlphaInstall.pending(broken));check(!broken.resolver.calls.contains("release"));
        broken.resolver.restoreFail=false;OwnerInstaller.recoverProfiles(broken);check("INSTALLED".equals(OwnerInstaller.state(broken)));check(!OwnerAlphaInstall.pending(broken));
        Context denied=update();f=issue(denied);install(denied,f);Intent no=new Intent();no.code=1;new OwnerInstaller.Result().onReceive(denied,no);
        check(!OwnerAlphaInstall.pending(denied));check(denied.resolver.calls.toString().equals("[snapshot, status, verify, release]"));check(get(denied,"installed-release.json").getLong("version_code")==1);
        File fresh=issue(denied);refuse("already dispatched",()->install(denied,fresh));check(!OwnerAlphaInstall.pending(denied));
        Context unowned=update();File u=issue(unowned);new File(unowned.getFilesDir(),"owner-input/installed-release.json").delete();refuse("no local ownership receipt",()->install(unowned,u));check(unowned.manager.installer.params==null);
        Context schema=update();File sf=issue(schema);get(schema,"owner-apk-ready.json").getJSONObject("release").getJSONObject("data_schema").put("reads",new JSONArray().put(2));
        refuse("Schema-incompatible",()->install(schema,sf));check(schema.resolver.calls.isEmpty());check(schema.manager.installer.params==null);
        Context ledger=context();File lf=issue(ledger);get(ledger,"work/releases/issued-versions.json").getJSONObject("issues").getJSONObject("2").put("payload_sha256","changed");
        refuse("binding differs",()->install(ledger,lf));check(ledger.manager.installer.params==null);
        Context drift=update();File df=issue(drift);Files.write(new File(drift.manager.current.applicationInfo.sourceDir).toPath(),"drift".getBytes("UTF-8"));refuse("identity/hash",()->install(drift,df));
        Context failure=update();File ff=issue(failure);failure.manager.installer.session.writeFail=true;refuse("write failed",()->install(failure,ff));
        check(!OwnerAlphaInstall.pending(failure));check(failure.resolver.calls.contains("release"));check(failure.manager.installer.abandoned);
        Context readback=update();File rf=issue(readback);install(readback,rf);readback.manager.current=readback.manager.next;
        readback.manager.current.applicationInfo.sourceDir=stream(readback,"wrong-installed.bin").getPath();Intent done=new Intent();done.code=0;new OwnerInstaller.Result().onReceive(readback,done);
        check("RECOVERY_REQUIRED".equals(OwnerInstaller.state(readback)));check(get(readback,"installed-release.json").getLong("version_code")==1);
        check(!readback.resolver.calls.contains("release"));readback.manager.current.applicationInfo.sourceDir=rf.getPath();OwnerInstaller.recoverProfiles(readback);check("INSTALLED".equals(OwnerInstaller.state(readback)));
        Context snap=update();File sp=issue(snap);snap.resolver.snapshotFail=true;refuse("snapshot refused",()->install(snap,sp));check(snap.manager.installer.params==null);
        check(OwnerAlphaInstall.pending(snap));check("RECOVERY_REQUIRED".equals(OwnerInstaller.state(snap)));snap.resolver.snapshotFail=false;OwnerInstaller.recoverProfiles(snap);check(!OwnerAlphaInstall.pending(snap));
        // Process death after a verified release but before installer pending cleanup.
        Context resumed=update();File resumedFile=issue(resumed);install(resumed,resumedFile);JSONObject journal=get(resumed,"pending-install.json");success(resumed,resumedFile);
        check(resumed.resolver.released);put(resumed,"pending-install.json",journal);resumed.resolver.mismatch=true;resumed.resolver.calls.clear();
        OwnerInstaller.recoverProfiles(resumed);check("INSTALLED".equals(OwnerInstaller.state(resumed)));check(!OwnerAlphaInstall.pending(resumed));
        check(resumed.resolver.calls.toString().equals("[status]"));check(resumed.resolver.mismatch);check(get(resumed,"previous-installed-release.json").getLong("version_code")==1);
        // Even an authentic released token cannot bypass the installed issue binding.
        put(resumed,"pending-install.json",journal);get(resumed,"work/releases/issued-versions.json").getJSONObject("issues").getJSONObject("2").put("apk_sha256","changed");resumed.resolver.calls.clear();
        OwnerInstaller.recoverProfiles(resumed);check("RECOVERY_REQUIRED".equals(OwnerInstaller.state(resumed)));check(OwnerAlphaInstall.pending(resumed));check(resumed.resolver.calls.isEmpty());
        // The same released-token recovery works after a cancelled install, without rotating receipts.
        Context cancelled=update();File cancelledFile=issue(cancelled);install(cancelled,cancelledFile);JSONObject cancelledJournal=get(cancelled,"pending-install.json");
        Intent cancelledResult=new Intent();cancelledResult.code=1;new OwnerInstaller.Result().onReceive(cancelled,cancelledResult);put(cancelled,"pending-install.json",cancelledJournal);
        cancelled.resolver.mismatch=true;cancelled.resolver.calls.clear();OwnerInstaller.recoverProfiles(cancelled);check(!OwnerAlphaInstall.pending(cancelled));
        check(cancelled.resolver.calls.toString().equals("[status]"));check(cancelled.resolver.mismatch);check(get(cancelled,"installed-release.json").getLong("version_code")==1);
        Context waiting=update();File wf=issue(waiting);install(waiting,wf);Intent confirmation=new Intent();confirmation.code=-1;new OwnerInstaller.Result().onReceive(waiting,confirmation);
        check(OwnerInstaller.busy(waiting));check(OwnerAlphaInstall.pending(waiting));check(!waiting.resolver.calls.contains("release"));
        System.out.println("alpha install retention contracts PASS "+checks);
    }
}"""


class AlphaInstallerTests(unittest.TestCase):
    def test_alpha_ui_stages_provider_client_and_preserves_session_policy(self):
        activity = (SOURCE / "ToolHostActivity.java").read_text()
        installer = (SOURCE / "OwnerInstaller.java").read_text()
        service = (SOURCE / "OwnerBuildService.java").read_text()
        for field in ("installed_release_version", "installer_package", "installer_signer_sha256", "last_build_action"):
            self.assertIn('"' + field + '"', activity)
        self.assertIn('startUpdate("release-rollback")', activity)
        self.assertIn('"profile-recover"', activity)
        self.assertIn("USER_ACTION_NOT_REQUIRED", installer)
        self.assertIn("awaitInstallation()", service)
        for name in ("stage.py", "build_fixture.py"):
            self.assertIn('"OwnerAlphaInstall.java"', (SOURCE / name).read_text())
        for name in ("ProfileStore.java", "ProfileRetentionProvider.java", "alpha_policy.py"):
            self.assertIn(name, (SOURCE / "stage.py").read_text())
        self.assertNotIn("getExternalFilesDir", (SOURCE / "OwnerAlphaInstall.java").read_text())

    def test_real_alpha_session_retention_and_ownership(self):
        compiler = Path(os.environ.get("JAVA_HOME", "/absent")) / "bin/javac"
        if not compiler.is_file():
            found = shutil.which("javac")
            if not found:
                self.skipTest("Java compiler absent")
            compiler = Path(found)
        stubs = {name: value for name, value in STUBS.items() if not name.endswith("OwnerAlphaInstall.java")}
        stubs.update(EXTRA)
        stubs["android/content/Context.java"] = stubs["android/content/Context.java"].replace(
            "public class Context {",
            "public class Context {public java.io.File root;public java.io.File getFilesDir(){return root;}public ContentResolver resolver=new ContentResolver();public ContentResolver getContentResolver(){return resolver;}",
        )
        stubs["android/content/pm/PackageInfo.java"] = stubs["android/content/pm/PackageInfo.java"].replace(
            "public class PackageInfo {", "public class PackageInfo {public ApplicationInfo applicationInfo=new ApplicationInfo();"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sources = []
            for name, value in stubs.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
                sources.append(str(path))
            harness = root / "AlphaHarness.java"
            harness.write_text(HARNESS)
            compile_result = subprocess.run(
                [str(compiler), "-d", str(root), *sources, str(SOURCE / "OwnerInstaller.java"), str(SOURCE / "OwnerAlphaInstall.java"), str(harness)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            result = subprocess.run(
                [str(compiler.with_name("java")), "-cp", str(root), "AlphaHarness", str(root / "synthetic")], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("contracts PASS", result.stdout)
