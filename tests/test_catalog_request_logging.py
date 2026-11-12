"""Compile the request observer and exercise unchanged locator semantics."""

import unittest

from test_native_commerce_release_order import braced_block, repo_root
from test_retained_catalog_dependencies import execute_host


FIXTURE = r"""
using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
interface IResourceLocation {}
interface IResourceLocator {
 string LocatorId { get; }
 IEnumerable<object> Keys { get; }
 bool Locate(object key, Type type, out IList<IResourceLocation> locations);
}
static class Debug {
 public static readonly List<string> Lines = new List<string>();
 public static void Log(object value) { Lines.Add((string)value); }
}
class Map : IResourceLocator {
 public string LocatorId => "original-whole-catalog";
 public IEnumerable<object> Keys => keys;
 public readonly object[] keys = { "main" };
 public readonly IList<IResourceLocation> rows = new List<IResourceLocation>();
 public object requestedKey; public Type requestedType; public int calls;
 public bool Locate(object key, Type type, out IList<IResourceLocation> locations) {
  calls++; requestedKey=key; requestedType=type;
  bool found=Equals(key,"main"); locations=found?rows:null; return found;
 }
}
class Host {
 static string phase = "catalog:SkinCatalog";
 OBSERVER
 static void Need(bool value) { if(!value) throw new Exception("locator contract changed"); }
 static void Main(string[] args) {
  var map=new Map(); IResourceLocator observer=new RequestLoggingLocator(map);
  Need(ReferenceEquals(observer.Keys,map.keys) && observer.LocatorId==map.LocatorId);
  IList<IResourceLocation> rows;
  Need(observer.Locate("main",typeof(Host),out rows) && ReferenceEquals(rows,map.rows));
  Need(map.calls==1 && Equals(map.requestedKey,"main") && map.requestedType==typeof(Host));
  string subobject="1234567890abcdef1234567890abcdef[mesh]";
  Need(!observer.Locate(subobject,null,out rows) && rows==null && map.calls==2);
  Need(!observer.Locate(null,typeof(int),out rows) && rows==null && map.calls==3);
  Need(Debug.Lines.Count==3);
  var hit=JObject.Parse(Debug.Lines[0].Substring("whole-catalog-request ".Length));
  var miss=JObject.Parse(Debug.Lines[1].Substring("whole-catalog-request ".Length));
  Need((bool)hit["locatorFound"] && (string)hit["phase"]==phase);
  Need((string)hit["type"]==typeof(Host).AssemblyQualifiedName);
  Need(!(bool)miss["locatorFound"] && (string)miss["key"]==subobject);
  Need(miss["type"].Type==JTokenType.Null && (int)miss["locations"]==0);
  Console.WriteLine("PASS request observer");
 }
}
"""


class CatalogRequestLoggingTests(unittest.TestCase):
    def test_interface_dispatch_preserves_hits_misses_and_subobject_keys(self):
        source = (repo_root() / "tools/unity/runtime/catalog/WholeCatalogLoader.cs").read_text()
        fixture = FIXTURE.replace("OBSERVER", braced_block(source, "sealed class RequestLoggingLocator"))
        result = execute_host(fixture, "observer")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS request observer", result.stdout)
