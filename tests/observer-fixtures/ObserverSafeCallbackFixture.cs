using OriginalOwnerProbeObserver;

var token = new object();
int called = 0;
int seenResult = 0;
ulong seenId = 0;
object seenOwner = null!;
Observer.MusicAddOutputReturned = (result, owner, id) =>
{
    called++;
    seenResult = result;
    seenOwner = owner;
    seenId = id;
};
Observer.RecordMusicAddOutputReturned(1, token, 0x1234UL);
if (called != 1 || seenResult != 1 || !ReferenceEquals(seenOwner, token) || seenId != 0x1234UL)
    throw new Exception("add result observer did not forward the exact bounded values");
Observer.MusicRemoveOutputReturned = (_, _, _) => throw new InvalidOperationException("observer fixture");
Observer.RecordMusicRemoveOutputReturned(4, token, 0x1234UL);
Console.WriteLine("safe callbacks forward exact scalar arguments and swallow observer exceptions");
