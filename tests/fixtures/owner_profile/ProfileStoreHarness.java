package dev.ror2owner.bootstrap;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** All bytes are authored nonsense/JSON, not game or personal data. */
public final class ProfileStoreHarness {
    static final int SCHEMA = 7;
    static final String PROFILE = "android-profile-v1/profile.json";
    static final String SETTINGS = "offline-settings-v1/preferences.json";
    static final String LEDGER = "offline-run-results-v1/profile.json";
    static final String RUN = "offline-run-results-v1/run-0123456789abcdef0123456789abcdef.xml";
    static int checks;
    interface Action { void run() throws Exception; }
    static void check(boolean condition, String message) { checks++; if (!condition) throw new AssertionError(message); }
    static void denied(Action action, String message) throws Exception { boolean failed = false; try { action.run(); } catch (IOException expected) { failed = true; } check(failed, message); }
    static final class Env implements ProfileStore.Environment {
        long available = Long.MAX_VALUE; String fault; Runnable hook;
        public long availableBytes(File dir) { return available; }
        public void syncDirectory(File dir) throws IOException {
            // Real directory fsync on the host; Android's provider uses Os.fsync.
            try (java.nio.channels.FileChannel channel = java.nio.channels.FileChannel.open(dir.toPath(), StandardOpenOption.READ)) { channel.force(true); }
        }
        public void checkpoint(String stage) throws IOException {
            if (hook != null) { Runnable once = hook; hook = null; once.run(); }
            if (stage.equals(fault)) { fault = null; throw new IOException("synthetic interruption"); }
        }
    }
    static final class Fixture {
        final File live, vault; final Env env = new Env(); ProfileStore store;
        Fixture(File base, String name) throws IOException {
            File root = new File(base, name); live = new File(root, "live"); vault = new File(root, "private");
            live.mkdirs(); vault.mkdirs(); store = new ProfileStore(live, vault, env);
        }
        void seed() throws IOException {
            put(live, PROFILE, "synthetic-profile-primary"); put(live, PROFILE + ".backup", "synthetic-profile-backup");
            put(live, PROFILE + ".pending", "synthetic-profile-pending"); put(live, PROFILE + ".backup.pending", "synthetic-profile-migration-pending");
            put(live, SETTINGS, "synthetic-preferences-primary"); put(live, SETTINGS + ".backup", "synthetic-preferences-backup");
            put(live, LEDGER, "synthetic-result-ledger"); put(live, RUN, "synthetic-run-report-not-resumable");
            put(live, RUN.replace(".xml", ".debug.json"), "synthetic-assistance-evidence");
            put(live, "payload/not-a-profile", "payload-untouched"); put(live, "cloud/not-a-profile", "cloud-untouched");
            put(live, PROFILE + ".rejected-authored", "excluded-diagnostic");
        }
        File archive(String token, String path) { return new File(vault, "snapshot-" + token + "/" + path); }
        void reopen() throws IOException { store = new ProfileStore(live, vault, env); }
    }
    static void put(File root, String path, String text) throws IOException {
        File file = new File(root, path); file.getParentFile().mkdirs(); Files.write(file.toPath(), text.getBytes(StandardCharsets.UTF_8));
    }
    static String get(File root, String path) throws IOException { return new String(Files.readAllBytes(new File(root, path).toPath()), StandardCharsets.UTF_8); }
    public static void main(String[] args) throws Exception {
        File base = new File(args[0]).getCanonicalFile();
        Fixture basic = new Fixture(base, "basic"); basic.seed();
        ProfileStore.Snapshot saved = basic.store.snapshot(SCHEMA);
        check(saved.files == 9 && saved.bytes > 0 && saved.schema == SCHEMA, "bounded exact whitelist");
        check(basic.store.frozen(), "snapshot freezes launch");
        check(!basic.archive(saved.token, "payload").exists() && !basic.archive(saved.token, "cloud").exists(), "no payload/cloud copied");
        check(saved.token.equals(basic.store.snapshot(SCHEMA).token), "duplicate snapshot is idempotent");
        basic.reopen(); basic.store.verify(saved.token, SCHEMA, new int[] {SCHEMA});
        put(basic.live, PROFILE, "synthetic-update-damage"); put(basic.live, SETTINGS, "synthetic-rollback-damage");
        denied(() -> basic.store.verify(saved.token, SCHEMA, new int[] {SCHEMA}), "changed live bytes refused");
        denied(() -> basic.store.release(saved.token, SCHEMA, new int[] {SCHEMA}), "cannot unfreeze damaged files");
        denied(() -> basic.store.restore(saved.token, SCHEMA, new int[] {SCHEMA + 1}), "incompatible schema refused");
        check(get(basic.live, PROFILE).equals("synthetic-update-damage"), "incompatible restore nonmutating");
        basic.store.restore(saved.token, SCHEMA, new int[] {SCHEMA, SCHEMA + 1});
        check(get(basic.live, PROFILE).equals("synthetic-profile-primary"), "profile restored exactly");
        check(get(basic.live, SETTINGS).equals("synthetic-preferences-primary"), "settings restored exactly");
        check(get(basic.live, RUN).equals("synthetic-run-report-not-resumable"), "baseline-dependent history restored");
        check(get(basic.live, "payload/not-a-profile").equals("payload-untouched") && get(basic.live, "cloud/not-a-profile").equals("cloud-untouched"), "unrelated roots unchanged");
        basic.store.release(saved.token, SCHEMA, new int[] {SCHEMA}); basic.store.release(saved.token, SCHEMA, new int[] {SCHEMA});
        check(!basic.store.frozen(), "duplicate release recovers interruption");
        denied(() -> basic.store.restore(saved.token, SCHEMA, new int[] {SCHEMA}), "no restore without active lease");

        for (String stage : new String[] {"restore-journal", "restore-file", "restore-remove", "restore-verified"}) {
            Fixture f = new Fixture(base, stage); f.seed(); ProfileStore.Snapshot snapshot = f.store.snapshot(SCHEMA);
            put(f.live, PROFILE, "synthetic-corrupt"); put(f.live, SETTINGS + ".pending", "synthetic-new-extra");
            f.env.fault = stage;
            denied(() -> f.store.restore(snapshot.token, SCHEMA, new int[] {SCHEMA}), "injected interruption " + stage);
            f.reopen(); check(f.store.frozen(), "interrupted restore remains frozen");
            f.store.restore(snapshot.token, SCHEMA, new int[] {SCHEMA});
            f.store.verify(snapshot.token, SCHEMA, new int[] {SCHEMA});
            check(get(f.live, PROFILE).equals("synthetic-profile-primary") && !new File(f.live, SETTINGS + ".pending").exists(), "restore replays exact original set");
            f.store.release(snapshot.token, SCHEMA, new int[] {SCHEMA});
        }
        for (String stage : new String[] {"snapshot-file", "snapshot-published", "snapshot-frozen"}) {
            Fixture f = new Fixture(base, stage); f.seed(); f.env.fault = stage;
            denied(() -> f.store.snapshot(SCHEMA), "injected snapshot interruption " + stage);
            f.reopen(); ProfileStore.Snapshot snapshot = f.store.snapshot(SCHEMA);
            check(f.store.frozen() && snapshot.files == 9, "snapshot retry reconciles publication/lease");
        }
        for (String stage : new String[] {"release-verified", "release-recorded"}) {
            Fixture f = new Fixture(base, stage); f.seed(); ProfileStore.Snapshot snapshot = f.store.snapshot(SCHEMA);
            check(f.store.status(snapshot.token, SCHEMA, new int[] {SCHEMA}).state.equals("active"), "active status before release");
            f.env.fault = stage;
            denied(() -> f.store.release(snapshot.token, SCHEMA, new int[] {SCHEMA}), "injected release interruption " + stage);
            f.reopen();
            if (stage.equals("release-verified")) {
                check(f.store.frozen() && f.store.status(snapshot.token, SCHEMA, new int[] {SCHEMA}).state.equals("active"), "unpublished release remains frozen");
                f.store.release(snapshot.token, SCHEMA, new int[] {SCHEMA});
            }
            check(!f.store.frozen(), "durable released receipt unfreezes launch");
            put(f.live, PROFILE, "synthetic-new-gameplay-progress");
            f.reopen();
            check(f.store.status(snapshot.token, SCHEMA, new int[] {SCHEMA}).state.equals("released"), "historical release proof ignores new gameplay");
            denied(() -> f.store.verify(snapshot.token, SCHEMA, new int[] {SCHEMA}), "historical release is not current byte proof");
            denied(() -> f.store.restore(snapshot.token, SCHEMA, new int[] {SCHEMA}), "stale restore after release refused");
            f.store.release(snapshot.token, SCHEMA, new int[] {SCHEMA});
            check(get(f.live, PROFILE).equals("synthetic-new-gameplay-progress"), "retry release never overwrites later progress");
            denied(() -> f.store.status(snapshot.token, SCHEMA + 1, new int[] {SCHEMA + 1}), "release proof bound to schema");
            ProfileStore.Snapshot next = f.store.snapshot(SCHEMA);
            check(!next.token.equals(snapshot.token) && f.store.frozen(), "next update can capture new progress");
            denied(() -> f.store.status(snapshot.token, SCHEMA, new int[] {SCHEMA}), "old token proof superseded without history growth");
            f.store.release(next.token, SCHEMA, new int[] {SCHEMA});
            check(!f.store.frozen() && f.store.status(next.token, SCHEMA, new int[] {SCHEMA}).state.equals("released"), "next update releases normally");
        }
        Fixture changed = new Fixture(base, "changed"); changed.seed();
        changed.env.hook = () -> { try { put(changed.live, PROFILE, "concurrent-synthetic-change"); } catch (IOException error) { throw new RuntimeException(error); } };
        denied(() -> changed.store.snapshot(SCHEMA), "concurrent writer refused"); check(!changed.store.frozen(), "failed snapshot no lease");
        Fixture empty = new Fixture(base, "empty"); ProfileStore.Snapshot absent = empty.store.snapshot(SCHEMA);
        check(absent.files == 0, "first install empty snapshot"); put(empty.live, PROFILE, "unexpected-created-profile");
        empty.store.restore(absent.token, SCHEMA, new int[] {SCHEMA}); check(!new File(empty.live, PROFILE).exists(), "absence restored exactly");
        Fixture low = new Fixture(base, "low"); low.seed(); low.env.available = 0;
        denied(() -> low.store.snapshot(SCHEMA), "storage refusal"); check(!low.store.frozen(), "low-space no accepted snapshot");
        Fixture large = new Fixture(base, "large");
        File tooLarge = new File(large.live, PROFILE); tooLarge.getParentFile().mkdirs();
        try (RandomAccessFile file = new RandomAccessFile(tooLarge, "rw")) { file.setLength(ProfileStore.MAX_FILE_BYTES + 1); }
        denied(() -> large.store.snapshot(SCHEMA), "oversize refusal");
        Fixture corrupt = new Fixture(base, "corrupt"); corrupt.seed(); ProfileStore.Snapshot broken = corrupt.store.snapshot(SCHEMA);
        put(corrupt.vault, "snapshot-" + broken.token + "/" + PROFILE, "corrupt-archive"); put(corrupt.live, PROFILE, "keep-on-refusal");
        denied(() -> corrupt.store.restore(broken.token, SCHEMA, new int[] {SCHEMA}), "archive hash corruption refused");
        check(get(corrupt.live, PROFILE).equals("keep-on-refusal") && !new File(corrupt.vault, "restoring").exists(), "all archive bytes checked before restore");
        Fixture manifest = new Fixture(base, "manifest"); manifest.seed(); ProfileStore.Snapshot m = manifest.store.snapshot(SCHEMA);
        Files.write(manifest.archive(m.token, "manifest").toPath(), new byte[] {1, 2, 3});
        denied(() -> manifest.store.verify(m.token, SCHEMA, new int[] {SCHEMA}), "manifest hash corruption refused");
        Fixture linked = new Fixture(base, "linked"); File outside = new File(base, "outside"); outside.mkdirs(); put(outside, "owned", "outside-unchanged");
        new File(linked.live, "android-profile-v1").mkdirs(); Files.createSymbolicLink(new File(linked.live, PROFILE).toPath(), new File(outside, "owned").toPath());
        denied(() -> linked.store.snapshot(SCHEMA), "profile symlink refused"); check(get(outside, "owned").equals("outside-unchanged"), "external target unchanged");
        Fixture linkRoot = new Fixture(base, "root-link"); File alias = new File(base, "alias"); Files.createSymbolicLink(alias.toPath(), linkRoot.live.toPath());
        denied(() -> new ProfileStore(alias, linkRoot.vault, linkRoot.env), "root symlink refused");
        denied(() -> new ProfileStore(linkRoot.live, new File(linkRoot.live, "nested"), linkRoot.env), "overlapping roots refused");
        for (String path : new String[] {"../escape", "/absolute", "android-profile-v1/../../escape", "android-profile-v1/not-profile", "offline-run-results-v1/run-abc.xml", "cloud/profile.json", "offline-settings-v1/preferences.json/key"}) check(!ProfileStore.allowed(path), "path whitelist " + path);
        Fixture retained = new Fixture(base, "retained"); retained.seed();
        String current = null;
        for (int i = 0; i < 4; i++) {
            put(retained.live, PROFILE, "synthetic-generation-" + i);
            current = retained.store.snapshot(SCHEMA).token;
            retained.store.release(current, SCHEMA, new int[] {SCHEMA});
            check(retained.archive(current, "manifest").isFile(), "release retains verified backup");
        }
        int archives = 0; for (String name : retained.vault.list()) if (name.startsWith("snapshot-")) archives++;
        check(archives == 2, "retained archives bounded to current plus one previous");
        byte[] cert = "synthetic-public-certificate-bytes-not-a-key".getBytes(StandardCharsets.UTF_8); String pin = ProfileStore.digest(cert);
        check(ProfileStore.authorized("dev.authored.installer", pin, new String[] {"dev.authored.installer"}, new byte[][] {cert}), "pinned installer admitted");
        check(!ProfileStore.authorized("dev.authored.installer", pin, new String[] {"dev.impostor"}, new byte[][] {cert}), "wrong package rejected");
        check(!ProfileStore.authorized("dev.authored.installer", pin, new String[] {"dev.authored.installer", "dev.shared"}, new byte[][] {cert}), "shared UID rejected");
        check(!ProfileStore.authorized("dev.authored.installer", pin, new String[] {"dev.authored.installer"}, new byte[][] {new byte[] {0}}), "wrong signer rejected");
        check(!ProfileStore.authorized("dev.authored.installer", pin, new String[] {"dev.authored.installer"}, new byte[][] {cert, cert}), "multiple signers rejected");
        check(!ProfileStore.authorized("dev.authored.installer", pin, null, null), "unknown UID rejected");
        System.out.println("{\"success\":true,\"checks\":" + checks + ",\"synthetic_only\":true}");
    }
}
