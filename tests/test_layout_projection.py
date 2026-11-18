"""Authored geometry only; no Unity/runtime input or display qualification."""

import unittest
from tests.layout_csharp import LAYOUT, run_csharp

HARNESS = r"""
using System;using OwnerLayout;
class Harness {
static void Check(bool b){if(!b)throw new Exception("projection assertion");}
static void Near(double a,double b){Check(Math.Abs(a-b)<1e-8);}
static void Same(LayoutRect a,LayoutRect b){Near(a.X,b.X);Near(a.Y,b.Y);Near(a.Width,b.Width);Near(a.Height,b.Height);}
static void Refuse(Action a){try{a();}catch(ArgumentException){return;}throw new Exception("accepted invalid geometry");}
static void Main(){
foreach(var size in new[]{new[]{1920.0,1080.0},new[]{1080.0,1920.0},new[]{2560.0,1080.0},new[]{1024.0,768.0}}){
 var p=new LayoutProjection(size[0],size[1],20,30,40,50);
 foreach(var r in new[]{new LayoutRect(0,0,1,1),new LayoutRect(.1,.2,.3,.4),new LayoutRect(.8,.8,.2,.2)}){
  Same(p.Unproject(p.Project(r)),r);var turned=r;for(int i=0;i<4;i++)turned=LayoutProjection.RotateClockwise(turned);Same(turned,r);
 }
 var small=p.Clamp(new LayoutRect(-.2,2,.01,.01),100,100);Near(small.X,0);Near(p.Project(small).Width,100);Near(p.Project(small).Height,100);
 var huge=p.Clamp(new LayoutRect(2,-1,3,4),size[0]*2,size[1]*2);Same(huge,new LayoutRect(0,0,1,1));
 Refuse(()=>p.Project(new LayoutRect(-1,0,1,1)));Refuse(()=>p.Unproject(new LayoutRect(0,0,1,1)));Refuse(()=>p.Clamp(new LayoutRect(0,0,1,1),double.NaN,0));
}
var edge=new LayoutProjection(375,100,7,0,0,0);var edgeRect=new LayoutRect(.8,0,.2,1);
Same(edge.Unproject(edge.Project(edgeRect)),edgeRect);
Refuse(()=>edge.Unproject(new LayoutRect(7-1e-6,0,100,100)));
Refuse(()=>new LayoutProjection(100,100,50,0,50,0));Refuse(()=>new LayoutProjection(100,100,-1,0,0,0));
Refuse(()=>new LayoutRect(0,0,0,1));Refuse(()=>new LayoutRect(double.NaN,0,1,1));Refuse(()=>LayoutProjection.RequireNormalized(default(LayoutRect)));
Console.WriteLine("layout projection PASS");}}
"""


class LayoutProjectionTests(unittest.TestCase):
    def test_dependency_and_coordinate_contract(self):
        source = (LAYOUT / "LayoutProjection.cs").read_text()
        self.assertNotIn("UnityEngine", source)
        self.assertIn("top-left origin", source)
        self.assertIn("public const int Schema = 1", source)

    def test_actual_projection_geometry(self):
        self.assertIn("layout projection PASS", run_csharp(HARNESS, ["LayoutProjection.cs"]))
