package dev.ror2owner.bootstrap;

import android.content.Context;
import android.os.StatFs;
import java.io.File;
import org.json.JSONObject;

public final class PayloadStore {
    private final Context context;
    private final File payloadDir;

    public PayloadStore(Context context) {
        this.context = context;
        this.payloadDir = new File(context.getFilesDir(), "ror2_payload");
        if (!payloadDir.exists()) payloadDir.mkdirs();
    }

    public JSONObject getSummaryJson() {
        JSONObject json = new JSONObject();
        try {
            json.put("exists", payloadDir.exists() && payloadDir.list() != null && payloadDir.list().length > 0);
            json.put("path", payloadDir.getAbsolutePath());
            json.put("freeBytes", getFreeBytes());
        } catch (Throwable t) {
            // ignore
        }
        return json;
    }

    public long getFreeBytes() {
        try {
            StatFs stat = new StatFs(payloadDir.getAbsolutePath());
            return stat.getAvailableBytes();
        } catch (Throwable t) {
            return 0L;
        }
    }
}
