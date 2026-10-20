// Authored input for the isolated IL2CPP converter probe; no Unity/game APIs.
namespace PhoneBuildFixture
{
    public static class Arithmetic
    {
        public static int Fold(int seed)
        {
            int value = seed;
            for (int i = 0; i < 17; ++i) value = unchecked(value * 31 + i);
            return value;
        }
    }
}
