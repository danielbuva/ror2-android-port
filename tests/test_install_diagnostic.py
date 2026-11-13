"""Execute the actual privacy-bounded install diagnostic writer with authored doubles."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallDiagnosticTests(unittest.TestCase):
    def test_writer_reset_callback_preservation_privacy_and_failure(self):
        javac = shutil.which("javac")
        if not javac:
            self.skipTest("Java compiler absent")
        source = (ROOT / "tools/phone-build/managed-host/ToolHostActivity.java").read_text()
        method = source[source.index("    static synchronized void updateInstallDiagnostic(") : source.index("    static void updateInstallCheckpoint(")]
        harness = r"""
import java.io.*;
import java.util.*;
public class DiagnosticHarness {
    static class Context { File root; Context(File root){this.root=root;} File getFilesDir(){return root;} }
    static class JSONObject {
        static final Object NULL=new Object(); Map<String,Object> data=new HashMap<>();
        JSONObject put(String key,Object value){data.put(key,value);return this;}
        Object opt(String key){return data.get(key);}
        String optString(String key,String fallback){Object v=opt(key);return v instanceof String?(String)v:fallback;}
    }
    static JSONObject saved; static boolean fail;
    static JSONObject readJson(File file)throws Exception {if(fail)throw new IOException();return saved;}
    static void writeJson(Context app,File file,JSONObject row)throws Exception {
        if(fail)throw new IOException();file.getParentFile().mkdirs();file.createNewFile();saved=row;
    }
METHOD
    static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args)throws Exception {
        Context c=new Context(new File(args[0]));
        updateInstallDiagnostic(c,"prepare",null,false);
        check(saved.opt("session_match")==JSONObject.NULL && saved.opt("callback").equals("none"));
        check(saved.data.size()==6 && saved.opt("schema").equals(2));
        check(saved.opt("receiver_registration").equals("unavailable") && saved.opt("callback_entry").equals("none"));
        for(String registration:new String[]{"private","exported","disabled","missing","unavailable"}) {
            updateInstallReceiverDiagnostic(c,registration,false);check(saved.opt("receiver_registration").equals(registration));
        }
        updateInstallReceiverDiagnostic(c,"private",false);
        updateInstallDiagnostic(c,"commit-start",null,false);
        updateInstallReceiverDiagnostic(c,null,true);
        check(saved.opt("callback_entry").equals("entered") && saved.opt("callback").equals("none"));
        updateInstallDiagnostic(c,null,"pending-user-action",true);
        updateInstallDiagnostic(c,"commit-returned",null,false);
        check(saved.opt("stage").equals("commit-returned") && saved.opt("callback").equals("pending-user-action") && saved.opt("session_match").equals(true));
        check(saved.opt("receiver_registration").equals("private") && saved.opt("callback_entry").equals("entered"));
        updateInstallDiagnostic(c,null,"failure",false);
        check(saved.opt("stage").equals("commit-returned") && saved.opt("session_match").equals(false));
        updateInstallDiagnostic(c,"prepare",null,false);
        check(saved.opt("session_match")==JSONObject.NULL && saved.opt("callback").equals("none"));
        check(saved.opt("receiver_registration").equals("unavailable") && saved.opt("callback_entry").equals("none"));
        // A successfully classified callback also proves entry if the early best-effort write failed.
        updateInstallDiagnostic(c,null,"success",true);check(saved.opt("callback_entry").equals("entered"));
        saved.put("stage","private-path").put("callback","private-error").put("session_match","private-id").put("extra","private-key")
             .put("receiver_registration","private-package").put("callback_entry","private-stack");
        updateInstallDiagnostic(c,null,null,false);
        check(saved.opt("stage").equals("unknown") && saved.opt("callback").equals("unknown") && saved.opt("session_match")==JSONObject.NULL && saved.data.size()==6);
        check(saved.opt("receiver_registration").equals("unavailable") && saved.opt("callback_entry").equals("unknown"));
        JSONObject prior=saved;fail=true;updateInstallDiagnostic(c,"prepare",null,false);check(saved==prior);
        updateInstallReceiverDiagnostic(c,"private",true);check(saved==prior);
        System.out.println("install-diagnostic-contracts-pass");
    }
}
""".replace("METHOD", method)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            java = root / "DiagnosticHarness.java"
            java.write_text(harness)
            result = subprocess.run([javac, "-source", "8", "-target", "8", str(java)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [str(Path(javac).with_name("java")), "-cp", str(root), "DiagnosticHarness", str(root / "data")],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("install-diagnostic-contracts-pass", result.stdout)
