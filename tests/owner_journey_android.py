"""Synthetic Android boundary executing the real installer/alpha receipt owners.

Input objects use a test-only binary bridge, not a JSON parser qualification.
Output JSON is serialized from actual owner-written objects, never invented success.
"""

import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from tests.test_owner_alpha_installer import EXTRA, SOURCE
from tests.test_owner_installer import STUBS


def encode(value):
    if isinstance(value, dict):
        return b"o" + struct.pack(">I", len(value)) + b"".join(encode(k) + encode(v) for k, v in value.items())
    if isinstance(value, list):
        return b"a" + struct.pack(">I", len(value)) + b"".join(map(encode, value))
    if value is None:
        return b"n"
    if isinstance(value, bool):
        return b"t" if value else b"f"
    if isinstance(value, int):
        return b"i" + struct.pack(">q", value)
    if isinstance(value, str):
        data = value.encode("utf-8")
        return b"s" + struct.pack(">I", len(data)) + data
    raise TypeError(f"unsupported fixture value: {type(value).__name__}")


def compile_installer(root, command):
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
    harness = """import android.content.*;import android.content.pm.*;import dev.ror2lab.phonebuildhostfixture.*;import org.json.*;import java.io.*;
public class Journey {
static Object read(DataInputStream in)throws IOException{
switch(in.readUnsignedByte()){
case 'n': return null;
case 't': return true;
case 'f': return false;
case 'i': return in.readLong();
case 's':
    byte[] data=new byte[in.readInt()];in.readFully(data);
    return new String(data,java.nio.charset.StandardCharsets.UTF_8);
case 'o':
    JSONObject object=new JSONObject();
    for(int n=in.readInt();n>0;n--)object.put((String)read(in),read(in));
    return object;
case 'a':
    JSONArray array=new JSONArray();
    for(int n=in.readInt();n>0;n--)array.put(read(in));
    return array;
default: throw new IOException("unknown fixture value tag");
}}
static void check(boolean b){if(!b)throw new AssertionError();}
static void put(Context c,String n,JSONObject v)throws Exception{ToolHostActivity.writeJson(c,new File(c.root,"owner-input/"+n),v);}
public static void main(String[] args)throws Exception{
Context c=new Context();c.root=new File(args[0]);JSONObject ready,previous,ledger;
try(DataInputStream in=new DataInputStream(new BufferedInputStream(System.in))){
ready=(JSONObject)read(in);previous=(JSONObject)read(in);ledger=(JSONObject)read(in);
check(in.read()==-1);
}
String outcome=args[1];
put(c,"owner-apk-ready.json",ready);put(c,"work/releases/issued-versions.json",ledger);
c.manager.next.packageName=OwnerAlphaInstall.PACKAGE;c.manager.next.versionCode=(int)ready.getLong("version_code");
if(previous!=null){put(c,"installed-release.json",previous);c.manager.current=new PackageInfo();c.manager.current.packageName=OwnerAlphaInstall.PACKAGE;c.manager.current.versionCode=(int)previous.getLong("version_code");c.manager.current.applicationInfo.sourceDir=previous.getString("apk");}
File stream=new File(ready.getString("apk"));OwnerInstaller.install(c,stream,ready.getString("sha256"),OwnerAlphaInstall.PACKAGE,ready.getLong("version_code"));
check(!"INSTALLED".equals(OwnerInstaller.state(c)));
if(!"failed".equals(outcome)) {
c.manager.installer.session.receiver.send(c,7,PackageInstaller.STATUS_PENDING_USER_ACTION,new Intent());
check("AWAITING_CONFIRMATION".equals(OwnerInstaller.state(c)));
check(previous!=null || !new File(c.root,"owner-input/installed-release.json").exists());
}
PackageInfo old=c.manager.current;
if("declined".equals(outcome)||"failed".equals(outcome)){
c.manager.installer.session.receiver.send(c,7,PackageInstaller.STATUS_FAILURE,null);
check("ERROR".equals(OwnerInstaller.state(c)));check(!OwnerAlphaInstall.pending(c));
check(!new File(c.root,"owner-input/owner-apk-ready.json").exists());return;
}
if("missing".equals(outcome)||"mismatch".equals(outcome)){
c.manager.current="missing".equals(outcome)?null:c.manager.next;
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
"""
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


class InstallerFixture:
    """Share immutable bytecode, not JVM processes or per-install state."""

    def __init__(self, root):
        self.root = root
        self.compiled = False

    def install(self, journey, previous=None, *, outcome="success"):
        if outcome not in {"success", "declined", "failed", "missing", "mismatch"}:
            raise ValueError("unknown synthetic installer outcome")
        java = shutil.which("java")
        if not java:
            raise unittest.SkipTest("Java runtime absent")
        if not self.compiled:
            compiler = shutil.which("javac")
            compile_installer(self.root, [compiler] if compiler else [java, "com.sun.tools.javac.Main"])
            self.compiled = True
        inputs = journey.inputs
        ready = json.loads((inputs / "owner-apk-ready.json").read_text())
        ledger = json.loads((inputs / "work/releases/issued-versions.json").read_text())
        # The synthetic Context adds owner-input; use a fresh private adapter
        # directory so each JVM invocation addresses only this journey's inputs.
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            (context / "owner-input").symlink_to(inputs, target_is_directory=True)
            result = subprocess.run(
                [java, "-cp", str(self.root), "Journey", str(context), outcome],
                input=encode(ready) + encode(previous) + encode(ledger),
                capture_output=True,
                timeout=20,
            )
            if result.returncode:
                raise AssertionError((result.stdout + result.stderr).decode("utf-8", errors="replace"))
        return json.loads((inputs / "installed-release.json").read_text())
