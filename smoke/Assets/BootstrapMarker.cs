using UnityEngine;
public class BootstrapMarker : MonoBehaviour
{
    void Start() { Debug.Log("ROR2_BOOTSTRAP_ARM64_OK | " + SystemInfo.processorType + " | " + SystemInfo.graphicsDeviceName); }
    void OnGUI()
    {
        GUIStyle style = new GUIStyle(GUI.skin.label) { fontSize = 36, alignment = TextAnchor.MiddleCenter };
        GUI.Label(new Rect(0, 0, Screen.width, Screen.height), "ARM64 ANDROID\nBOOTSTRAP OK\nUnity 2021.3.33f1", style);
    }
}
