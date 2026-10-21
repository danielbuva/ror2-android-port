using System;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public static implicit operator bool(Object value) { return !ReferenceEquals(value, null) && !value.destroyed; }
        public bool destroyed;
    }
    public class GameObject : Object
    {
        readonly Dictionary<Type, Component> components = new Dictionary<Type, Component>();
        public bool activeInHierarchy = true;
        public T Add<T>(T component) where T : Component { component.gameObject = this; components[typeof(T)] = component; return component; }
        public Component GetComponent(Type type) { Component value; return components.TryGetValue(type, out value) ? value : null; }
    }
    public class Component : Object
    {
        public GameObject gameObject;
        public bool isActiveAndEnabled = true;
        public Component GetComponent(Type type) { return gameObject == null ? null : gameObject.GetComponent(type); }
    }
    public class MonoBehaviour : Component { }
    public static class Time { public static float deltaTime = 0.016f; }
}

namespace RoR2
{
    using UnityEngine;
    public interface ICameraStateProvider { }
    public sealed class RoR2Application : MonoBehaviour { public static RoR2Application instance; }
    public sealed class SceneCamera : MonoBehaviour { }
    public sealed class CameraRigController : MonoBehaviour
    {
        public GameObject nextTarget;
        public GameObject target;
        public object localUserViewer;
        public bool isCutscene;
        public int originalCalls;
        public bool throwOnOriginalCall;
        public CameraRigController contextRig;
        private void EarlyUpdate()
        {
            originalCalls++;
            if (throwOnOriginalCall) throw new InvalidOperationException("fixture callback failure");
            target = nextTarget;
            if (Time.deltaTime != 0f && !isCutscene)
                contextRig = this;
        }
        public void InvokeOriginalApplicationPath() { EarlyUpdate(); }
    }
}
