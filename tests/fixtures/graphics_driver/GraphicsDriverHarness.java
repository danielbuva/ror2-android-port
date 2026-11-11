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
                "MIT", 28, new HashSet<>(Arrays.asList(6, 7)));
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
    private static void pickerContracts(GraphicsDriverPackage.Verified driver) throws Exception {
        GraphicsDriverPolicy.State state = freshProcess();
        GraphicsDriverProviders.resetToSystem(state);
        Provider provider = new Provider(state);
        check(GraphicsDriverProviders.curatedReleases().isEmpty());
        check(GraphicsDriverProviders.EMPTY_CATALOG.contains("license-notice"));
        check(GraphicsDriverProviders.ADRENOTOOLS_LICENSE.equals("BSD-2-Clause"));
        check(GraphicsDriverProviders.ADRENOTOOLS_SOURCE.endsWith("8fae8ce254dfc1344527e05301e43f37dea2df80"));
        java.util.List<GraphicsDriverProviders.Choice> choices = GraphicsDriverProviders.choices(ADRENO, null);
        check(choices.size() == 3);
        check(choices.get(0).available && choices.get(0).id.equals("system"));
        check(!choices.get(1).available && choices.get(1).explanation.contains("not connected to Unity"));
        check(!choices.get(2).available && choices.get(2).id.equals("mesa-panvk"));
        try { choices.clear(); throw new AssertionError("mutable choices"); }
        catch (UnsupportedOperationException expected) { checks++; }
        check(!GraphicsDriverProviders.choices(null, provider).get(1).available);
        GraphicsDriverPolicy.Device mali = new GraphicsDriverPolicy.Device(0x13b5, 0, 30, true);
        check(!GraphicsDriverProviders.choices(mali, provider).get(1).available);
        check(!GraphicsDriverProviders.choices(mali, provider).get(2).available);
        check(!GraphicsDriverProviders.choices(new GraphicsDriverPolicy.Device(0x5143, 7, 27, true), provider).get(1).available);
        check(!GraphicsDriverProviders.choices(new GraphicsDriverPolicy.Device(0x5143, 7, 30, false), provider).get(1).available);
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, null, provider, driver));
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, mali, provider, driver));
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, ADRENO, null, driver));
        provider.available = false;
        check(!GraphicsDriverProviders.choices(ADRENO, provider).get(1).available);
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, ADRENO, provider, driver));
        provider.available = true;
        provider.valid = false;
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, ADRENO, provider, driver));
        provider.valid = true;
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, ADRENO, provider, null));
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, new GraphicsDriverPolicy.Device(0x5143, 8, 30, true), provider, driver));
        check(state.selected().equals("system") && provider.loads == 0 && provider.fallbacks == 0);
        GraphicsDriverProviders.ActiveDriver active = GraphicsDriverProviders.ActiveDriver.unavailable();
        check(!active.observed && active.summary().contains("unavailable"));
        check(GraphicsDriverProviders.choices(ADRENO, provider).get(1).available);
        GraphicsDriverProviders.selectTurnip(state, ADRENO, provider, driver);
        check(state.selected().equals(driver.archiveSha256) && freshProcess().selected().equals(driver.archiveSha256));
        check(!active.observed && provider.loads == 0); // Selection is neither load nor active-driver evidence.
        GraphicsDriverProviders.resetToSystem(state);
        check(freshProcess().selected().equals("system") && provider.loads == 0);
        active = GraphicsDriverProviders.ActiveDriver.fromActivePhysicalDevice("Observed GPU", 0x5143, -1, null, null);
        check(active.observed && active.driverVersionRaw.equals("4294967295") && active.vendorId.equals("20803"));
        check(active.driverName.isEmpty() && active.driverInfo.isEmpty());
        active = GraphicsDriverProviders.ActiveDriver.fromActivePhysicalDevice("Observed GPU", 0x13b5, 42, "Observed driver", "Observed info");
        check(active.summary().contains("Observed driver") && active.summary().contains("Observed info"));
        rejects(() -> GraphicsDriverProviders.ActiveDriver.fromActivePhysicalDevice("", 0, 0, null, null));
        rejects(() -> GraphicsDriverProviders.ActiveDriver.fromActivePhysicalDevice("GPU\ninjected", 0, 0, null, null));
        rejects(() -> GraphicsDriverProviders.ActiveDriver.fromActivePhysicalDevice("GPU", 0, 0, null, "info\u0000"));
        check(GraphicsDriverProviders.SETTINGS_EXPLANATION.contains("does not change"));
        GraphicsDriverPackage.Verified changed = stage("good.zip", release("mesa-turnip", driver.archiveSha256, SOURCE, DOWNLOAD));
        Files.write(changed.directory.resolve(changed.metadata.library), new byte[] {0});
        rejects(() -> GraphicsDriverProviders.selectTurnip(state, ADRENO, provider, changed));
        check(state.selected().equals("system") && provider.loads == 0);
    }
    private static void syntheticPickerContracts() throws Exception {
        String owned = "dev.ror2lab.installertest";
        check(GraphicsDriverFixture.allowed(owned, true));
        check(!GraphicsDriverFixture.allowed(owned, false));
        check(!GraphicsDriverFixture.allowed("dev.ror2lab.alpha", true));
        check(!GraphicsDriverFixture.allowed("dev.ror2lab.phonebuildhostfixture", true));
        Path directory = Files.createDirectory(root.resolve("graphics-fixture"));
        Path zip = directory.resolve("package.zip"), pin = directory.resolve("sha256");
        Files.copy(root.resolve("synthetic.zip"), zip);
        GraphicsDriverPackage.MetadataReader reader = bytes -> new GraphicsDriverPackage.Metadata(
                1, "Authored graphics fixture", "synthetic-only", 28, "libvulkan_fixture.so");
        Files.write(pin, hash(zip).getBytes(StandardCharsets.US_ASCII));
        rejects(() -> GraphicsDriverFixture.verify(owned, false, directory, reader, 30));
        rejects(() -> GraphicsDriverFixture.verify("dev.ror2lab.alpha", true, directory, reader, 30));
        GraphicsDriverFixture.verify(owned, true, directory, reader, 30);
        try (java.util.stream.Stream<Path> files = Files.list(directory)) { check(files.count() == 2); }
        check(freshProcess().selected().equals("system"));
        Files.write(pin, new String(new char[64]).replace('\0', '0').getBytes(StandardCharsets.US_ASCII));
        rejects(() -> GraphicsDriverFixture.verify(owned, true, directory, reader, 30));
        Files.copy(root.resolve("non-synthetic.zip"), zip, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        Files.write(pin, hash(zip).getBytes(StandardCharsets.US_ASCII));
        rejects(() -> GraphicsDriverFixture.verify(owned, true, directory, reader, 30));
        try (java.util.stream.Stream<Path> files = Files.list(directory)) { check(files.count() == 2); }
        Files.write(zip, new byte[4097]);
        rejects(() -> GraphicsDriverFixture.verify(owned, true, directory, reader, 30));
        Files.delete(zip); Files.createSymbolicLink(zip, root.resolve("synthetic.zip"));
        rejects(() -> GraphicsDriverFixture.verify(owned, true, directory, reader, 30));
        check(freshProcess().selected().equals("system"));
    }
    private static String hash(Path path) throws Exception {
        StringBuilder text = new StringBuilder();
        for (byte value : java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)))
            text.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        return text.toString();
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
        pickerContracts(driver);
        syntheticPickerContracts();
        try (java.util.stream.Stream<Path> files = Files.list(driver.directory)) { check(files.count() == 3); }
        check(!Files.exists(driver.directory.resolve("extra.so")));
        // Real AdrenoTools recipes can use a non-lib-prefixed name and minApi 27.
        GraphicsDriverPackage.MetadataReader adrenoMetadata = bytes -> new GraphicsDriverPackage.Metadata(
                1, "Authored Turnip", "test", 27, "vulkan.ad07XX.so");
        GraphicsDriverPackage.Verified adreno = GraphicsDriverPackage.stage(Files.newInputStream(root.resolve("adrenotools.zip")),
                root.resolve("adrenotools"), adrenoMetadata, null, 28);
        check(adreno.minApi == 28 && GraphicsDriverPackage.verify(adreno));
        rejects(() -> GraphicsDriverPackage.stage(Files.newInputStream(root.resolve("adrenotools.zip")),
                root.resolve("adrenotools-old"), adrenoMetadata, null, 27));
        GraphicsDriverPackage.TurnipRelease newerApi = new GraphicsDriverPackage.TurnipRelease(
                "mesa-turnip", "reviewed-api", "Authored Turnip", "test", SOURCE, DOWNLOAD, hash, "MIT", 35,
                new HashSet<>(Arrays.asList(7)));
        rejects(() -> stage("good.zip", newerApi));
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
