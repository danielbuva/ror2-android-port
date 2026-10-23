// API shape only for the combined PCM/coordinator compilation fixture.
// Catalog behavior is exercised with controlled observations in CatalogOwnerHarness.
namespace RoR2
{
    public sealed class NetworkSoundEventDef : UnityEngine.Object
    {
        public string eventName;
        public Audio.NetworkSoundEventIndex index;
        public uint akId;
    }
    public struct ResourceAvailability
    {
        public bool available;
        public void MakeAvailable() { available = true; }
    }
}
namespace RoR2.Audio
{
    public enum NetworkSoundEventIndex { Invalid = -1 }
    public static class NetworkSoundEventCatalog
    {
        public static int networkSoundCount => 0;
        public static RoR2.ResourceAvailability availability;
        public static void SetNetworkSoundEvents(RoR2.NetworkSoundEventDef[] values) { }
        public static RoR2.NetworkSoundEventDef GetNetworkSoundEventDef(NetworkSoundEventIndex index) => null;
    }
}
