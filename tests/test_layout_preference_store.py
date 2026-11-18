"""Authored temporary-file persistence, never real owner preferences."""

import unittest
from tests.layout_csharp import LAYOUT, run_csharp

HARNESS = r"""
using System;using System.IO;using OwnerLayout;
class Faults:LayoutFileOperations {
internal bool WriteFailure,PublishFailure,ReadFailure;
internal override void Write(string path,string text){base.Write(path,text);if(WriteFailure)throw new IOException("injected write failure");}
internal override void Publish(string temporary,string destination,bool replace){if(PublishFailure)throw new IOException("injected publish failure");base.Publish(temporary,destination,replace);}
internal override string Read(string path){if(ReadFailure)throw new IOException("injected read failure");return base.Read(path);}
}
class Harness {
static void Check(bool value){if(!value)throw new Exception("store assertion");}
static void Fail(Action action){try{action();}catch(IOException){return;}catch(InvalidDataException){return;}throw new Exception("expected refusal");}
static void Main(){
string root=Path.Combine(Path.GetTempPath(),"authored-layout-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
try {
var doc=new TouchLayoutDocument(new[]{new TouchProfile("p",new[]{new TouchControl("generic",new LayoutRect(.1,.1,.2,.2),1,1)})});
var edit=new TouchLayoutEditor(doc);edit.Begin("p","generic");edit.SetDraft(new LayoutRect(.3,.3,.2,.2),2,.5);edit.Confirm();var next=edit.Document;
string path=Path.Combine(root,"touch.txt");var faults=new Faults();var store=new LayoutPreferenceStore(path,faults);
var missing=store.LoadTouch(doc);Check(missing.State==LayoutLoadState.Missing&&missing.Value==doc&&!File.Exists(path));
store.SaveTouch(doc);Check(store.LoadTouch(next).Value.Export()==doc.Export());
foreach(bool write in new[]{true,false}){
 faults.WriteFailure=write;faults.PublishFailure=!write;Fail(()=>store.SaveTouch(next));
 Check(File.ReadAllText(path)==doc.Export()&&Directory.GetFiles(root,".layout-*.tmp").Length==0);
}
faults.WriteFailure=false;faults.PublishFailure=false;store.SaveTouch(next);Check(store.LoadTouch(doc).Value.Export()==next.Export());
// Invalid files never become default successes and are not silently overwritten.
foreach(string bad in new[]{"bad",next.Export().Replace("touch-layout\t1","touch-layout\t2"),new string('x',1048577)}){
 File.WriteAllText(path,bad);var result=store.LoadTouch(doc);Check(result.State==LayoutLoadState.Invalid&&result.Value==null);
 Fail(()=>store.SaveTouch(doc));Check(File.ReadAllText(path)==bad);
}
File.WriteAllBytes(path,new byte[]{255,254,255});Check(store.LoadTouch(doc).State==LayoutLoadState.Invalid);Fail(()=>store.SaveTouch(doc));
File.WriteAllText(path,doc.Export());faults.ReadFailure=true;Check(store.LoadTouch(doc).State==LayoutLoadState.Unavailable);Fail(()=>store.SaveTouch(next));Check(File.ReadAllText(path)==doc.Export());faults.ReadFailure=false;
var absentDirectory=new LayoutPreferenceStore(Path.Combine(root,"absent","touch.txt"));Check(absentDirectory.LoadTouch(doc).State==LayoutLoadState.Unavailable);Fail(()=>absentDirectory.SaveTouch(doc));
string fresh=Path.Combine(root,"fresh.txt");faults.PublishFailure=true;Fail(()=>new LayoutPreferenceStore(fresh,faults).SaveTouch(doc));Check(!File.Exists(fresh));faults.PublishFailure=false;
var hud=new HudLayoutModel(new[]{new HudGroup("group",new LayoutRect(.2,.2,.2,.2),HudAnchor.Center)},new[]{new HudProfile("main",1,new HudGroup[0])});
var hudStore=new LayoutPreferenceStore(Path.Combine(root,"hud.txt"));Check(hudStore.LoadHud(hud).State==LayoutLoadState.Missing);hudStore.SaveHud(hud);
var hudEdit=new HudLayoutEditor(hud);hudEdit.Begin("main");hudEdit.SetScale(2);hudEdit.Confirm();hudStore.SaveHud(hudEdit.Model);Check(hudStore.LoadHud(hud).Value.Find("main").Scale==2);
Check(new LayoutPreferenceStore(path).LoadHud(hud).State==LayoutLoadState.Invalid);Fail(()=>new LayoutPreferenceStore(path).SaveHud(hud));Check(File.ReadAllText(path)==doc.Export());
Check(Directory.GetFiles(root,".layout-*.tmp").Length==0);Console.WriteLine("layout store PASS");
} finally {Directory.Delete(root,true);}
}}
"""


class LayoutPreferenceStoreTests(unittest.TestCase):
    def test_source_boundary(self):
        source = (LAYOUT / "LayoutPreferenceStore.cs").read_text()
        self.assertNotIn("UnityEngine", source)
        self.assertIn("File.Replace(temporary, destination, null)", source)
        self.assertNotIn("File.Delete(destination)", source)

    def test_actual_preference_store(self):
        self.assertIn(
            "layout store PASS",
            run_csharp(HARNESS, ["LayoutProjection.cs", "TouchLayoutDocument.cs", "HudLayoutModel.cs", "LayoutPreferenceStore.cs"]),
        )
