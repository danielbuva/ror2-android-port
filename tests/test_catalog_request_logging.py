"""Compile the request observer and exercise unchanged locator semantics."""

import unittest

from test_native_commerce_release_order import braced_block, repo_root
from test_retained_catalog_dependencies import execute_host


FIXTURE = r"""
using System;
using System.Collections.Generic;
using System.Reflection;
using Newtonsoft.Json.Linq;
interface IResourceLocation {
 string InternalId { get; }
 string PrimaryKey { get; }
 string ProviderId { get; }
 IList<IResourceLocation> Dependencies { get; }
}
class Location : IResourceLocation {
 public string InternalId { get; set; }
 public string PrimaryKey => InternalId;
 public string ProviderId => "authored-provider";
 public IList<IResourceLocation> Dependencies { get; set; }
}
struct AsyncOperationHandle {
 public string DebugName;
 public string Status;
 public Exception OperationException;
 public object Result;
 public bool IsDone => true;
 public bool IsValid() {return true;}
}
class ResourceManager {
 internal bool postProfilerEvents;
 public enum DiagnosticEventType { AsyncOperationComplete, AsyncOperationFail, AsyncOperationCreate }
 public struct DiagnosticEventContext {
  public AsyncOperationHandle OperationHandle;
  public DiagnosticEventType Type;
  public IResourceLocation Location;
  public string Error;
 }
 public Action<DiagnosticEventContext> Callback;
 public void RegisterDiagnosticCallback(Action<DiagnosticEventContext> cb) {Callback+=cb;}
 public void UnregisterDiagnosticCallback(Action<DiagnosticEventContext> cb) {Callback-=cb;}
 public void Emit(DiagnosticEventContext context) {if(postProfilerEvents) Callback?.Invoke(context);}
}
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
 OPERATIONS
 static void Need(bool value) { if(!value) throw new Exception("locator contract changed"); }
 static void Main(string[] args) {
  var map=new Map(); IResourceLocator observer=new RequestLoggingLocator(map);
  map.rows.Add(new Location { InternalId="member", Dependencies=new List<IResourceLocation> {new Location {InternalId="bundle"}} });
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
  Need((string)hit["resolved"][0]["member"]=="member" && (string)hit["resolved"][0]["bundle"]=="bundle");
  Need(!(bool)miss["locatorFound"] && (string)miss["key"]==subobject);
  Need(miss["type"].Type==JTokenType.Null && (int)miss["locations"]==0);
  var manager=new ResourceManager(); int priorCalls=0;
  manager.Callback+=context=>priorCalls++;
  var operation=new ResourceManager.DiagnosticEventContext {
   OperationHandle=new AsyncOperationHandle { DebugName="skin-params", Status="Succeeded", Result=new Host() },
   Location=map.rows[0], Type=ResourceManager.DiagnosticEventType.AsyncOperationComplete
  };
  using(var observerOperations=new OperationLoggingObserver(manager)) {
   manager.Emit(operation);
   operation.Type=ResourceManager.DiagnosticEventType.AsyncOperationFail;
   operation.OperationHandle=new AsyncOperationHandle { DebugName="missing-mesh", Status="Failed" };
   operation.Error="authored missing asset";
   manager.Emit(operation);
  }
  Need(!manager.postProfilerEvents && priorCalls==2 && Debug.Lines.Count==5);
  var complete=JObject.Parse(Debug.Lines[3].Substring("whole-catalog-operation ".Length));
  var failed=JObject.Parse(Debug.Lines[4].Substring("whole-catalog-operation ".Length));
  Need((string)complete["status"]=="Succeeded" && (string)complete["member"]=="member");
  Need((string)failed["status"]=="Failed" && (string)failed["exception"]==operation.Error);
  manager.postProfilerEvents=true; manager.Emit(operation);
  Need(priorCalls==3 && Debug.Lines.Count==5);
  Console.WriteLine("PASS request observer");
 }
}
"""


class CatalogRequestLoggingTests(unittest.TestCase):
    def test_interface_dispatch_preserves_hits_misses_and_subobject_keys(self):
        source = (repo_root() / "tools/unity/runtime/catalog/WholeCatalogLoader.cs").read_text()
        fixture = FIXTURE.replace("OBSERVER", braced_block(source, "sealed class RequestLoggingLocator"))
        fixture = fixture.replace("OPERATIONS", braced_block(source, "sealed class OperationLoggingObserver"))
        result = execute_host(fixture, "observer")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS request observer", result.stdout)
