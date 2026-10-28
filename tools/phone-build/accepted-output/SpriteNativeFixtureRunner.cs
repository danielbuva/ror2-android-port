// Current SDK-only device diagnostic. Inputs and results stay in app-private files.
using System;
using System.IO;
using UnityEngine;

public sealed class SpriteNativeFixtureRunner : MonoBehaviour
{
    void Start()
    {
        Application.targetFrameRate = 15;
        string root = Application.persistentDataPath;
#if UNITY_ANDROID && !UNITY_EDITOR
        using (var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
        using (var activity = player.GetStatic<AndroidJavaObject>("currentActivity"))
        using (var directory = activity.Call<AndroidJavaObject>("getFilesDir"))
            root = directory.Call<string>("getAbsolutePath");
#endif
        try
        {
            SpriteNativeFixture.Run(Path.Combine(root, "sprite-source-request.json"), Path.Combine(root, "sprite-source-result.json"));
            Debug.Log("SPRITE_NATIVE_FIXTURE_OK");
        }
        catch (Exception error)
        {
            File.WriteAllText(Path.Combine(root, "sprite-source-error.txt"), error.ToString());
            Debug.LogException(error);
        }
    }
}
