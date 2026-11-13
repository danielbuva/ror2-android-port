package dev.ror2owner.graphics;

import java.io.IOException;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Picker model only. Selection never loads native code or changes Android settings. */
public final class GraphicsDriverProviders {
    public static final String TURNIP = "mesa-turnip", PANVK = "mesa-panvk";
    public static final String ADRENOTOOLS_SOURCE =
            "https://github.com/bylaws/libadrenotools/tree/8fae8ce254dfc1344527e05301e43f37dea2df80";
    public static final String ADRENOTOOLS_LICENSE = "BSD-2-Clause";
    public static final String EMPTY_CATALOG = "No curated Turnip drivers are available in this build. "
            + "No package has completed source, license-notice, and compatibility review. The system Vulkan driver remains available.";
    public static final String SETTINGS_EXPLANATION = "Android Graphics Driver Preferences may be in Developer options. "
            + "Availability varies by Android build. This app does not change that setting or enable Developer options.";
    private GraphicsDriverProviders() {}

    // Adding a row requires a reviewed Mesa source/build pin, archive SHA-256,
    // bundled component notices and API/device constraints. A release URL alone is not approval.
    public static List<GraphicsDriverPackage.TurnipRelease> curatedReleases() {
        return Collections.emptyList();
    }

    public static final class Choice {
        public final String id, title, explanation;
        public final boolean available;
        private Choice(String id, String title, boolean available, String explanation) {
            this.id = id; this.title = title; this.available = available; this.explanation = explanation;
        }
    }

    public static List<Choice> choices(GraphicsDriverPolicy.Device device, GraphicsDriverPolicy.Provider provider) {
        String reason = turnipUnavailable(device, provider);
        return Collections.unmodifiableList(Arrays.asList(
                new Choice(GraphicsDriverPolicy.SYSTEM, "System (default)", true,
                        "Use Android's selected Vulkan driver. Reset applies on the next game launch, not to live Vulkan objects."),
                new Choice(TURNIP, "Adreno / Mesa Turnip", reason.isEmpty(), reason.isEmpty()
                        ? "Optional Mesa Turnip through libadrenotools. Explicit selection and a verified package are required." : reason),
                new Choice(PANVK, "Mali / Mesa PanVK", false,
                        "Unavailable: no Android PanVK provider is implemented. Use System.")));
    }

    private static String turnipUnavailable(GraphicsDriverPolicy.Device device, GraphicsDriverPolicy.Provider provider) {
        if (device == null) return "Unavailable: no verified GPU capability information. Use System.";
        if (!device.supportsAdreno()) return "Unavailable: requires an Adreno GPU, ARM64 and Android API 28 or newer. Use System.";
        if (provider == null || !provider.detect(device) || !provider.available())
            return "Unavailable: the libadrenotools loader is not connected to Unity in this build. Use System.";
        return "";
    }

    /** Explicit picker action; launch admission and crash recovery remain owned by Policy. */
    public static void selectTurnip(GraphicsDriverPolicy.State state, GraphicsDriverPolicy.Device device,
            GraphicsDriverPolicy.Provider provider, GraphicsDriverPackage.Verified driver) throws IOException {
        String reason = turnipUnavailable(device, provider);
        GraphicsDriverPackage.require(reason.isEmpty(), reason);
        GraphicsDriverPackage.require(driver != null, "Select a verified driver package first");
        GraphicsDriverPackage.require(device.api >= driver.minApi
                && (!driver.curated || driver.generations.contains(device.adrenoGeneration)),
                "Driver does not support this Android version or Adreno generation");
        GraphicsDriverPackage.require(GraphicsDriverPackage.verify(driver) && provider.verify(driver), "Driver verification failed");
        state.select(driver);
    }

    /** Does not reset the process-wide native-attempt latch or claim a live System driver. */
    public static void resetToSystem(GraphicsDriverPolicy.State state) throws IOException {
        state.resetToSystem();
    }

    /** Runtime evidence is independent of the saved preference, ZIP labels and provider availability. */
    public static final class ActiveDriver {
        public final boolean observed;
        public final String deviceName, vendorId, driverVersionRaw, driverName, driverInfo;
        private ActiveDriver(boolean observed, String deviceName, String vendorId, String version,
                String driverName, String driverInfo) {
            this.observed = observed; this.deviceName = deviceName; this.vendorId = vendorId;
            this.driverVersionRaw = version; this.driverName = driverName; this.driverInfo = driverInfo;
        }
        public static ActiveDriver unavailable() { return new ActiveDriver(false, "", "", "", "", ""); }

        /** Caller must query Unity's ACTUAL active VkPhysicalDevice, never a second instance.
         * Rich properties must be absent unless the existing instance/API/extension contract allows them.
         * driverVersion is vendor-specific, so display its unsigned raw value, not VK_VERSION decoding.
         */
        public static ActiveDriver fromActivePhysicalDevice(String deviceName, int vendorId, int driverVersion,
                String driverName, String driverInfo) throws IOException {
            return new ActiveDriver(true, displayText(deviceName, false),
                    Long.toString(vendorId & 0xffffffffL), Long.toString(driverVersion & 0xffffffffL),
                    displayText(driverName, true), displayText(driverInfo, true));
        }
        public String summary() {
            if (!observed) return "Active driver details unavailable: the running game's Vulkan device has not been observed.";
            String text = "GPU: " + deviceName + "; vendor ID: " + vendorId + "; driver version (raw): " + driverVersionRaw;
            if (!driverName.isEmpty()) text += "; driver: " + driverName;
            if (!driverInfo.isEmpty()) text += "; info: " + driverInfo;
            return text;
        }
    }

    private static String displayText(String value, boolean optional) throws IOException {
        if (optional && value == null) return "";
        GraphicsDriverPackage.require(value != null && value.length() <= 256 && (optional || !value.trim().isEmpty()),
                "Invalid active driver detail");
        for (int i = 0; i < value.length(); i++)
            GraphicsDriverPackage.require(!Character.isISOControl(value.charAt(i)), "Invalid active driver detail");
        return value;
    }
}
