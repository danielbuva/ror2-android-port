import com.android.build.gradle.internal.generators.BuildConfigData;
import com.android.build.gradle.internal.generators.BuildConfigGenerator;
import com.android.builder.symbols.BytecodeRClassWriterKt;
import com.android.ide.common.symbols.Symbol;
import com.android.ide.common.symbols.SymbolIo;
import com.android.ide.common.symbols.SymbolTable;
import com.android.ide.common.xml.XmlFormatPreferences;
import com.android.ide.common.xml.XmlFormatStyle;
import com.android.ide.common.xml.XmlPrettyPrinter;
import com.android.resources.ResourceType;
import com.android.tools.r8.CompilationMode;
import com.android.tools.r8.D8;
import com.android.tools.r8.D8Command;
import com.android.tools.r8.OutputMode;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;

/** Calls separately supplied AGP 7.4.2 and D8 4.0.52; contains no SDK implementation. */
public final class SdkAndroidCode {
    private static final String APPLICATION = "dev.ror2lab.arm64";
    private static final String LIBRARY = "com.unity3d.player";

    private static Path config(Path sourceRoot, String namespace, boolean application)
            throws Exception {
        BuildConfigData.Builder data = new BuildConfigData.Builder()
                .setOutputPath(sourceRoot)
                .setNamespace(namespace)
                .addBooleanField("DEBUG", true)
                .addStringField(application ? "APPLICATION_ID" : "LIBRARY_PACKAGE_NAME", namespace)
                .addStringField("BUILD_TYPE", "debug");
        if (application) {
            data.addIntField("VERSION_CODE", 1).addStringField("VERSION_NAME", "1.0");
        }
        BuildConfigGenerator generator = new BuildConfigGenerator(data.build());
        generator.generate();
        return generator.getGeneratedFilePath().toPath();
    }

    private static Path compile(Path directory, Path androidJar, Path playerJar, Path... sources)
            throws Exception {
        Path classes = Files.createDirectories(directory.resolve("classes"));
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            throw new IllegalStateException("A Java 11 JDK compiler is required");
        }
        List<String> arguments = new ArrayList<>(Arrays.asList(
                "-g", "-source", "11", "-target", "11", "-encoding", "UTF-8",
                "-classpath", androidJar + File.pathSeparator + playerJar,
                "-d", classes.toString()));
        for (Path source : sources) {
            arguments.add(source.toString());
        }
        if (compiler.run(null, System.out, System.err, arguments.toArray(new String[0])) != 0) {
            throw new IllegalStateException("SDK Java compilation failed");
        }
        Path jar = directory.resolve("classes.jar");
        List<Path> files;
        try (Stream<Path> paths = Files.walk(classes)) {
            files = paths.filter(Files::isRegularFile).sorted().collect(Collectors.toList());
        }
        try (JarOutputStream archive = new JarOutputStream(Files.newOutputStream(jar))) {
            for (Path file : files) {
                JarEntry entry = new JarEntry(classes.relativize(file).toString().replace('\\', '/'));
                entry.setTime(0);
                archive.putNextEntry(entry);
                Files.copy(file, archive);
                archive.closeEntry();
            }
        }
        return jar;
    }

    private static void dex(Path program, Path androidJar, boolean disableDesugaring,
            boolean perClass, Path output) throws Exception {
        Path directory = Files.createDirectory(output.resolveSibling(output.getFileName() + "-d8"));
        D8Command.Builder command = D8Command.builder()
                .addProgramFiles(program)
                .addLibraryFiles(androidJar)
                .setMinApiLevel(23)
                .setMode(CompilationMode.DEBUG)
                .setIncludeClassesChecksum(true)
                .setDisableDesugaring(disableDesugaring)
                .setIntermediate(perClass)
                .setOutput(directory, perClass ? OutputMode.DexFilePerClassFile : OutputMode.DexIndexed);
        D8.run(command.build());
        List<Path> dexFiles;
        try (Stream<Path> files = Files.walk(directory)) {
            dexFiles = files.filter(Files::isRegularFile).collect(Collectors.toList());
        }
        if (dexFiles.size() != 1 || !dexFiles.get(0).toString().endsWith(".dex")) {
            throw new IllegalStateException("Expected one DEX output");
        }
        Files.move(dexFiles.get(0), output);
    }

    private static Path resources(Path symbols, Path directory) throws Exception {
        SymbolTable application = SymbolIo.readFromAapt(symbols.toFile(), APPLICATION);
        SymbolTable.Builder library = SymbolTable.builder().tablePackage(LIBRARY);
        for (ResourceType type : Arrays.asList(ResourceType.ID, ResourceType.STRING, ResourceType.STYLE)) {
            for (Symbol symbol : application.getSymbolByResourceType(type)) {
                // Unity exports these two strings to the launcher rather than unityLibrary.
                if (type != ResourceType.STRING || (!symbol.getName().equals("app_name")
                        && !symbol.getName().equals("game_view_content_description"))) {
                    library.add(symbol);
                }
            }
        }
        Path jar = directory.resolve("resources.jar");
        BytecodeRClassWriterKt.exportToCompiledJava(
                Arrays.asList(application, library.build()), jar, true);
        return jar;
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length == 3 && arguments[0].equals("manifest")) {
            String xml = Files.readString(Paths.get(arguments[1]));
            String formatted = XmlPrettyPrinter.prettyPrint(
                    xml, XmlFormatPreferences.defaults(), XmlFormatStyle.MANIFEST, "\n");
            if (!formatted.startsWith("<?xml")) {
                formatted = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + formatted;
            }
            Files.writeString(Paths.get(arguments[2]), formatted, StandardOpenOption.CREATE_NEW);
            return;
        }
        if (arguments.length != 4) {
            throw new IllegalArgumentException(
                    "Usage: SdkAndroidCode SDK_ROOT ANDROID_JAR AAPT_R_TXT NEW_OUTPUT");
        }
        Path sdk = Paths.get(arguments[0]);
        Path androidJar = Paths.get(arguments[1]);
        Path symbols = Paths.get(arguments[2]);
        Path output = Paths.get(arguments[3]);
        Path playerJar = sdk.resolve("Variations/il2cpp/Development/Classes/classes.jar");
        Path activity = sdk.resolve("Source/com/unity3d/player/UnityPlayerActivity.java");
        for (Path input : Arrays.asList(androidJar, symbols, playerJar, activity)) {
            if (!Files.isRegularFile(input)) {
                throw new IllegalArgumentException("Required SDK input is not a regular file");
            }
        }
        Files.createDirectory(output);
        dex(playerJar, androidJar, false, false, output.resolve("classes.dex"));
        Path libraryConfig = config(output.resolve("library-source"), LIBRARY, false);
        Path libraryJar = compile(output.resolve("library"), androidJar, playerJar, libraryConfig, activity);
        dex(libraryJar, androidJar, true, false, output.resolve("classes2.dex"));
        dex(resources(symbols, output), androidJar, false, false, output.resolve("classes3.dex"));
        Path applicationConfig = config(output.resolve("application-source"), APPLICATION, true);
        Path applicationJar = compile(
                output.resolve("application"), androidJar, playerJar, applicationConfig);
        // AGP's application class-directory path uses per-class intermediate DEX output.
        dex(applicationJar, androidJar, true, true, output.resolve("classes4.dex"));
    }
}
