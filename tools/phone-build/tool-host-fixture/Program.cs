using System.Globalization;
using System.Runtime;
using System.Security.Cryptography;
using System.Text;

sealed class Node(long id, string name, Node? parent)
{
    public readonly long Id = id;
    public readonly string Name = name;
    public readonly Node? Parent = parent;
    public readonly List<Node> Children = new();
    public readonly byte[] Payload = new byte[32];
}

static class Program
{
    static int Main(string[] args)
    {
        if (args.Length != 1 || (args[0] != "--self-test" && args[0] != "--graph")) return 3;
        string digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes("ror2-tool-host-fixture-v1\n"))).ToLowerInvariant();
        if (digest != "cee05eb8a363fd88bcd8f840066bf358cbb9d70ab1f19b7c20c4f0e1109904ff") return 2;
        int count = args[0] == "--self-test" ? 4096 : 262144;
        var nodes = new Node[count];
        for (int i = 0; i < count; i++)
        {
            var parent = i == 0 ? null : nodes[(i - 1) / 2];
            var node = new Node(i, "fixture-node-" + i.ToString(CultureInfo.InvariantCulture), parent);
            for (int j = 0; j < node.Payload.Length; j++) node.Payload[j] = (byte)(i + j);
            parent?.Children.Add(node);
            nodes[i] = node;
        }
        bool valid = true;
        ulong sum = 0, witness = 0;
        for (int i = 0; i < count; i++)
        {
            var node = nodes[i];
            valid &= node.Id == i && node.Name == "fixture-node-" + i.ToString(CultureInfo.InvariantCulture);
            valid &= node.Parent == (i == 0 ? null : nodes[(i - 1) / 2]);
            int expectedChildren = Math.Clamp(count - (2 * i + 1), 0, 2);
            valid &= node.Children.Count == expectedChildren && node.Payload.Length == 32;
            sum += (ulong)node.Id;
            witness += (ulong)node.Id + (ulong)(node.Parent == null ? 0 : node.Parent.Id + 1) + (ulong)node.Children.Count;
            foreach (char c in node.Name) witness += c;
            for (int j = 0; j < node.Payload.Length; j++)
            {
                valid &= node.Payload[j] == (byte)(i + j);
                witness += node.Payload[j];
            }
            for (int j = 0; j < node.Children.Count; j++)
            {
                valid &= node.Children[j] == nodes[2 * i + 1 + j];
                witness += (ulong)node.Children[j].Id + 1;
            }
        }
        valid &= sum == (ulong)count * (ulong)(count - 1) / 2;
        long live = GC.GetTotalMemory(true);
        Console.WriteLine("{\"schema\":2,\"success\":" + (valid ? "true" : "false") + ",\"count\":" + count + ",\"sum\":" + sum + ",\"witness\":" + witness + ",\"sha256\":\"" + digest + "\",\"live_managed_bytes\":" + live + ",\"server_gc\":" + (GCSettings.IsServerGC ? "true" : "false") + ",\"game_runtime_qualified\":false}");
        Thread.Sleep(2000);
        GC.KeepAlive(nodes);
        return valid ? 0 : 2;
    }
}
