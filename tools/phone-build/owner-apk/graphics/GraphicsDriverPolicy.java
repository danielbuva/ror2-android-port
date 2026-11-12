package dev.ror2owner.graphics;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;

/** Pre-Unity driver admission and process-restart fallback; no Android/global setting writes. */
public final class GraphicsDriverPolicy {
    public static final String SYSTEM = "system";
    private GraphicsDriverPolicy() {}
    static final class ProcessState { boolean nativeAttempted; }
    private static final ProcessState PROCESS = new ProcessState();

    public static final class Device {
        public final int vendorId, adrenoGeneration, api;
        public final boolean arm64;
        public Device(int vendorId, int adrenoGeneration, int api, boolean arm64) {
            this.vendorId = vendorId; this.adrenoGeneration = adrenoGeneration; this.api = api; this.arm64 = arm64;
        }
        // Vulkan vendor ID, not a marketing/device-name substring.
        public boolean supportsAdreno() { return vendorId == 0x5143 && arm64 && api >= 28; }
    }

    /** Native binding must be available before offering import/select in the UI. */
    public interface Provider {
        boolean detect(Device device);
        boolean available();
        GraphicsDriverPackage.Verified install() throws IOException;
        boolean verify(GraphicsDriverPackage.Verified driver) throws IOException;
        /** True means the intended loader is wired into Unity, NOT just dlopen succeeded. */
        boolean load(GraphicsDriverPackage.Verified driver) throws IOException;
        /** Invoked after first-frame failure, never to hot-swap a live Vulkan instance. */
        void fallback();
    }

    public enum Outcome { SYSTEM, CUSTOM_PENDING_FIRST_FRAME, CUSTOM_READY, RESTART_WITH_SYSTEM }
    public static final class Launch {
        public final Outcome outcome;
        public final String reason, cacheKey;
        private Launch(Outcome outcome, String reason, String cacheKey) {
            this.outcome = outcome; this.reason = reason; this.cacheKey = cacheKey;
        }
    }

    /** Durable marker is written BEFORE native code can crash. All calls must be serialized. */
    public static final class State {
        private final Path directory, receipt;
        private final ProcessState process;
        private String phase = SYSTEM, identity = SYSTEM;
        public State(Path privateDirectory) throws IOException { this(privateDirectory, PROCESS); }
        // Package-private process injection exists only for authored crash-recovery tests.
        State(Path privateDirectory, ProcessState process) throws IOException {
            this.process = process;
            directory = privateDirectory; receipt = directory.resolve("launch-state");
            Files.createDirectories(directory);
            if (Files.exists(receipt)) {
                GraphicsDriverPackage.require(!Files.isSymbolicLink(receipt) && Files.size(receipt) <= 256, "Invalid driver launch state");
                String[] values = new String(Files.readAllBytes(receipt), StandardCharsets.US_ASCII).split("\n", -1);
                if (values.length == 3 && (values[0].equals("selected") || values[0].equals("pending"))
                        && values[1].matches("[0-9a-f]{64}") && values[2].isEmpty()) {
                    phase = values[0]; identity = values[1];
                } else if (!new String(Files.readAllBytes(receipt), StandardCharsets.US_ASCII).equals("system\nsystem\n")) {
                    // Corruption cannot opt the next launch into custom native code.
                    save(SYSTEM, SYSTEM);
                }
            }
        }
        public boolean pending() { return phase.equals("pending"); }
        public String selected() { return identity; }
        public void select(GraphicsDriverPackage.Verified driver) throws IOException {
            GraphicsDriverPackage.require(!pending(), "A graphics driver launch is still pending");
            save("selected", driver.archiveSha256);
        }
        public void resetToSystem() throws IOException { save(SYSTEM, SYSTEM); }
        private void save(String nextPhase, String nextIdentity) throws IOException {
            Path temporary = directory.resolve("launch-state.new");
            byte[] bytes = (nextPhase + "\n" + nextIdentity + "\n").getBytes(StandardCharsets.US_ASCII);
            // A stale incomplete write is ours; never follow a symlink through it.
            Files.deleteIfExists(temporary);
            try (FileChannel channel = FileChannel.open(temporary, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                ByteBuffer buffer = ByteBuffer.wrap(bytes);
                while (buffer.hasRemaining()) channel.write(buffer);
                channel.force(true);
            }
            Files.move(temporary, receipt, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            try (FileChannel channel = FileChannel.open(directory, StandardOpenOption.READ)) { channel.force(true); }
            phase = nextPhase; identity = nextIdentity;
        }
    }

    public static Launch begin(State state, Device device, Provider provider, GraphicsDriverPackage.Verified driver) throws IOException {
        if (state.process.nativeAttempted)
            return restart(state, provider, "A custom graphics driver was already attempted in this process. Restart with the system driver.");
        if (state.pending()) return system(state, "The previous custom-driver launch did not complete. Using the system driver.");
        if (state.selected().equals(SYSTEM)) return new Launch(Outcome.SYSTEM, "", SYSTEM);
        if (provider == null || driver == null || !provider.detect(device) || !provider.available())
            return system(state, "Custom graphics drivers are unavailable on this device or build.");
        if (device.api < driver.minApi || (driver.curated && !driver.generations.contains(device.adrenoGeneration)))
            return system(state, "Graphics driver does not support this Android version or Adreno generation.");
        if (!state.selected().equals(driver.archiveSha256)) return system(state, "Selected graphics driver is missing or changed.");
        try {
            if (!provider.verify(driver)) return system(state, "Graphics driver verification failed.");
        } catch (IOException failure) { return system(state, "Graphics driver verification failed."); }
        state.save("pending", driver.archiveSha256);
        state.process.nativeAttempted = true;
        try {
            if (provider.load(driver)) return new Launch(Outcome.CUSTOM_PENDING_FIRST_FRAME, "", driver.cacheKey());
        } catch (IOException failure) { /* The process may already contain part of the custom loader. */ }
        return restart(state, provider, "Custom graphics driver loading failed. Restart with the system driver.");
    }

    /** The native first-frame hook must attest the intended driver and a completed Vulkan frame. */
    public static Launch firstFrame(State state, Provider provider, GraphicsDriverPackage.Verified driver,
            boolean intendedDriver, boolean frameComplete) throws IOException {
        GraphicsDriverPackage.require(state.process.nativeAttempted && state.pending() && driver != null && state.selected().equals(driver.archiveSha256), "No matching custom launch is pending");
        if (!intendedDriver || !frameComplete)
            return restart(state, provider, "Custom graphics driver self-check failed. Restart with the system driver.");
        state.save("selected", driver.archiveSha256);
        return new Launch(Outcome.CUSTOM_READY, "", driver.cacheKey());
    }

    private static Launch system(State state, String reason) throws IOException {
        state.resetToSystem(); return new Launch(Outcome.SYSTEM, reason, SYSTEM);
    }
    private static Launch restart(State state, Provider provider, String reason) throws IOException {
        // Never issue a system load in a process that may retain custom driver objects.
        state.resetToSystem();
        if (provider != null) provider.fallback();
        return new Launch(Outcome.RESTART_WITH_SYSTEM, reason, SYSTEM);
    }
}
