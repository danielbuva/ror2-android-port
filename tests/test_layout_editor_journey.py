"""Composed authored editor, persistence and restart acceptance; no live UI/device."""

import unittest
from tests.layout_csharp import run_csharp

HARNESS = r"""
using System;using System.IO;using OwnerLayout;
class PublishFault:LayoutFileOperations {
internal bool Fail;
internal override void Publish(string temporary,string destination,bool replace){if(Fail)throw new IOException("authored storage refusal");base.Publish(temporary,destination,replace);}
}
class Harness {
static void Check(bool value){if(!value)throw new Exception("editor journey assertion");}
static void Near(double a,double b){Check(Math.Abs(a-b)<1e-8);}
static void Main(){
string root=Path.Combine(Path.GetTempPath(),"authored-editor-journey-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
try{
var touchDefaults=new TouchLayoutDocument(new[]{new TouchProfile("p",new[]{new TouchControl("generic",new LayoutRect(.1,.1,.2,.2),1,1)})});
var hudDefaults=new HudLayoutModel(new[]{new HudGroup("group",new LayoutRect(.1,.1,.2,.2),HudAnchor.TopLeft)},new[]{new HudProfile("p",1,new HudGroup[0])});
string touchPath=Path.Combine(root,"touch.txt"),hudPath=Path.Combine(root,"hud.txt");
var fault=new PublishFault();var touchStore=new LayoutPreferenceStore(touchPath,fault);var hudStore=new LayoutPreferenceStore(hudPath);
var initial=touchStore.LoadTouch(touchDefaults);Check(initial.State==LayoutLoadState.Missing);
var editor=new TouchLayoutEditor(initial.Value);var pointer=new TouchEditorGesture(editor,40,40);var landscape=new LayoutProjection(1000,600,0,0,0,0);
// Cancel a preview before any file exists. No model or file changes.
Check(pointer.Down(1,150,90,landscape,"p",false));Check(pointer.Move(1,350,210,landscape));pointer.Cancel();
Check(editor.Document.Export()==touchDefaults.Export()&&!File.Exists(touchPath));
// Commit in memory, explicitly save, and reconstruct the editor from the file.
Check(pointer.Down(2,150,90,landscape,"p",false));Check(pointer.Up(2,350,210,landscape));
Near(editor.Document.Find("p").Find("generic").Rectangle.X,.3);Check(!File.Exists(touchPath));touchStore.SaveTouch(editor.Document);
string saved=File.ReadAllText(touchPath);var restart=new LayoutPreferenceStore(touchPath).LoadTouch(touchDefaults);Check(restart.State==LayoutLoadState.Loaded);
editor=new TouchLayoutEditor(restart.Value);pointer=new TouchEditorGesture(editor,40,40);Check(editor.Document.Export()==saved&&!editor.Undo());
// Display-change interruption cannot leak its draft into the subsequently saved document.
var portrait=new LayoutProjection(600,1000,0,0,0,0);
Check(pointer.Down(3,350,210,landscape,"p",false));Check(!pointer.Up(3,350,210,portrait));touchStore.SaveTouch(editor.Document);Check(File.ReadAllText(touchPath)==saved);
// A failed durable save leaves the memory commit available for retry and disk unchanged.
Check(pointer.Down(4,350,210,landscape,"p",true));Check(pointer.Up(4,450,270,landscape));string pending=editor.Document.Export();Check(pending!=saved);
fault.Fail=true;try{touchStore.SaveTouch(editor.Document);throw new Exception("save falsely succeeded");}catch(IOException){}
Check(editor.Document.Export()==pending&&File.ReadAllText(touchPath)==saved&&touchStore.LoadTouch(touchDefaults).Value.Export()==saved);
fault.Fail=false;touchStore.SaveTouch(editor.Document);Check(new LayoutPreferenceStore(touchPath).LoadTouch(touchDefaults).Value.Export()==pending);
// HUD preferences persist separately; preview/cancel never rewrites either file.
var hud=new HudLayoutEditor(hudStore.LoadHud(hudDefaults).Value);hud.Begin("p");hud.SetScale(2);Near(hud.Preview("group",landscape).Width,400);hud.Cancel();
Check(!File.Exists(hudPath)&&File.ReadAllText(touchPath)==pending);hud.Begin("p");hud.SetScale(1.5);hud.Confirm();hudStore.SaveHud(hud.Model);
var hudRestart=new LayoutPreferenceStore(hudPath).LoadHud(hudDefaults);Check(hudRestart.State==LayoutLoadState.Loaded);Near(hudRestart.Value.Project("p","group",portrait).Width,180);
Check(File.ReadAllText(touchPath)==pending);
// Corrupt restart remains an explicit recovery decision, never silent default/save.
File.WriteAllText(touchPath,"authored corrupt receipt");var invalid=new LayoutPreferenceStore(touchPath).LoadTouch(touchDefaults);Check(invalid.State==LayoutLoadState.Invalid&&invalid.Value==null);
try{touchStore.SaveTouch(editor.Document);throw new Exception("overwrote corrupt preference");}catch(InvalidDataException){}
Check(File.ReadAllText(touchPath)=="authored corrupt receipt");Check(Directory.GetFiles(root,".layout-*.tmp").Length==0);
Console.WriteLine("layout editor journey PASS");
}finally{Directory.Delete(root,true);}
}}
"""


class LayoutEditorJourneyTests(unittest.TestCase):
    def test_actual_editor_save_restart(self):
        self.assertIn(
            "layout editor journey PASS",
            run_csharp(
                HARNESS,
                ["LayoutProjection.cs", "TouchLayoutDocument.cs", "HudLayoutModel.cs", "LayoutPreferenceStore.cs", "TouchEditorGesture.cs"],
            ),
        )
