package dev.ror2owner.graphics;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.UUID;

/** Authored, non-executable picker qualification only. Never selects or loads a driver. */
public final class GraphicsDriverFixture {
    private GraphicsDriverFixture() {}
    public static boolean allowed(String packageName, boolean debuggable) {
        return debuggable && "dev.ror2lab.installertest".equals(packageName);
    }
    public static byte[] library() {
        byte[] bytes = new byte[64];
        bytes[0] = 0x7f; bytes[1] = 'E'; bytes[2] = 'L'; bytes[3] = 'F';
        bytes[4] = 2; bytes[5] = 1; bytes[6] = 1; bytes[16] = 3; bytes[18] = (byte) 0xb7;
        return bytes;
    }
    public static void verify(String packageName, boolean debuggable, Path directory,
            GraphicsDriverPackage.MetadataReader reader, int api) throws IOException {
        GraphicsDriverPackage.require(allowed(packageName, debuggable), "Synthetic graphics fixture refused");
        GraphicsDriverPackage.require(!Files.isSymbolicLink(directory), "Synthetic graphics fixture refused");
        Path zip = directory.resolve("package.zip"), pin = directory.resolve("sha256");
        GraphicsDriverPackage.require(Files.isRegularFile(zip, LinkOption.NOFOLLOW_LINKS) && Files.size(zip) <= 4096
                && Files.isRegularFile(pin, LinkOption.NOFOLLOW_LINKS) && Files.size(pin) == 64, "Synthetic graphics fixture refused");
        byte[] bytes = Files.readAllBytes(zip);
        String expected = new String(Files.readAllBytes(pin), StandardCharsets.US_ASCII);
        StringBuilder actual = new StringBuilder();
        try {
            for (byte value : MessageDigest.getInstance("SHA-256").digest(bytes)) {
                actual.append(Character.forDigit((value >> 4) & 15, 16));
                actual.append(Character.forDigit(value & 15, 16));
            }
        } catch (NoSuchAlgorithmException impossible) { throw new IOException("SHA-256 unavailable", impossible); }
        GraphicsDriverPackage.require(expected.matches("[0-9a-f]{64}") && expected.equals(actual.toString()), "Synthetic graphics hash refused");
        Path stage = directory.resolve("verified-" + UUID.randomUUID());
        try {
            GraphicsDriverPackage.Verified verified = GraphicsDriverPackage.stage(new ByteArrayInputStream(bytes), stage, reader, null, api);
            GraphicsDriverPackage.require("Authored graphics fixture".equals(verified.metadata.name)
                    && "synthetic-only".equals(verified.metadata.version) && "libvulkan_fixture.so".equals(verified.metadata.library)
                    && Arrays.equals(library(), Files.readAllBytes(stage.resolve(verified.metadata.library))), "Non-synthetic graphics file refused");
            GraphicsDriverPackage.require(GraphicsDriverPackage.verify(verified), "Synthetic graphics verification refused");
        } finally {
            // Only this newly generated flat stage is ours, never caller inputs/captures.
            if (Files.isDirectory(stage, LinkOption.NOFOLLOW_LINKS)) {
                try (DirectoryStream<Path> files = Files.newDirectoryStream(stage)) {
                    for (Path file : files) Files.delete(file);
                }
                Files.delete(stage);
            }
        }
    }
}
