"""Synthetic stream import and Android phone-flow wiring; never builds an APK."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/phone-build/managed-host"
HARNESS = r"""
import dev.ror2lab.phonebuildhostfixture.OwnerInputImport;
import java.io.*; import java.nio.file.*; import java.util.*; import java.util.zip.*;
public class Harness {
    static int cases;
    static void check(boolean value) { if (!value) throw new AssertionError(); cases++; }
    interface Attempt { void run() throws Exception; }
    static void refuses(String part, Attempt action) throws Exception {
        try { action.run(); throw new AssertionError("accepted " + part); }
        catch (IOException expected) { if (!expected.getMessage().contains(part)) throw expected; cases++; }
    }
    static class Watch implements OwnerInputImport.Observer {
        long progress; boolean cancel; int checks;
        public void checkpoint() throws Exception { checks++; if (cancel) throw new InterruptedIOException("cancelled"); }
        public void progress(String path,long done,long total) { progress=done; }
    }
    static class Source implements OwnerInputImport.Source {
        Map<String,byte[]> values = new LinkedHashMap<>(); int opens;
        public Map<String,Long> inventory() {Map<String,Long> result=new LinkedHashMap<>();for (Map.Entry<String,byte[]> row:values.entrySet()) result.put(row.getKey(),(long)row.getValue().length);return result;}
        public InputStream open(String path) { opens++;return new ByteArrayInputStream(values.get(path)); }
    }
    static String hash(byte[] bytes) throws Exception {StringBuilder s=new StringBuilder();for(byte b:java.security.MessageDigest.getInstance("SHA-256").digest(bytes))s.append(String.format("%02x",b&255));return s.toString();}
    static OwnerInputImport.Required row(String path,byte[] data) throws Exception{return new OwnerInputImport.Required(path,data.length,hash(data));}
    static byte[] zip(String[] names,byte[][] values) throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(ZipOutputStream z=new ZipOutputStream(bytes)){for(int i=0;i<names.length;i++){z.putNextEntry(new ZipEntry(names[i]));z.write(values[i]);z.closeEntry();}}return bytes.toByteArray();
    }
    public static void main(String[] args) throws Exception {
        File root=new File(args[0]); byte[] one="authored synthetic one".getBytes("UTF-8"), two=new byte[200000];Arrays.fill(two,(byte)37);
        List<OwnerInputImport.Required> manifest=Arrays.asList(row("Data/a.bin",one),row("Data/b.bin",two));
        Source source=new Source();source.values.put("Data/a.bin",one);source.values.put("Data/b.bin",two);source.values.put("unneeded.txt",one);
        Watch watch=new Watch();File privateRoot=new File(root,"tree");
        OwnerInputImport.Result result=new OwnerInputImport(privateRoot,manifest,0,watch).tree(source);
        check(result.bytes==one.length+two.length && watch.progress==result.bytes);check(result.extra.equals(Arrays.asList("unneeded.txt")));check(source.opens==2);
        check(Arrays.equals(Files.readAllBytes(new File(privateRoot,"files/Data/a.bin").toPath()),one));
        new OwnerInputImport(privateRoot,manifest,0,new Watch()).tree(source);check(source.opens==2);
        Files.write(new File(privateRoot,"files/Data/a.bin").toPath(),new byte[one.length]);new OwnerInputImport(privateRoot,manifest,0,new Watch()).tree(source);check(source.opens==3);
        check(Arrays.equals(source.values.get("Data/a.bin"),one));
        Source missing=new Source();missing.values.put("Data/a.bin",one);
        refuses("Missing required",()->new OwnerInputImport(new File(root,"missing"),manifest,0,new Watch()).tree(missing));check(!new File(root,"missing/files").exists());
        Source wrong=new Source();wrong.values.put("Data/a.bin",new byte[one.length]);wrong.values.put("Data/b.bin",two);
        refuses("Version mismatch",()->new OwnerInputImport(new File(root,"wrong"),manifest,0,new Watch()).tree(wrong));check(!new File(root,"wrong/files/Data/a.bin").exists());
        List<OwnerInputImport.Required> huge=Arrays.asList(new OwnerInputImport.Required("huge",Long.MAX_VALUE/2,hash(one)));
        OwnerInputImport.Source hugeSource=new OwnerInputImport.Source(){public Map<String,Long> inventory(){return Collections.singletonMap("huge",Long.MAX_VALUE/2);}public InputStream open(String path){throw new AssertionError("source opened before space gate");}};
        refuses("Not enough",()->new OwnerInputImport(new File(root,"space"),huge,0,new Watch()).tree(hugeSource));
        final Watch cancelled=new Watch(){public void progress(String path,long done,long total){super.progress(path,done,total);if(done>=one.length)cancel=true;}};
        File interrupted=new File(root,"interrupted");refuses("cancelled",()->new OwnerInputImport(interrupted,manifest,0,cancelled).tree(source));
        check(new File(interrupted,"files/Data/a.bin").isFile());check(!new File(interrupted,"files/Data/b.bin").isFile());
        new OwnerInputImport(interrupted,manifest,0,new Watch()).tree(source);check(new File(interrupted,"files/Data/b.bin").length()==two.length);
        Watch rehashCancel=new Watch();rehashCancel.cancel=true;refuses("cancelled",()->new OwnerInputImport(interrupted,manifest,0,rehashCancel).tree(source));
        File zipped=new File(root,"zipped");byte[] archive=zip(new String[]{"Data/a.bin","Data/b.bin","extra.txt"},new byte[][]{one,two,one});
        result=new OwnerInputImport(zipped,manifest,0,new Watch()).zip(new ByteArrayInputStream(archive));check(result.extra.equals(Arrays.asList("extra.txt")));check(result.bytes==one.length+two.length);
        File first=new File(zipped,"files/Data/a.bin");long modified=first.lastModified();Thread.sleep(20);
        new OwnerInputImport(zipped,manifest,0,new Watch()).zip(new ByteArrayInputStream(archive));check(first.lastModified()==modified);
        refuses("Unsafe",()->new OwnerInputImport(new File(root,"traversal"),manifest,0,new Watch()).zip(new ByteArrayInputStream(zip(new String[]{"../escape"},new byte[][]{one}))));check(!new File(root,"escape").exists());
        refuses("Case-aliased",()->new OwnerInputImport(new File(root,"case"),manifest,0,new Watch()).zip(new ByteArrayInputStream(zip(new String[]{"Data/a.bin","data/b.bin"},new byte[][]{one,two}))));
        refuses("file/directory",()->new OwnerInputImport(new File(root,"collision"),manifest,0,new Watch()).zip(new ByteArrayInputStream(zip(new String[]{"Data/","Data"},new byte[][]{new byte[0],one}))));
        refuses("Missing required",()->new OwnerInputImport(new File(root,"zipmissing"),manifest,0,new Watch()).zip(new ByteArrayInputStream(zip(new String[]{"extra"},new byte[][]{one}))));
        for(String bad: new String[]{"../x","/x","a//b","a\\b","C:bad","a\nb","e\u0301"}) refuses("Unsafe",()->new OwnerInputImport.Required(bad,0,hash(one)));
        refuses("case-aliased",()->new OwnerInputImport(new File(root,"manifestcase"),Arrays.asList(row("A",one),row("a",one)),0,new Watch()));
        File linked=new File(root,"linked");linked.mkdirs();Files.createSymbolicLink(new File(linked,"files").toPath(),privateRoot.toPath());
        refuses("links",()->new OwnerInputImport(linked,manifest,0,new Watch()).tree(source));
        String pinA="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", pinB="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        byte[] newer="new-one".getBytes("UTF-8"), ancient="ancient-one".getBytes("UTF-8");
        List<OwnerInputImport.Version> versions=Arrays.asList(
            new OwnerInputImport.Version("v1",pinA,manifest,true),
            new OwnerInputImport.Version("v2",pinB,Arrays.asList(row("Data/a.bin",newer),row("Data/b.bin",two)),true),
            new OwnerInputImport.Version("v0",pinB,Arrays.asList(row("Data/a.bin",ancient),row("Data/b.bin",two)),false));
        Source versionSource=new Source(); versionSource.values.put("Data/a.bin",one);versionSource.values.put("Data/b.bin",two);versionSource.values.put("extra",new byte[]{9});
        check(OwnerInputImport.identifyTree(versionSource,versions,new Watch()).name.equals("v1"));check(versionSource.opens==2);
        versionSource.values.put("Data/a.bin",newer);check(OwnerInputImport.identifyTree(versionSource,versions,new Watch()).name.equals("v2"));
        versionSource.values.put("Data/a.bin",ancient);refuses("Found version: v0",()->OwnerInputImport.identifyTree(versionSource,versions,new Watch()));
        versionSource.values.put("Data/a.bin",new byte[]{8,9});refuses("Found version: unknown",()->OwnerInputImport.identifyTree(versionSource,versions,new Watch()));
        check(OwnerInputImport.identifyZip(new ByteArrayInputStream(zip(new String[]{"Data/a.bin","Data/b.bin"},new byte[][]{one,two})),versions,new Watch()).name.equals("v1"));
        refuses("Found version: v0",()->OwnerInputImport.identifyZip(new ByteArrayInputStream(zip(new String[]{"Data/a.bin","Data/b.bin"},new byte[][]{ancient,two})),versions,new Watch()));
        refuses("Found version: unknown",()->OwnerInputImport.identifyZip(new ByteArrayInputStream(zip(new String[]{"Data/a.bin"},new byte[][]{one})),versions,new Watch()));
        Watch versionCancelled=new Watch();versionCancelled.cancel=true;refuses("cancelled",()->OwnerInputImport.identifyTree(versionSource,versions,versionCancelled));
        check(watch.checks>0); System.out.println("phone import contracts PASS " + cases);
    }
}
"""


class OwnerPhoneFlowTests(unittest.TestCase):
    def test_local_stream_import_contracts(self):
        compiler = Path(os.environ.get("JAVA_HOME", "/absent")) / "bin/javac"
        if not compiler.is_file():
            found = shutil.which("javac")
            if not found:
                self.skipTest("Java compiler absent")
            compiler = Path(found)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            harness = root / "Harness.java"
            harness.write_text(HARNESS)
            compile_result = subprocess.run(
                [str(compiler), "-d", str(root), str(SOURCE / "OwnerInputImport.java"), str(harness)], capture_output=True, text=True
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            result = subprocess.run(
                [str(compiler.with_name("java")), "-cp", str(root), "Harness", str(root / "inputs")], capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("phone import contracts PASS", result.stdout)

    def test_foreground_service_owns_worker_and_is_never_boot_started(self):
        manifest = ET.parse(SOURCE / "AndroidManifest.xml").getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        service = manifest.find("application/service")
        self.assertEqual(service.attrib[android + "name"], ".OwnerBuildService")
        self.assertEqual(service.attrib[android + "exported"], "false")
        self.assertEqual(service.attrib[android + "stopWithTask"], "false")
        self.assertEqual(manifest.attrib[android + "versionCode"], "3")
        permissions = {row.attrib[android + "name"] for row in manifest.findall("uses-permission")}
        self.assertTrue({"android.permission.FOREGROUND_SERVICE", "android.permission.WAKE_LOCK"} <= permissions)
        self.assertNotIn("android.permission.RECEIVE_BOOT_COMPLETED", permissions)
        service_source = (SOURCE / "OwnerBuildService.java").read_text()
        self.assertIn("START_NOT_STICKY", service_source)
        self.assertIn("startForeground(NOTIFICATION", service_source)
        self.assertIn("worker.executeUpdate(action)", service_source)
        self.assertIn("worker.cancel()", service_source)
        self.assertIn('path.startsWith("Checking version:")', service_source)
        self.assertIn('validating ? "VALIDATING" : "IMPORTING"', service_source)
        self.assertIn("if (!validating && total > 0)", service_source)
        self.assertIn("wakeLock.release()", service_source)
        self.assertIn('"interrupted", true', service_source)
        activity = (SOURCE / "ToolHostActivity.java").read_text()
        ui = activity[: activity.index("public static class Runner")]
        self.assertNotIn("new Thread", ui)
        self.assertIn("OwnerBuildService.launch", ui)
        self.assertIn("ACTION_OPEN_DOCUMENT_TREE", ui)
        self.assertIn("ACTION_OPEN_DOCUMENT", ui)
        self.assertIn("takePersistableUriPermission", ui)
        self.assertIn("releasePersistableUriPermission", ui)
        self.assertIn("first_failure", ui)
        self.assertIn('if (state.optLong("total", 0) > 0)', ui)
        self.assertIn('"--control"', activity)
        self.assertIn('"--status"', activity)
        self.assertNotIn(".toString());\n        else detail.append", ui)
        source = (SOURCE / "OwnerInputSource.java").read_text()
        self.assertIn("getPersistedUriPermissions", source)
        self.assertIn("openAssetFileDescriptor", source)
        self.assertIn("signal.cancel()", source)
        self.assertIn("stream.close()", source)
        self.assertNotIn("java.net", source)
        self.assertNotIn("openOutputStream", source)


if __name__ == "__main__":
    unittest.main()
