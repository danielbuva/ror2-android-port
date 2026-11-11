"""Package Android x86_64 SDK runtime libraries into the target APK."""

from pathlib import Path
import shutil

SDK_ENTRIES = {
    "lib/x86_64/libmain.so",
    "lib/x86_64/libunity.so",
}


def copy_sdk_libraries(sdk: Path, output: Path):
    for library in ("libmain.so", "libunity.so"):
        path = output / "apk/lib/x86_64" / library
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sdk / "Variations/il2cpp/Development/Libs/x86_64" / library, path)
