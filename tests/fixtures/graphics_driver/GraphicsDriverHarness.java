package dev.ror2owner.graphics;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.HashSet;

public final class GraphicsDriverHarness {
    private static int checks, sequence;
    private static Path root;
    private static final GraphicsDriverPackage.MetadataReader META = bytes -> {
        check(new String(bytes, StandardCharsets.UTF_8).equals("authored metadata fixture"));
        return new GraphicsDriverPackage.Metadata(1, "Authored Turnip", "test", 28, "libvulkan_test.so");
    };
    private interface Action { void run() throws Exception; }
    private static void check(boolean value) { if (!value) throw new AssertionError("check " + checks); checks++; }
    private static void rejects(Action action) throws Exception {
        try { action.run(); } catch (IOException expected) { checks++; return; }
        throw new AssertionError("expected rejection at " + checks);
    }
    private static GraphicsDriverPackage.Verified stage(String name, GraphicsDriverPackage.TurnipRelease release) throws Exception {
        return GraphicsDriverPackage.stage(Files.newInputStream(root.resolve(name)), root.resolve("stage-" + sequence++), META, release, 30);
    }
    private static GraphicsDriverPackage.TurnipRelease release(String family, String hash, String source, String download) throws IOException {
        return new GraphicsDriverPackage.TurnipRelease(family, "authored-test", "Authored Turnip", "test", source, download, hash,
                "MIT", new HashSet<>(Arrays.asList(6, 7)));
    }
    private static GraphicsDriverPolicy.State freshProcess() throws IOException {
        return new GraphicsDriverPolicy.State(root.resolve("state"), new GraphicsDriverPolicy.ProcessState());
    }
    private static final String SOURCE = "https://github.com/example/turnip/releases/tag/test";
    private static final String DOWNLOAD = "https://github.com/example/turnip/releases/download/test/driver.zip";
    private static final GraphicsDriverPolicy.Device ADRENO = new GraphicsDriverPolicy.Device(0x5143, 7, 30, true);
    private static final class Provider implements GraphicsDriverPolicy.Provider {
        boolean available = true, valid = true, loaded = true;
        boolean loadThrows;
        int loads, fallbacks;
        final GraphicsDriverPolicy.State state;
        Provider(GraphicsDriverPolicy.State state) { this.state = state; }
        public boolean detect(GraphicsDriverPolicy.Device device) { return device.supportsAdreno(); }
        public boolean available() { return available; }
        public GraphicsDriverPackage.Verified install() throws IOException { throw new IOException("Explicit import required"); }
        public boolean verify(GraphicsDriverPackage.Verified driver) throws IOException { return valid && GraphicsDriverPackage.verify(driver); }
        public boolean load(GraphicsDriverPackage.Verified driver) throws IOException {
            check(new GraphicsDriverPolicy.State(root.resolve("state")).pending()); // durable BEFORE native call
            loads++;
            if (loadThrows) throw new IOException("authored private failure text");
            return loaded;
        }
        public void fallback() { fallbacks++; }
    }
    public static void main(String[] args) throws Exception {
        root = Paths.get(args[0]);
        String hash = new String(Files.readAllBytes(root.resolve("hash.txt")), StandardCharsets.US_ASCII).trim();
        GraphicsDriverPackage.TurnipRelease pinned = release("mesa-turnip", hash, SOURCE, DOWNLOAD);
        rejects(() -> release("qualcomm-proprietary", hash, SOURCE, DOWNLOAD));
        rejects(() -> release("mesa-turnip", "not-a-hash", SOURCE, DOWNLOAD));
        rejects(() -> release("mesa-turnip", hash, SOURCE, DOWNLOAD.replace("/test/", "/different/")));
        rejects(() -> release("mesa-turnip", hash, SOURCE, DOWNLOAD.replace("https:", "http:")));
        rejects(() -> release("mesa-turnip", hash, SOURCE, DOWNLOAD + "?token=example"));
        rejects(() -> release("mesa-turnip", hash, SOURCE, DOWNLOAD.replace("github.com", "example.com")));
        rejects(() -> new GraphicsDriverPackage.Metadata(2, "Turnip", "test", 28, "libtest.so"));
        rejects(() -> new GraphicsDriverPackage.Metadata(1, "Turnip\nInjected", "test", 28, "libtest.so"));
        rejects(() -> new GraphicsDriverPackage.Metadata(1, "Turnip", "test", 28, "../libtest.so"));
        GraphicsDriverPackage.Verified driver = stage("good.zip", pinned);
        check(driver.curated && driver.archiveSha256.equals(hash) && GraphicsDriverPackage.verify(driver));
        try (java.util.stream.Stream<Path> files = Files.list(driver.directory)) { check(files.count() == 3); }
        check(!Files.exists(driver.directory.resolve("extra.so")));
        GraphicsDriverPackage.Verified local = stage("good.zip", null);
        check(!local.curated && local.cacheKey().equals(driver.cacheKey()));
        check(!stage("other.zip", null).cacheKey().equals(driver.cacheKey()));
        for (String name : Arrays.asList("traversal.zip", "nested.zip", "missing-meta.zip", "large-meta.zip", "wrong-arch.zip", "duplicate.zip"))
            rejects(() -> stage(name, null));
        rejects(() -> stage("other.zip", pinned));
        rejects(() -> GraphicsDriverPackage.stage(Files.newInputStream(root.resolve("good.zip")), driver.directory, META, pinned, 30));
        rejects(() -> GraphicsDriverPackage.stage(Files.newInputStream(root.resolve("good.zip")), root.resolve("old-api"), META, null, 27));
        check(!Files.exists(root.resolve("escaped")));
        GraphicsDriverPolicy.State state = freshProcess();
        Provider provider = new Provider(state);
        check(GraphicsDriverPolicy.begin(state, ADRENO, null, null).outcome == GraphicsDriverPolicy.Outcome.SYSTEM);
        check(provider.loads == 0);
        state.select(driver);
        check(GraphicsDriverPolicy.begin(state, new GraphicsDriverPolicy.Device(0x13b5, 0, 30, true), provider, driver).outcome == GraphicsDriverPolicy.Outcome.SYSTEM);
        check(provider.loads == 0 && state.selected().equals("system"));
        state.select(driver);
        check(GraphicsDriverPolicy.begin(state, new GraphicsDriverPolicy.Device(0x5143, 8, 30, true), provider, driver).outcome == GraphicsDriverPolicy.Outcome.SYSTEM);
        check(provider.loads == 0);
        state.select(driver); provider.available = false;
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, driver).outcome == GraphicsDriverPolicy.Outcome.SYSTEM);
        check(provider.loads == 0); provider.available = true;
        state.select(driver); provider.valid = false;
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, driver).reason.equals("Graphics driver verification failed."));
        check(provider.loads == 0); provider.valid = true;
        state.select(driver);
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, driver).outcome == GraphicsDriverPolicy.Outcome.CUSTOM_PENDING_FIRST_FRAME);
        GraphicsDriverPolicy.State pendingState = state;
        rejects(() -> pendingState.select(driver));
        // Simulate a process crash before first frame. No retry or native load on next process.
        state = freshProcess();
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, driver).outcome == GraphicsDriverPolicy.Outcome.SYSTEM);
        check(provider.loads == 1 && state.selected().equals("system"));
        state.select(driver); provider.loaded = false;
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, driver).outcome == GraphicsDriverPolicy.Outcome.RESTART_WITH_SYSTEM);
        check(provider.fallbacks == 1 && !state.pending());
        state = freshProcess();
        state.select(driver); provider.loadThrows = true;
        GraphicsDriverPolicy.Launch failed = GraphicsDriverPolicy.begin(state, ADRENO, provider, driver);
        check(failed.outcome == GraphicsDriverPolicy.Outcome.RESTART_WITH_SYSTEM && !failed.reason.contains("private"));
        provider.loadThrows = false; provider.loaded = true;
        state = freshProcess();
        state = freshProcess();
        state.select(driver);
        GraphicsDriverPolicy.begin(state, ADRENO, provider, driver);
        check(GraphicsDriverPolicy.firstFrame(state, provider, driver, false, true).outcome == GraphicsDriverPolicy.Outcome.RESTART_WITH_SYSTEM);
        state = freshProcess();
        state.select(driver);
        GraphicsDriverPolicy.begin(state, ADRENO, provider, driver);
        check(GraphicsDriverPolicy.firstFrame(state, provider, driver, true, false).outcome == GraphicsDriverPolicy.Outcome.RESTART_WITH_SYSTEM);
        state = freshProcess();
        state.select(driver);
        GraphicsDriverPolicy.begin(state, ADRENO, provider, driver);
        check(GraphicsDriverPolicy.firstFrame(state, provider, driver, true, true).outcome == GraphicsDriverPolicy.Outcome.CUSTOM_READY);
        check(!state.pending() && new GraphicsDriverPolicy.State(root.resolve("state")).selected().equals(hash));
        state.resetToSystem(); check(state.selected().equals("system"));
        state = freshProcess();
        state.select(driver);
        Files.write(driver.directory.resolve(driver.metadata.library), "changed".getBytes(StandardCharsets.US_ASCII));
        int loads = provider.loads;
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, driver).outcome == GraphicsDriverPolicy.Outcome.SYSTEM);
        check(provider.loads == loads);
        // A repeated call in the same process must not authorize a system hot swap.
        state = freshProcess(); state.select(local);
        GraphicsDriverPolicy.begin(state, ADRENO, provider, local);
        loads = provider.loads;
        check(GraphicsDriverPolicy.begin(state, ADRENO, provider, local).outcome == GraphicsDriverPolicy.Outcome.RESTART_WITH_SYSTEM);
        check(provider.loads == loads);
        state.resetToSystem();
        check(GraphicsDriverPolicy.begin(state, ADRENO, null, null).outcome == GraphicsDriverPolicy.Outcome.RESTART_WITH_SYSTEM);
        Files.write(root.resolve("state/launch-state"), "corrupt".getBytes(StandardCharsets.US_ASCII));
        check(new GraphicsDriverPolicy.State(root.resolve("state")).selected().equals("system"));
        check(!new GraphicsDriverPolicy.Device(0x5143, 7, 27, true).supportsAdreno());
        check(!new GraphicsDriverPolicy.Device(0x5143, 7, 30, false).supportsAdreno());
        System.out.println("{\"success\":true,\"synthetic_only\":true,\"checks\":" + checks + "}");
    }
}
