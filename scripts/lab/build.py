from pathlib import Path
from common import ROOT, WORK, read, toolchain


def build_backend_name(api="vulkan"):
    tc = toolchain()
    arch = tc.get("architecture", "x86_64").upper()
    return f"IL2CPP-{arch}-{api}"
