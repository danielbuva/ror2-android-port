"""Synthetic authored layout transactions; no live input or device evidence."""

import unittest
from tests.layout_csharp import LAYOUT, run_csharp

HARNESS = r"""
using System;using System.Globalization;using OwnerLayout;
class Harness {
static void Check(bool value){if(!value)throw new Exception("touch layout assertion");}
static void Refuse(Action action){try{action();}catch(ArgumentException){return;}throw new Exception("accepted invalid document");}
static void Busy(Action action){try{action();}catch(InvalidOperationException){return;}throw new Exception("changed active transaction");}
static TouchControl Control(string id){return new TouchControl(id,new LayoutRect(.1,.2,.3,.4),1,.7);}
static void Main(){
var controls=new[]{Control("generic_1"),Control("generic_2")};
var profile=new TouchProfile("portrait",controls);controls[0]=Control("changed");
var profiles=new[]{profile,new TouchProfile("landscape",new[]{Control("generic_1")})};
var doc=new TouchLayoutDocument(profiles);profiles[0]=profiles[1];
profile.Controls[0]=null;doc.Profiles[0]=null;
Check(doc.Find("portrait").Find("generic_1").Id=="generic_1");
string original=doc.Export();
CultureInfo.CurrentCulture=new CultureInfo("fr-FR");
Check(TouchLayoutDocument.Import(original).Export()==original);
var editor=new TouchLayoutEditor(doc);
Check(!editor.Undo()&&!editor.Redo());
editor.Begin("portrait","generic_1");
editor.DragResize(new LayoutRect(-.1,2,.01,.01),new LayoutProjection(1000,500,0,0,0,0),100,50);
Check(editor.Draft.Rectangle.X==0&&editor.Draft.Rectangle.Width==.1&&editor.Draft.Rectangle.Y==.9);
editor.SetDraft(editor.Draft.Rectangle,2,.4);
Check(editor.Document.Export()==original&&editor.SelectedProfile=="portrait");
Busy(()=>editor.Begin("landscape","generic_1"));Busy(()=>editor.Import(original));Busy(()=>editor.Reset("portrait"));Busy(()=>editor.Undo());
Refuse(()=>editor.SetDraft(new LayoutRect(2,0,.2,.2),1,1));Check(editor.Draft.Scale==2);
editor.Cancel();editor.Cancel();Check(editor.Document.Export()==original&&editor.Draft==null);
editor.Begin("portrait","generic_1");editor.SetDraft(new LayoutRect(.2,.3,.4,.5),2,0);editor.Confirm();
string changed=editor.Document.Export();Check(changed!=original&&editor.SelectedProfile==null);
Check(editor.Document.Find("landscape").Find("generic_1").Scale==1);
Check(editor.Undo()&&editor.Document.Export()==original);Check(editor.Redo()&&editor.Document.Export()==changed);
editor.Reset("portrait");Check(editor.Document.Export()==original);Check(editor.Undo()&&editor.Document.Export()==changed);
editor.Import(original);Check(!editor.Redo()&&editor.Document.Export()==original);Check(editor.Undo()&&editor.Document.Export()==changed);
foreach(string bad in new[]{original.Replace("touch-layout\t1","touch-layout\t2"),original.Replace("0.1","NaN"),
 original.Replace("0.1","-1"),original.Replace("generic_2","generic_1"),original.Replace("landscape","portrait"),
 original.Replace("P\tportrait","P\tbad name"),original.Replace("C\t","X\t"),original+"\n",original.TrimEnd('\n'),
 "touch-layout\t1\nP\tempty\n","touch-layout\t1\n",new string('x',TouchLayoutDocument.MaximumTextLength+1)}){
 Refuse(()=>editor.Import(bad));Check(editor.Document.Export()==changed);
}
Check(editor.Redo()&&editor.Document.Export()==original); // failed imports preserved history
Refuse(()=>new TouchControl("bad/id",new LayoutRect(0,0,1,1),1,1));
Refuse(()=>new TouchControl("id",new LayoutRect(0,0,1,1),double.NaN,1));
Refuse(()=>new TouchControl("id",new LayoutRect(0,0,1,1),1,1.1));
Refuse(()=>new TouchProfile("p",new[]{Control("same"),Control("same")}));
Refuse(()=>editor.Reset("unknown"));Check(editor.Document.Export()==original);
for(int i=0;i<40;i++){editor.Begin("portrait","generic_1");editor.SetDraft(new LayoutRect(.1,.2,.3,.4),1,i/40.0);editor.Confirm();}
int count=0;while(editor.Undo())count++;Check(count==32);
editor.Begin("portrait","generic_1");editor.Confirm();Check(!editor.Redo());
var maximum=new TouchProfile[16];for(int p=0;p<16;p++){
 var many=new TouchControl[128];for(int c=0;c<128;c++)many[c]=Control("control_"+c+new string('a',50));
 maximum[p]=new TouchProfile("profile_"+p,many);
}
var big=new TouchLayoutDocument(maximum);Check(TouchLayoutDocument.Import(big.Export()).Profiles.Length==16);
Refuse(()=>new TouchLayoutDocument(new TouchProfile[17]));Refuse(()=>new TouchProfile("p",new TouchControl[129]));
Console.WriteLine("touch layout PASS");}}
"""


class TouchLayoutDocumentTests(unittest.TestCase):
    def test_source_boundary(self):
        source = (LAYOUT / "TouchLayoutDocument.cs").read_text()
        self.assertNotIn("UnityEngine", source)
        self.assertNotIn("System.IO", source)
        self.assertIn("public const int Schema = 1", source)

    def test_actual_touch_document(self):
        self.assertIn("touch layout PASS", run_csharp(HARNESS, ["LayoutProjection.cs", "TouchLayoutDocument.cs"]))
