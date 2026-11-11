package dev.ror2owner.graphics;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Android-independent verifier. Call only for an explicit user import/download. */
public final class GraphicsDriverPackage {
    public static final long MAX_ARCHIVE_BYTES = 64L * 1024 * 1024;
    public static final long MAX_EXPANDED_BYTES = 256L * 1024 * 1024;
    private static final int MAX_MEMBERS = 64;
    private static final int MAX_METADATA_BYTES = 64 * 1024;
    private GraphicsDriverPackage() {}

    /** The Android adapter parses bounded meta.json with org.json, without trusting its claims. */
    public interface MetadataReader { Metadata read(byte[] json) throws IOException; }

    public static final class Metadata {
        public final String name, version, library;
        public final int minApi;
        public Metadata(int schemaVersion, String name, String version, int minApi, String library) throws IOException {
            require(schemaVersion == 1, "Unsupported driver metadata version");
            this.name = label(name);
            this.version = label(version);
            require(minApi >= 28 && minApi <= 100, "Invalid driver Android requirement");
            require(library != null && library.matches("lib[A-Za-z0-9_.-]+\\.so"), "Invalid driver library name");
            this.minApi = minApi;
            this.library = library;
        }
    }

    /** A row from a manifest pinned in the APK, never from the downloaded ZIP. */
    public static final class TurnipRelease {
        public final String id, name, version, releaseUrl, downloadUrl, sha256, license;
        public final Set<Integer> generations;
        public TurnipRelease(String family, String id, String name, String version, String releaseUrl,
                String downloadUrl, String sha256, String license, Set<Integer> generations) throws IOException {
            require("mesa-turnip".equals(family), "Only Mesa Turnip releases are curated");
            require(id != null && id.matches("[a-z0-9][a-z0-9._-]{0,79}"), "Invalid curated driver identity");
            require(sha256 != null && sha256.matches("[0-9a-f]{64}"), "Curated driver requires SHA-256");
            this.name = label(name);
            this.version = label(version);
            this.license = label(license);
            require("MIT".equals(license), "Curated Mesa release license requires review");
            URI release = https(releaseUrl), download = https(downloadUrl);
            require("github.com".equals(release.getHost()) && "github.com".equals(download.getHost()), "Curated source must be a reviewed GitHub release");
            String[] releasePath = release.getPath().split("/"), downloadPath = download.getPath().split("/");
            require(releasePath.length == 6 && downloadPath.length == 7
                    && "releases".equals(releasePath[3]) && "tag".equals(releasePath[4])
                    && "releases".equals(downloadPath[3]) && "download".equals(downloadPath[4])
                    && releasePath[1].equals(downloadPath[1]) && releasePath[2].equals(downloadPath[2])
                    && releasePath[5].equals(downloadPath[5]) && downloadPath[6].endsWith(".zip"),
                    "Curated download must match its source release");
            require(generations != null && !generations.isEmpty(), "Supported Adreno generations required");
            for (Integer generation : generations)
                require(generation != null && generation >= 6 && generation <= 8, "Unsupported Adreno generation");
            this.generations = Collections.unmodifiableSet(new HashSet<>(generations));
            this.id = id; this.sha256 = sha256; this.releaseUrl = releaseUrl; this.downloadUrl = downloadUrl;
        }
    }

    /** Hash identity is content-derived even for user files; metadata is never a trust root. */
    public static final class Verified {
        public final Metadata metadata;
        public final String archiveSha256, librarySha256;
        public final Path directory;
        public final boolean curated;
        public final Set<Integer> generations;
        private Verified(Metadata metadata, String archiveSha256, String librarySha256, Path directory, TurnipRelease release) {
            this.metadata = metadata; this.archiveSha256 = archiveSha256; this.librarySha256 = librarySha256;
            this.directory = directory; this.curated = release != null;
            this.generations = release == null ? Collections.emptySet() : release.generations;
        }
        public String cacheKey() { return "adreno-turnip-" + archiveSha256; }
    }

    /**
     * The caller supplies a NEW child of Context.getFilesDir(), not shared/SAF storage.
     * The input is closed. Failure retains only caller-owned staging for caller cleanup.
     * The caller publishes this directory/selection only after this method succeeds.
     */
    public static Verified stage(InputStream source, Path newPrivateDirectory, MetadataReader reader,
            TurnipRelease release, int api) throws IOException {
        Path directory = newPrivateDirectory.toAbsolutePath();
        try (InputStream owned = source) {
            Files.createDirectory(directory);
            Path archive = directory.resolve("package.zip");
            String archiveHash;
            try (OutputStream output = Files.newOutputStream(archive, StandardOpenOption.CREATE_NEW)) {
                archiveHash = copy(owned, output, MAX_ARCHIVE_BYTES, null);
            }
            require(release == null || release.sha256.equals(archiveHash), "Driver download hash differs from pinned manifest");
            try (ZipFile zip = new ZipFile(archive.toFile())) {
                Set<String> names = new HashSet<>();
                long total = 0;
                Enumeration<? extends ZipEntry> entries = zip.entries();
                while (entries.hasMoreElements()) {
                    ZipEntry entry = entries.nextElement();
                    require(!entry.isDirectory() && entry.getName().matches("[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}"), "Driver ZIP must contain flat file names");
                    require(names.add(entry.getName()) && names.size() <= MAX_MEMBERS, "Duplicate or excessive driver ZIP members");
                    require(entry.getSize() >= 0 && entry.getSize() <= MAX_EXPANDED_BYTES - total, "Driver ZIP exceeds expansion limit");
                    total += entry.getSize();
                }
                ZipEntry meta = zip.getEntry("meta.json");
                require(meta != null && meta.getSize() <= MAX_METADATA_BYTES, "Driver metadata missing or too large");
                ByteArrayOutputStream json = new ByteArrayOutputStream();
                try (InputStream input = zip.getInputStream(meta)) { copy(input, json, MAX_METADATA_BYTES, null); }
                Metadata metadata = reader.read(json.toByteArray());
                require(metadata != null && metadata.minApi <= api, "Driver requires a newer Android version");
                ZipEntry library = zip.getEntry(metadata.library);
                require(library != null && library.getSize() >= 64, "Driver library missing or truncated");
                byte[] header = new byte[64];
                String libraryHash;
                // Only the declared library is executable content. Archive extras are not extracted.
                try (InputStream input = zip.getInputStream(library);
                        OutputStream output = Files.newOutputStream(directory.resolve(metadata.library), StandardOpenOption.CREATE_NEW)) {
                    libraryHash = copy(input, output, MAX_EXPANDED_BYTES, header);
                }
                require(header[0] == 0x7f && header[1] == 'E' && header[2] == 'L' && header[3] == 'F'
                        && header[4] == 2 && header[5] == 1 && header[6] == 1
                        && header[16] == 3 && header[17] == 0 && (header[18] & 255) == 183 && header[19] == 0,
                        "Driver must be a little-endian ARM64 ELF shared library");
                Files.write(directory.resolve("meta.json"), json.toByteArray(), StandardOpenOption.CREATE_NEW);
                return new Verified(metadata, archiveHash, libraryHash, directory, release);
            }
        }
    }

    /** Recheck the selected bytes immediately before giving the path to the native loader. */
    public static boolean verify(Verified installed) throws IOException {
        Path library = installed.directory.resolve(installed.metadata.library);
        if (Files.isSymbolicLink(library) || !Files.isRegularFile(library)) return false;
        try (InputStream input = Files.newInputStream(library)) {
            return installed.librarySha256.equals(copy(input, null, MAX_EXPANDED_BYTES, null));
        }
    }

    private static String copy(InputStream input, OutputStream output, long limit, byte[] header) throws IOException {
        MessageDigest digest;
        try { digest = MessageDigest.getInstance("SHA-256"); }
        catch (java.security.NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
        byte[] buffer = new byte[65536];
        long total = 0;
        for (int count; (count = input.read(buffer)) != -1;) {
            require(count <= limit - total, "Driver input exceeds size limit");
            if (header != null && total < header.length)
                System.arraycopy(buffer, 0, header, (int) total, Math.min(count, header.length - (int) total));
            if (output != null) output.write(buffer, 0, count);
            digest.update(buffer, 0, count); total += count;
        }
        StringBuilder text = new StringBuilder();
        for (byte value : digest.digest()) text.append(String.format(Locale.ROOT, "%02x", value & 255));
        return text.toString();
    }

    private static URI https(String value) throws IOException {
        try {
            URI uri = new URI(value);
            require("https".equals(uri.getScheme()) && uri.getHost() != null && uri.getUserInfo() == null
                    && uri.getPort() == -1 && uri.getQuery() == null && uri.getFragment() == null
                    && !uri.getRawPath().contains("%") && !uri.getPath().contains(".."), "Invalid release URL");
            return uri;
        } catch (java.net.URISyntaxException | NullPointerException error) { throw new IOException("Invalid release URL"); }
    }
    private static String label(String value) throws IOException {
        require(value != null && !value.trim().isEmpty() && value.length() <= 200, "Invalid driver label");
        for (int i = 0; i < value.length(); i++) require(!Character.isISOControl(value.charAt(i)), "Invalid driver label");
        return value;
    }
    static void require(boolean condition, String message) throws IOException { if (!condition) throw new IOException(message); }
}
