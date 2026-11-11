package dev.ror2lab.phonebuildhostfixture;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import android.provider.Settings;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import dev.ror2owner.graphics.GraphicsDriverFixture;
import dev.ror2owner.graphics.GraphicsDriverPackage;
import dev.ror2owner.graphics.GraphicsDriverPolicy;
import dev.ror2owner.graphics.GraphicsDriverProviders;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/** Tool-host picker preview; game-process wiring and native loading are not implemented. */
final class OwnerGraphicsPicker {
    private final Activity activity;
    private AlertDialog dialog;
    private TextView selected, choices, result;
    private GraphicsDriverPolicy.State state;
    private GraphicsDriverPolicy.Device device;
    private boolean fixture;
    OwnerGraphicsPicker(Activity activity) { this.activity = activity; }

    void show() {
        if (dialog != null && dialog.isShowing()) return;
        LinearLayout layout = new LinearLayout(activity); layout.setOrientation(LinearLayout.VERTICAL); layout.setPadding(24, 16, 24, 16);
        ScrollView scroll = new ScrollView(activity); scroll.addView(layout);
        text(layout, "Preview only: preferences are stored in this tool host, not connected to the separately installed game.");
        selected = text(layout, "Selected for next launch: System"); selected.setContentDescription("graphics-selection");
        text(layout, GraphicsDriverProviders.ActiveDriver.unavailable().summary()).setContentDescription("graphics-active");
        choices = text(layout, ""); choices.setContentDescription("graphics-choices");
        result = text(layout, ""); result.setContentDescription("graphics-result");
        state = null; device = null;
        boolean requested = activity.getIntent().getBooleanExtra("graphics_fixture", false);
        fixture = requested && Build.VERSION.SDK_INT >= 28 && GraphicsDriverFixture.allowed(activity.getPackageName(), debuggable());
        if (requested) text(layout, fixture ? "SYNTHETIC FIXTURE MODE: authored files only; no native driver execution." : "Synthetic graphics fixture refused.");
        if (Build.VERSION.SDK_INT >= 28) {
            try { state = new GraphicsDriverPolicy.State(new File(activity.getFilesDir(), "graphics-driver").toPath()); }
            catch (IOException failure) { result.setText("Graphics preferences unavailable."); }
        } else result.setText("Graphics preferences require Android API 28 or newer. System remains unchanged.");
        if (fixture) device = new GraphicsDriverPolicy.Device(0x5143, 7, Build.VERSION.SDK_INT, true);
        render();
        Button reset = button(layout, "Use System driver", new Runnable() { public void run() {
            try { GraphicsDriverProviders.resetToSystem(state); result.setText("System selected for next launch. No live driver was changed."); render(); }
            catch (IOException failure) { result.setText("Could not save System preference."); }
        } });
        reset.setEnabled(state != null);
        button(layout, "View driver source and licenses", new Runnable() { public void run() {
            AlertDialog license = new AlertDialog.Builder(activity).setTitle("Driver source and licenses")
                    .setMessage("libadrenotools: " + GraphicsDriverProviders.ADRENOTOOLS_LICENSE + "\n"
                            + GraphicsDriverProviders.ADRENOTOOLS_SOURCE + "\n\n" + GraphicsDriverProviders.EMPTY_CATALOG
                            + "\nNo proprietary Qualcomm drivers are listed or bundled.")
                    .setPositiveButton("Back to graphics drivers", null).show();
            TextView message = license.findViewById(android.R.id.message);
            if (message != null) message.setContentDescription("graphics-license");
        } });
        text(layout, GraphicsDriverProviders.SETTINGS_EXPLANATION);
        final Intent settings = developerOptions();
        Button openSettings = button(layout, "Open Android Developer options", new Runnable() { public void run() {
            try { activity.startActivity(settings); }
            catch (android.content.ActivityNotFoundException | SecurityException failure) { result.setText("Android Developer options unavailable."); }
        } });
        openSettings.setEnabled(settings != null);
        if (settings == null) text(layout, "No available system Developer-options activity.");
        if (fixture) {
            button(layout, "Verify synthetic driver file", new Runnable() { public void run() { verifyFixture(); } });
            button(layout, "Show Mali fixture", new Runnable() { public void run() {
                device = new GraphicsDriverPolicy.Device(0x13b5, 0, Build.VERSION.SDK_INT, true); render();
                result.setText("Synthetic Mali: custom activation unavailable.");
            } });
            button(layout, "Show Adreno fixture", new Runnable() { public void run() {
                device = new GraphicsDriverPolicy.Device(0x5143, 7, Build.VERSION.SDK_INT, true); render();
                result.setText("Synthetic Adreno: custom activation unavailable.");
            } });
        }
        dialog = new AlertDialog.Builder(activity).setTitle("Graphics drivers").setView(scroll).setNegativeButton("Close graphics drivers", null).create();
        dialog.show();
    }
    void close() { if (dialog != null) dialog.dismiss(); }
    private boolean debuggable() { return (activity.getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0; }
    private void render() {
        selected.setText("Selected for next launch: " + (state == null || GraphicsDriverPolicy.SYSTEM.equals(state.selected()) ? "System" : "Custom package (not active)"));
        StringBuilder body = new StringBuilder();
        // No native binding and no active-device probe exist in this tool host.
        for (GraphicsDriverProviders.Choice choice : GraphicsDriverProviders.choices(device, null))
            body.append(choice.title).append("\n").append(choice.explanation).append("\n\n");
        body.append(GraphicsDriverProviders.EMPTY_CATALOG);
        choices.setText(body.toString());
    }
    private Intent developerOptions() {
        Intent intent = new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS);
        ResolveInfo target = activity.getPackageManager().resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
        if (target == null || target.activityInfo == null || !target.activityInfo.enabled || !target.activityInfo.exported
                || target.activityInfo.applicationInfo == null
                || (target.activityInfo.applicationInfo.flags & (ApplicationInfo.FLAG_SYSTEM | ApplicationInfo.FLAG_UPDATED_SYSTEM_APP)) == 0) return null;
        return intent.setComponent(new ComponentName(target.activityInfo.packageName, target.activityInfo.name));
    }
    private void verifyFixture() {
        try {
            GraphicsDriverFixture.verify(activity.getPackageName(), debuggable(), new File(activity.getFilesDir(), "graphics-fixture").toPath(),
                    new GraphicsDriverPackage.MetadataReader() { public GraphicsDriverPackage.Metadata read(byte[] bytes) throws IOException {
                        try {
                            JSONObject row = new JSONObject(new String(bytes, StandardCharsets.UTF_8));
                            return new GraphicsDriverPackage.Metadata(integer(row, "schemaVersion"), string(row, "name"),
                                    string(row, "driverVersion"), integer(row, "minApi"), string(row, "libraryName"));
                        } catch (Exception invalid) { throw new IOException("Invalid graphics metadata"); }
                    } }, Build.VERSION.SDK_INT);
            result.setText("Synthetic package verified; custom activation unavailable.");
        } catch (IOException failure) { result.setText("Synthetic package rejected."); }
    }
    private static int integer(JSONObject row, String key) throws Exception {
        Object value = row.get(key); if (!(value instanceof Integer)) throw new IOException("Integer required"); return (Integer) value;
    }
    private static String string(JSONObject row, String key) throws Exception {
        Object value = row.get(key); if (!(value instanceof String)) throw new IOException("String required"); return (String) value;
    }
    private TextView text(LinearLayout layout, String value) { TextView view = new TextView(activity); view.setText(value); layout.addView(view); return view; }
    private Button button(LinearLayout layout, String label, final Runnable action) {
        Button view = new Button(activity); view.setText(label); layout.addView(view);
        view.setOnClickListener(new android.view.View.OnClickListener() { public void onClick(android.view.View ignored) { action.run(); } });
        return view;
    }
}
