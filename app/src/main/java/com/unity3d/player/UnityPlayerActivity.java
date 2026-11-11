package com.unity3d.player;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.TextView;

/**
 * Fallback x64 host activity when Unity player payload is not yet mounted in ror2_payload.
 * Replaced or hooked by converted game payload once imported.
 */
public class UnityPlayerActivity extends Activity {
    static {
        try {
            System.loadLibrary("ror2_x64_bridge");
            System.loadLibrary("il2cpp");
        } catch (UnsatisfiedLinkError ignored) {
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView view = new TextView(this);
        view.setGravity(Gravity.CENTER);
        view.setBackgroundColor(0xFF182B31);
        view.setTextColor(0xFFF0F1DF);
        view.setTextSize(18f);
        String abi = (Build.SUPPORTED_64_BIT_ABIS != null && Build.SUPPORTED_64_BIT_ABIS.length > 0)
                ? Build.SUPPORTED_64_BIT_ABIS[0]
                : Build.CPU_ABI;
        view.setText("Risk of Rain 2 · Android x64 (x86_64) Runtime\nActive ABI: " + abi + "\nWaiting for converted PC payload in ror2_payload/");
        setContentView(view);
    }
}
