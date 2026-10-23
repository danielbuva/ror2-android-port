using System;
using System.Linq;
namespace UnityEngine
{
    public class Object
    {
        public string name;
        public static bool operator !(Object value) => value == null;
    }
}
namespace RoR2
{
    public sealed class NetworkSoundEventDef : UnityEngine.Object
    {
        public string eventName;
        public RoR2.Audio.NetworkSoundEventIndex index;
        public uint akId;
    }
    public struct ResourceAvailability
    {
        public bool available;
        public void MakeAvailable() { available = true; }
    }
    public static class WholeCatalogComposed
    {
        public static NetworkSoundEventDef[] Definitions = Array.Empty<NetworkSoundEventDef>();
        public static NetworkSoundEventDef[] DefinitionFamily(NetworkSoundEventDef[] selected) => Definitions;
    }
}
namespace RoR2.Audio
{
    public enum NetworkSoundEventIndex { Invalid = -1 }
    public static class NetworkSoundEventCatalog
    {
        static RoR2.NetworkSoundEventDef[] entries = Array.Empty<RoR2.NetworkSoundEventDef>();
        public static int networkSoundCount => entries.Length;
        public static int setCalls;
        public static int mappedEventNameCount;
        public static bool throwAfterSet;
        public static string zeroEventName;
        public static RoR2.ResourceAvailability availability;
        public static RoR2.NetworkSoundEventDef GetNetworkSoundEventDef(NetworkSoundEventIndex index) => entries[(int)index];
        public static void SetNetworkSoundEvents(RoR2.NetworkSoundEventDef[] values)
        {
            setCalls++;
            entries = (RoR2.NetworkSoundEventDef[])values.Clone();
            Array.Sort(entries, (a, b) => String.CompareOrdinal(a.name, b.name));
            mappedEventNameCount = 0;
            for (int i = 0; i < entries.Length; i++)
            {
                entries[i].index = (NetworkSoundEventIndex)i;
                mappedEventNameCount++;
                uint mapped = 2166136261u;
                foreach (char character in entries[i].eventName) mapped = (mapped ^ character) * 16777619u;
                entries[i].akId = entries[i].eventName == zeroEventName ? 0u : mapped;
            }
            if (throwAfterSet) throw new InvalidOperationException("fixture setter failure");
        }
        public static void Reset(RoR2.NetworkSoundEventDef[] values = null)
        {
            entries = values ?? Array.Empty<RoR2.NetworkSoundEventDef>(); setCalls = 0;
            mappedEventNameCount = 0; throwAfterSet = false; zeroEventName = null;
            availability = default(RoR2.ResourceAvailability);
        }
    }
}
