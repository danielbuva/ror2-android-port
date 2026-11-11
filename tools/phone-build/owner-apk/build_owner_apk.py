"""Build a private owner x64 (x86_64) APK with an authored pre-Unity payload bootstrap."""

from pathlib import Path

CODE_ENTRIES = {
    "lib/x86_64/libil2cpp.so",
    "lib/x86_64/lib_burst_generated.so",
    "assets/bin/Data/Managed/Metadata/global-metadata.dat",
}
