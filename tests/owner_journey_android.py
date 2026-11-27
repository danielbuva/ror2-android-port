"""Synthetic Android boundary executing the real installer/alpha receipt owners.

Input objects are generated Java literals, not a JSON parser qualification.
Output JSON is serialized from actual owner-written objects, never invented success.
"""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from tests.test_owner_alpha_installer import EXTRA, SOURCE
from tests.test_owner_installer import STUBS


def literal(value):
    if isinstance(value, dict):
        return "new JSONObject()" + "".join(".put(" + json.dumps(k) + "," + literal(v) + ")" for k, v in value.items())
    if isinstance(value, list):
        return "new JSONArray()" + "".join(".put(" + literal(v) + ")" for v in value)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value) + "L"
    return json.dumps(value)


def install(journey, previous=None, *, outcome="success"):
    if outcome not in {"success", "declined", "failed", "missing", "mismatch"}:
        raise ValueError("unknown synthetic installer outcome")
    java = shutil.which("java")
    if not java:
        raise unittest.SkipTest("Java runtime absent")
    compiler = shutil.which("javac")
    command = [compiler] if compiler else [java, "com.sun.tools.javac.Main"]
    inputs = journey.inputs
    ready = json.loads((inputs / "owner-apk-ready.json").read_text())
    ledger = json.loads((inputs / "work/releases/issued-versions.json").read_text())
    stubs = {name: value for name, value in STUBS.items() if not name.endswith("OwnerAlphaInstall.java")}
    stubs.update(EXTRA)
    stubs["android/content/Context.java"] = stubs["android/content/Context.java"].replace(
        "public class Context {",
        "public class Context {public java.io.File root;public java.io.File getFilesDir(){return root;}public ContentResolver resolver=new ContentResolver();public ContentResolver getContentResolver(){return resolver;}",
    )
    stubs["android/content/pm/PackageInfo.java"] = stubs["android/content/pm/PackageInfo.java"].replace(
        "public class PackageInfo {", "public class PackageInfo {public ApplicationInfo applicationInfo=new ApplicationInfo();"
    )
    stubs["org/json/JSONObject.java"] = stubs["org/json/JSONObject.java"].replace("private Map<String,Object> values", "public Map<String,Object> values")
    stubs["org/json/JSONArray.java"] = (
        stubs["org/json/JSONArray.java"]
        .replace("private java.util.List<Integer> values", "public java.util.List<Object> values")
        .replace("put(int v)", "put(Object v)")
        .replace("return values.get(i);", "return ((Number)values.get(i)).intValue();")
    )
    activity = stubs["dev/ror2lab/phonebuildhostfixture/ToolHostActivity.java"]
    activity = activity.replace("o.write(1);", "o.write(org.json.Export.encode(v).getBytes(java.nio.charset.StandardCharsets.UTF_8));")
    stubs["dev/ror2lab/phonebuildhostfixture/ToolHostActivity.java"] = activity
    stubs["org/json/Export.java"] = r"""package org.json;import java.util.*;public class Export {
    public static String encode(Object o){if(o==null)return "null";if(o instanceof JSONObject)return encode(((JSONObject)o).values);if(o instanceof JSONArray)return encode(((JSONArray)o).values);
    if(o instanceof String)return "\""+((String)o).replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n")+"\"";
    if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object k:((Map)o).keySet())j.add(encode(k)+":"+encode(((Map)o).get(k)));return j.toString();}
    if(o instanceof Iterable){StringJoiner j=new StringJoiner(",","[","]");for(Object v:(Iterable)o)j.add(encode(v));return j.toString();}return o.toString();}}
    """
    harness = (
        """import android.content.*;import android.content.pm.*;import dev.ror2lab.phonebuildhostfixture.*;import org.json.*;import java.io.*;
public class Journey {
static void check(boolean b){if(!b)throw new AssertionError();}
static void put(Context c,String n,JSONObject v)throws Exception{ToolHostActivity.writeJson(c,new File(c.root,"owner-input/"+n),v);}
public static void main(String[] args)throws Exception{
Context c=new Context();c.root=new File(args[0]);JSONObject ready=READY;JSONObject previous=PREVIOUS;
put(c,"owner-apk-ready.json",ready);put(c,"work/releases/issued-versions.json",LEDGER);
c.manager.next.packageName=OwnerAlphaInstall.PACKAGE;c.manager.next.versionCode=(int)ready.getLong("version_code");
if(previous!=null){put(c,"installed-release.json",previous);c.manager.current=new PackageInfo();c.manager.current.packageName=OwnerAlphaInstall.PACKAGE;c.manager.current.versionCode=(int)previous.getLong("version_code");c.manager.current.applicationInfo.sourceDir=previous.getString("apk");}
File stream=new File(ready.getString("apk"));OwnerInstaller.install(c,stream,ready.getString("sha256"),OwnerAlphaInstall.PACKAGE,ready.getLong("version_code"));
check(!"INSTALLED".equals(OwnerInstaller.state(c)));
if(!"failed".equals(OUTCOME)) {
c.manager.installer.session.receiver.send(c,7,PackageInstaller.STATUS_PENDING_USER_ACTION,new Intent());
check("AWAITING_CONFIRMATION".equals(OwnerInstaller.state(c)));
check(previous!=null || !new File(c.root,"owner-input/installed-release.json").exists());
}
PackageInfo old=c.manager.current;
if("declined".equals(OUTCOME)||"failed".equals(OUTCOME)){
c.manager.installer.session.receiver.send(c,7,PackageInstaller.STATUS_FAILURE,null);
check("ERROR".equals(OwnerInstaller.state(c)));check(!OwnerAlphaInstall.pending(c));
check(!new File(c.root,"owner-input/owner-apk-ready.json").exists());return;
}
if("missing".equals(OUTCOME)||"mismatch".equals(OUTCOME)){
c.manager.current="missing".equals(OUTCOME)?null:c.manager.next;
if(c.manager.current!=null){c.manager.current.applicationInfo.sourceDir=stream.getPath();c.manager.current.signatures=new Signature[]{new Signature("wrong-simulated-key")};}
c.manager.installer.session.receiver.send(c,7,PackageInstaller.STATUS_SUCCESS,null);
check("RECOVERY_REQUIRED".equals(OwnerInstaller.state(c)));check(OwnerAlphaInstall.pending(c));
check(previous!=null);check(ToolHostActivity.readJson(new File(c.root,"owner-input/installed-release.json")).getLong("version_code")==previous.getLong("version_code"));
c.manager.current=old;OwnerInstaller.recoverProfiles(c);
check("ERROR".equals(OwnerInstaller.state(c)));check(!OwnerAlphaInstall.pending(c));
return;
}
c.manager.current=c.manager.next;c.manager.current.applicationInfo.sourceDir=stream.getPath();
c.manager.installer.session.receiver.send(c,7,PackageInstaller.STATUS_SUCCESS,null);
check("INSTALLED".equals(OwnerInstaller.state(c)));check(!OwnerAlphaInstall.pending(c));
check(c.resolver.calls.toString().equals(previous==null?"[]":"[snapshot, status, verify, release]"));
System.out.println("consent -> verified installed receipt PASS");}}
""".replace("READY", literal(ready))
        .replace("PREVIOUS", literal(previous))
        .replace("LEDGER", literal(ledger))
        .replace("OUTCOME", json.dumps(outcome))
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths = []
        for name, source in stubs.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
            paths.append(str(path))
        path = root / "Journey.java"
        path.write_text(harness)
        result = subprocess.run(
            [*command, "-d", str(root), *paths, str(SOURCE / "OwnerInstaller.java"), str(SOURCE / "OwnerAlphaInstall.java"), str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        # The synthetic Context adds owner-input; use a private adapter directory
        # symlink so real owner file paths address this same journey's inputs.
        context = root / "context"
        context.mkdir()
        (context / "owner-input").symlink_to(inputs, target_is_directory=True)
        result = subprocess.run([java, "-cp", str(root), "Journey", str(context)], capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
    return json.loads((inputs / "installed-release.json").read_text())
