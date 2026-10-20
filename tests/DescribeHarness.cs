using System;
using System.Reflection;

public static class DescribeHarness
{
    static int Main(string[] args)
    {
        try
        {
            Type owner = typeof(PlayerLinkerInputCapture);
            if (args.Length == 2 && args[0] == "prepare-output")
            {
                MethodInfo prepare = owner.GetMethod("PrepareOutput", BindingFlags.NonPublic | BindingFlags.Static);
                Console.WriteLine((string)prepare.Invoke(null, new object[] { args[1] }));
                return 0;
            }
            if (args.Length == 3 && args[0] == "ancestors")
            {
                MethodInfo check = owner.GetMethod("RejectReparseAncestors", BindingFlags.NonPublic | BindingFlags.Static);
                check.Invoke(null, new object[] { args[1], args[2] });
                Console.WriteLine("accepted");
                return 0;
            }
            if (args.Length == 3 && args[0] == "existing-ancestors")
            {
                MethodInfo check = owner.GetMethod("RejectExistingReparseAncestors", BindingFlags.NonPublic | BindingFlags.Static);
                check.Invoke(null, new object[] { args[1], args[2] });
                Console.WriteLine("accepted");
                return 0;
            }
            if (args.Length != 6 || args[0] != "describe")
                throw new ArgumentException("Expected describe <input-root> <source-file> <snapshot-root> <work-root> <request-id>");
            MethodInfo describe = owner.GetMethod("Describe", BindingFlags.NonPublic | BindingFlags.Static);
            object row = describe.Invoke(null, new object[] { args[1], args[2], args[3], args[4], args[5] });
            Type rowType = row.GetType();
            string hash = (string)rowType.GetField("sha256").GetValue(row);
            long size = (long)rowType.GetField("size").GetValue(row);
            Console.WriteLine(hash + " " + size);
            return 0;
        }
        catch (TargetInvocationException ex)
        {
            Console.Error.WriteLine(ex.InnerException == null ? ex.ToString() : ex.InnerException.ToString());
            return 3;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex);
            return 2;
        }
    }
}
