using System;

namespace RoR2
{
    public static class AndroidCommandoPostObserver
    {
        public static Action<uint, object> Returned;

        public static void Record(uint playingId, object emitter)
        {
            try { Returned?.Invoke(playingId, emitter); }
            catch { }
        }
    }
}
