using System;
using System.Security.Cryptography;
using System.Text;
class Hello {
    static int Main() {
        byte[] digest = SHA256.HashData(Encoding.UTF8.GetBytes("authored-phone-build-host-v1"));
        Console.WriteLine("PHONE_TOOL_HOST_OK " + Environment.Version + " " + Convert.ToHexString(digest).ToLowerInvariant());
        return 0;
    }
}
