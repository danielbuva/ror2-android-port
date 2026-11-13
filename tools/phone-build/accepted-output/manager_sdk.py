"""Bounded metadata selection from the owner's pinned SDK; no native execution."""

from bisect import bisect_right
import mmap
import struct


def require(value, message):
    if not value:
        raise ValueError(message)


def bounds(image, name):
    start = image.symbol(name)
    index = bisect_right(image.symbol_addresses, start)
    require(index < len(image.symbol_addresses), "SDK function end absent")
    end = image.symbol_addresses[index]
    require(0 < end - start < 16384 and (end - start) % 4 == 0, "unbounded SDK manager declaration")
    return start, end


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def calls(image, name):
    start, end = bounds(image, name)
    return [
        (pc, pc + signed(word & 0x3FFFFFF, 26) * 4)
        for pc in range(start, end, 4)
        if (word := struct.unpack("<I", image.at(pc, 4))[0]) & 0xFC000000 == 0x94000000
    ]


def argument(image, before, register, depth=0):
    """Resolve one constant argument through at most 32 preceding instructions.

    An intervening call or unknown write refuses; runtime values are never guessed.
    Instruction fields follow the public ARM64 encoding, not captured SDK bytes.
    """
    require(depth < 12, "recursive SDK argument")
    for pc in range(before - 4, before - 132, -4):
        word = struct.unpack("<I", image.at(pc, 4))[0]
        dest, source = word & 31, (word >> 5) & 31
        require(word & 0xFC000000 != 0x94000000, "SDK argument crosses a call")
        if dest != register:
            continue
        if word & 0x9F000000 == 0x90000000:
            return (pc & ~4095) + signed(((word >> 5) & 0x7FFFF) * 4 + ((word >> 29) & 3), 21) * 4096
        if word & 0xFFC00000 == 0x91000000:
            return argument(image, pc, source, depth + 1) + ((word >> 10) & 4095)
        if word & 0x7F800000 == 0x52800000:
            return ((word >> 5) & 65535) << (((word >> 21) & 3) * 16)
        if word & 0x7FE0FFE0 == 0x2A0003E0:
            copied = (word >> 16) & 31
            return 0 if copied == 31 else argument(image, pc, copied, depth + 1)
        raise ValueError("unsupported constant SDK argument write")
    raise ValueError("SDK argument has no bounded definition")


def cstring(image, address):
    raw = image.at(address, 256)
    require(b"\0" in raw, "unterminated SDK resource declaration")
    value = raw.split(b"\0")[0].decode("utf-8")
    require(value and len(value) < 200 and all(32 <= ord(c) < 127 for c in value), "invalid SDK resource declaration")
    return value


def android_graphics(binary, registry_module):
    """Read resource registrations and the non-XR Android internal Shader cohort."""
    with binary.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        image = registry_module.MachO(data)
        target = image.symbol("__ZN22BuiltinResourceManager14RegisterShaderExPKcS1_b")
        registered = []
        for pc, called in calls(image, "__ZN22BuiltinResourceManager24InitializeExtraResourcesEv"):
            if called == target:
                registered.append(dict(id=argument(image, pc, 1), path=cstring(image, argument(image, pc, 2)), name=cstring(image, argument(image, pc, 3))))
        require(registered and len({row["id"] for row in registered}) == len(registered), "ambiguous SDK Shader registration")
        lookup = {row["path"]: row for row in registered}
        hidden = "__ZNK16GraphicsSettings24AddHiddenInternalShadersERNSt3__16vectorI4PPtrI6ShaderE13stl_allocatorIS4_L18MemLabelIdentifier58ELi16EEEE"
        start, _ = bounds(image, hidden)
        xr = image.symbol("__ZN15XREditorSupport33RequiresSinglePassInstanceSupportEv")
        gates = [pc for pc, called in calls(image, hidden) if called == xr]
        require(len(gates) == 1, "SDK XR Shader boundary differs")
        selected = []
        for pc in range(start, gates[0] - 4, 4):
            word, next_word = struct.unpack("<II", image.at(pc, 8))
            if word & 0x9F000000 != 0x90000000 or next_word & 0xFFC00000 != 0x91000000 or (next_word >> 5) & 31 != word & 31:
                continue
            try:
                literal = cstring(image, argument(image, pc + 8, next_word & 31))
            except (ValueError, UnicodeDecodeError):
                continue  # Native RTTI/allocator addresses are not string declarations.
            if literal in lookup:
                selected.append(lookup[literal])
        video = "__ZN20video_YUV420_convert12DecodeShader26GetShadersForBuildPlatformE19BuildTargetPlatformR13dynamic_arrayI4PPtrI6ShaderELm0EE"
        constructor = image.symbol("__ZN20video_YUV420_convert12DecodeShader13BuiltinShaderC2EPKc")
        video_names = [cstring(image, argument(image, pc, 1)) for pc, called in calls(image, video) if called == constructor]
        require(len(video_names) == 4, "SDK video build selectors differ")
        # Pinned SDK branches: common, non-WebGL, OSX and Android. This owner
        # selects Android without XR; all names and resource IDs stay SDK-owned.
        by_name = {row["name"]: row for row in registered}
        selected.extend(by_name[video_names[index]] for index in (0, 1, 3))
        sizes = {address for name, addresses in image.symbols.items() if "string_traits" in name for address in addresses}
        mix = calls(image, "__ZN20TextureMixerPlayable10InitializeEv")
        names = [cstring(image, argument(image, pc, 0)) for pc, called in mix if called in sizes]
        require(names and names[0] in by_name, "SDK compositor declaration absent")
        selected.append(by_name[names[0]])
        require(len({row["id"] for row in selected}) == len(selected), "duplicate SDK internal Shader")
        return dict(registered=registered, hidden=selected)
