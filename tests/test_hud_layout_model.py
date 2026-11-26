"""Authored HUD preferences and preview geometry, not runtime HUD rendering."""

import unittest
from tests.layout_csharp import LAYOUT, run_csharp

HARNESS = r"""
using System;using System.Globalization;using OwnerLayout;
class Harness {
static void Check(bool value){if(!value)throw new Exception("HUD assertion");}
static void Near(double a,double b){Check(Math.Abs(a-b)<1e-8);}
static void Refuse(Action action){try{action();}catch(ArgumentException){return;}throw new Exception("accepted invalid HUD");}
static void Busy(Action action){try{action();}catch(InvalidOperationException){return;}throw new Exception("accepted conflicting edit");}
static void Main(){
var a=new HudGroup("group_a",new LayoutRect(.7,.7,.2,.2),HudAnchor.BottomRight);
var b=new HudGroup("group_b",new LayoutRect(.2,.2,.2,.2),HudAnchor.Center);
var defaults=new[]{a,b};var profiles=new[]{new HudProfile("main",1,new HudGroup[0]),new HudProfile("other",1,new HudGroup[0])};
var model=new HudLayoutModel(defaults,profiles);defaults[0]=b;profiles[0]=profiles[1];model.Defaults[0]=null;model.Profiles[0]=null;
Check(model.Resolve("main","group_a")==a);
var editor=new HudLayoutEditor(model);string original=model.Export();
editor.Begin("main");editor.SetScale(2);
var wide=new LayoutProjection(1000,500,10,20,30,40);
var preview=editor.Preview("group_a",wide);Near(preview.X,490);Near(preview.Y,240);Near(preview.Width,384);Near(preview.Height,176);
Check(editor.Model.Export()==original&&editor.Model.Find("other").Scale==1);
Busy(()=>editor.Begin("other"));Busy(()=>editor.Import(original));Busy(()=>editor.Reset("main"));
Refuse(()=>editor.SetScale(double.NaN));Refuse(()=>editor.SetGroup(new HudGroup("unknown",a.Rectangle,HudAnchor.Center)));Check(editor.Draft.Scale==2);
editor.Cancel();editor.Cancel();Check(editor.Model.Export()==original);
editor.Begin("main");editor.SetScale(1.5);editor.SetGroup(new HudGroup("group_a",new LayoutRect(.1,.1,.3,.3),HudAnchor.TopLeft));editor.Confirm();
Check(editor.Model.Resolve("main","group_b")==b&&editor.Model.Resolve("other","group_a")==a);
string changed=editor.Model.Export();CultureInfo.CurrentCulture=new CultureInfo("fr-FR");
Check(HudLayoutModel.Import(model.Defaults,changed).Export()==changed);
foreach(var size in new[]{new[]{1920.0,1080.0},new[]{1080.0,1920.0},new[]{2560.0,1080.0},new[]{1024.0,768.0}}){
 var projection=new LayoutProjection(size[0],size[1],20,30,40,50);
 foreach(HudAnchor anchor in Enum.GetValues(typeof(HudAnchor))){
  var g=new HudGroup("edge",new LayoutRect(.8,.8,.2,.2),anchor);
  var pixels=g.Project(projection,2);LayoutProjection.RequireNormalized(projection.Unproject(pixels));
 }
 // Scene callers may request only one group; omitted groups and all preferences remain unchanged.
 editor.Model.Project("main","group_b",projection);Check(editor.Model.Export()==changed);
}
foreach(string bad in new[]{changed.Replace("hud-layout\t1","hud-layout\t2"),changed.Replace("1.5","NaN"),changed.Replace("1.5","4"),
 changed.Replace("group_a","unknown"),changed.Replace("G\tgroup_a\t0","G\tgroup_a\t9"),changed.Replace("0.1","-1"),
 changed.Replace("other","main"),changed+"\n",changed.TrimEnd('\n'),"hud-layout\t1\n",new string('x',HudLayoutModel.MaximumTextLength+1)}){
 Refuse(()=>editor.Import(bad));Check(editor.Model.Export()==changed);
}
string duplicate=changed.Replace("P\tother", "G\tgroup_a\t0\t0.1\t0.1\t0.3\t0.3\nP\tother");
Refuse(()=>editor.Import(duplicate));Check(editor.Model.Export()==changed);
editor.Reset("main");Check(editor.Model.Export()==original);editor.Import(changed);Check(editor.Model.Export()==changed);
Refuse(()=>editor.Reset("unknown"));Check(editor.Model.Export()==changed);
Refuse(()=>new HudGroup("bad",a.Rectangle,(HudAnchor)10));Refuse(()=>new HudLayoutModel(new[]{a,a},model.Profiles));
Refuse(()=>new HudProfile("bad",.4,new HudGroup[0]));
Console.WriteLine("HUD layout PASS");}}
"""


class HudLayoutModelTests(unittest.TestCase):
    def test_source_boundary(self):
        source = (LAYOUT / "HudLayoutModel.cs").read_text()
        self.assertNotIn("UnityEngine", source)
        self.assertNotIn("System.IO", source)
        self.assertIn("public const int Schema = 1", source)

    def test_actual_hud_preferences(self):
        self.assertIn("HUD layout PASS", run_csharp(HARNESS, ["LayoutProjection.cs", "HudLayoutModel.cs"]))
