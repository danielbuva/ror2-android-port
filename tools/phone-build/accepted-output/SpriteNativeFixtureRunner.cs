// Current SDK-only device diagnostic. Inputs and results stay in app-scoped files.
using System;
using System.Collections;
using System.IO;
using UnityEngine;

public sealed class SpriteNativeFixtureRunner : MonoBehaviour
{
    IEnumerator Start()
    {
        Application.targetFrameRate = 15;
        string root = Application.persistentDataPath;
        Directory.CreateDirectory(root);
        string request = Path.Combine(root, "sprite-source-request.json");
        Debug.Log("SPRITE_NATIVE_FIXTURE_ROOT " + root);
        float deadline = Time.realtimeSinceStartup + 120f;
        while (!File.Exists(request) && Time.realtimeSinceStartup < deadline)
            yield return new WaitForSecondsRealtime(0.25f);
        try
        {
            SpriteNativeFixture.Run(request, Path.Combine(root, "sprite-source-result.json"));
            Debug.Log("SPRITE_NATIVE_FIXTURE_OK");
        }
        catch (Exception error)
        {
            File.WriteAllText(Path.Combine(root, "sprite-source-error.txt"), error.ToString());
            Debug.LogException(error);
        }
    }
}
