package dev.ror2owner.bootstrap;

import android.content.Context;
import java.io.File;
import org.json.JSONArray;
import org.json.JSONObject;

public final class ProfileStore {
    private final Context context;
    private final File profilesDir;

    public ProfileStore(Context context) {
        this.context = context;
        this.profilesDir = new File(context.getFilesDir(), "profiles");
        if (!profilesDir.exists()) profilesDir.mkdirs();
    }

    public JSONObject getSummaryJson() {
        JSONObject json = new JSONObject();
        try {
            JSONArray list = new JSONArray();
            File[] files = profilesDir.listFiles();
            if (files != null) {
                for (File f : files) {
                    list.put(f.getName());
                }
            }
            json.put("profiles", list);
            json.put("count", list.length());
        } catch (Throwable t) {
            // ignore
        }
        return json;
    }
}
