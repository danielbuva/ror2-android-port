using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace OwnerConversion
{
    // Disposable tool entry point. The device controller supplies request.json
    // before launch; all input/output stays inside this tool's private storage.
    public sealed class RuntimeEnvironmentTool : MonoBehaviour
    {
        IEnumerator Start()
        {
            string root = Application.persistentDataPath;
            string input = Path.Combine(root, "request.json");
            Debug.Log("OWNER_ENVIRONMENT_ROOT " + root);
            float started = Time.realtimeSinceStartup;
            while (!File.Exists(input) && Time.realtimeSinceStartup - started < 120)
                yield return null;
            try
            {
                var request = JsonUtility.FromJson<RuntimeEnvironmentProducer.Request>(
                    File.ReadAllText(input));
                GetComponent<RuntimeEnvironmentProducer>().Begin(request,
                    Path.Combine(root, "output-" + request.id));
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                File.WriteAllText(Path.Combine(Application.persistentDataPath, "startup-error.txt"), error.ToString());
            }
        }
    }
}
