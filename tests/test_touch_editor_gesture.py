"""Synthetic editor pointer events; no gameplay input dispatch or digitizer claims."""

import unittest
from tests.layout_csharp import LAYOUT, run_csharp

HARNESS = r"""
using System;using OwnerLayout;
class Harness {
static void Check(bool value){if(!value)throw new Exception("gesture assertion");}
static void Near(double a,double b){Check(Math.Abs(a-b)<1e-8);}
static void Main(){
var doc=new TouchLayoutDocument(new[]{new TouchProfile("p",new[]{
 new TouchControl("bottom",new LayoutRect(.1,.1,.4,.4),1,1),new TouchControl("top",new LayoutRect(.2,.2,.2,.2),1,.5)})});
var editor=new TouchLayoutEditor(doc);var gesture=new TouchEditorGesture(editor,50,30);
var projection=new LayoutProjection(1000,600,100,50,100,50); // safe800x500
string original=doc.Export();
Check(!gesture.Down(1,0,0,projection,"p",false));Check(!gesture.Active&&editor.Draft==null);
Check(gesture.Down(7,300,200,projection,"p",false));Check(editor.Draft.Id=="top");
Check(!gesture.Down(8,300,200,projection,"p",false));Check(!gesture.Move(8,600,400,projection));Check(!gesture.Up(8,600,400,projection));Check(!gesture.CancelPointer(8));
Check(gesture.Move(7,380,250,projection));Near(editor.Draft.Rectangle.X,.3);Near(editor.Draft.Rectangle.Y,.3);Check(editor.Document.Export()==original);
Check(gesture.Move(7,380,250,projection));Near(editor.Draft.Rectangle.X,.3); // absolute origin, no accumulated drift
Check(gesture.Up(7,380,250,projection));Check(!gesture.Active&&editor.Draft==null);string changed=editor.Document.Export();Check(changed!=original);
Check(!gesture.Up(7,380,250,projection));Check(editor.Undo()&&editor.Document.Export()==original);Check(editor.Redo()&&editor.Document.Export()==changed);
Check(gesture.Down(2,380,250,projection,"p",true));Check(gesture.Move(2,-1000,-1000,projection));Near(editor.Draft.Rectangle.Width,50.0/800);Near(editor.Draft.Rectangle.Height,30.0/500);
gesture.Cancel();gesture.Cancel();Check(editor.Document.Export()==changed&&editor.Draft==null);
Check(gesture.Down(3,380,250,projection,"p",false));Check(gesture.Move(3,10000,10000,projection));Near(editor.Draft.Rectangle.X,.8);Near(editor.Draft.Rectangle.Y,.8);Check(gesture.CancelPointer(3));Check(editor.Document.Export()==changed);
foreach(var next in new[]{new LayoutProjection(600,1000,50,100,50,100),new LayoutProjection(1000,600,110,50,100,50),new LayoutProjection(1600,600,100,50,100,50)}){
 Check(gesture.Down(4,380,250,projection,"p",false));Check(!gesture.Up(4,400,300,next));Check(!gesture.Active&&editor.Draft==null&&editor.Document.Export()==changed);
}
// Invalid samples do not silently commit or mutate the active draft.
Check(gesture.Down(5,380,250,projection,"p",false));var before=editor.Draft;
try{gesture.Move(5,double.NaN,0,projection);throw new Exception("accepted NaN");}catch(ArgumentException){}
Check(editor.Draft==before&&gesture.Active);gesture.Cancel();
// Gesture helper must not cancel an externally owned draft when idle.
editor.Begin("p","bottom");gesture.Cancel();Check(editor.Draft!=null);
try{gesture.Down(6,300,200,projection,"p",false);throw new Exception("stole external draft");}catch(InvalidOperationException){}
editor.Cancel();
Check(gesture.Down(9,380,250,projection,"p",true));Check(gesture.Up(9,460,300,projection));Near(editor.Document.Find("p").Find("top").Rectangle.Width,.3);Near(editor.Document.Find("p").Find("top").Rectangle.Height,.3);
// Bottom-right resizing must never move the opposite corner, even when
// the requested minimum is larger than the remaining safe-area span.
foreach(bool oversizedMinimum in new[]{false,true}){
 var edgeDoc=new TouchLayoutDocument(new[]{new TouchProfile("p",new[]{new TouchControl("edge",new LayoutRect(.7,.6,.2,.2),1,1)})});
 var edgeEditor=new TouchLayoutEditor(edgeDoc);var edgeGesture=new TouchEditorGesture(edgeEditor,oversizedMinimum?10000:50,oversizedMinimum?10000:30);
 Check(edgeGesture.Down(10,700,375,projection,"p",true));Check(edgeGesture.Move(10,860,525,projection));
 Near(edgeEditor.Draft.Rectangle.X,.7);Near(edgeEditor.Draft.Rectangle.Y,.6);Near(edgeEditor.Draft.Rectangle.Width,.3);Near(edgeEditor.Draft.Rectangle.Height,.4);
 Check(edgeEditor.Document.Export()==edgeDoc.Export());
 Check(edgeGesture.Move(10,-1000,-1000,projection));Near(edgeEditor.Draft.Rectangle.X,.7);Near(edgeEditor.Draft.Rectangle.Y,.6);
 Near(edgeEditor.Draft.Rectangle.Width,oversizedMinimum?.3:50.0/800);Near(edgeEditor.Draft.Rectangle.Height,oversizedMinimum?.4:30.0/500);
 Check(edgeGesture.Up(10,860,525,projection));var edge=edgeEditor.Document.Find("p").Find("edge").Rectangle;
 Near(edge.X,.7);Near(edge.Y,.6);Near(edge.Width,.3);Near(edge.Height,.4);
 Check(edgeEditor.Undo()&&edgeEditor.Document.Export()==edgeDoc.Export());
}
// A stationary tap or returning to the origin must preserve authored
// rectangles below the editor minimum and must not consume undo/redo history.
foreach(bool resize in new[]{false,true}){
 var tinyDoc=new TouchLayoutDocument(new[]{new TouchProfile("p",new[]{new TouchControl("tiny",new LayoutRect(.2,.2,.02,.02),1,1)})});
 var tinyEditor=new TouchLayoutEditor(tinyDoc);var tinyGesture=new TouchEditorGesture(tinyEditor,50,30);
 Check(tinyGesture.Down(11,264,154,projection,"p",resize));Check(tinyGesture.Up(11,264,154,projection));
 Check(!tinyGesture.Active&&tinyEditor.Draft==null&&tinyEditor.Document.Export()==tinyDoc.Export()&&!tinyEditor.Undo());
 Check(tinyGesture.Down(12,264,154,projection,"p",resize));Check(tinyGesture.Up(12,304,184,projection));
 var moved=tinyEditor.Document.Export();Check(moved!=tinyDoc.Export()&&tinyEditor.Undo());
 Check(tinyGesture.Down(13,264,154,projection,"p",resize));Check(tinyGesture.Move(13,304,184,projection));
 Check(tinyGesture.Up(13,264,154,projection));Check(tinyEditor.Document.Export()==tinyDoc.Export());
 Check(!tinyEditor.Undo()&&tinyEditor.Redo()&&tinyEditor.Document.Export()==moved);
}
// A non-stationary gesture that clamps to the same rectangle is also a no-op.
var fullDoc=new TouchLayoutDocument(new[]{new TouchProfile("p",new[]{new TouchControl("full",new LayoutRect(0,0,1,1),1,1)})});
var fullEditor=new TouchLayoutEditor(fullDoc);var fullGesture=new TouchEditorGesture(fullEditor,50,30);
Check(fullGesture.Down(14,300,200,projection,"p",false));Check(fullGesture.Up(14,900,300,projection));
Check(fullEditor.Document.Export()==fullDoc.Export()&&!fullEditor.Undo());
Console.WriteLine("touch gesture PASS");}}
"""


class TouchEditorGestureTests(unittest.TestCase):
    def test_editor_only_boundary(self):
        source = (LAYOUT / "TouchEditorGesture.cs").read_text()
        self.assertNotIn("UnityEngine", source)
        self.assertNotIn("System.IO", source)
        self.assertIn("editor.Confirm()", source)

    def test_actual_editor_gesture(self):
        self.assertIn("touch gesture PASS", run_csharp(HARNESS, ["LayoutProjection.cs", "TouchLayoutDocument.cs", "TouchEditorGesture.cs"]))
