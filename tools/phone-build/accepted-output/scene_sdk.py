"""Read native default declarations from paired owner SDK ARM64 ELF inputs."""

from bisect import bisect_right
import mmap
import struct


def require(value, message):
    if not value:
        raise ValueError(message)


class Elf:
    """Symbols may have NOBITS text; instruction/literal reads use the code file."""

    def __init__(self, code, symbols):
        self.code, self.symbols, self.segments = code, {}, []
        for data in (code, symbols):
            require(len(data) >= 64 and data[:6] == b"\x7fELF\x02\x01", "SDK requires little-endian ELF64")
            require(self.unpack(data, "<H", 18)[0] == 183, "SDK ELF is not ARM64")
        offset = self.unpack(code, "<Q", 32)[0]
        size, count = self.unpack(code, "<HH", 54)
        require(size >= 56 and count < 4096, "invalid SDK ELF segment table")
        self.take(code, offset, size * count)
        for i in range(count):
            kind, flags, pos, address, _, length, memory, _ = self.unpack(code, "<IIQQQQQQ", offset + i * size)
            if kind == 1:
                self.take(code, pos, length)
                require(length <= memory, "SDK ELF segment exceeds memory extent")
                self.segments.append((address, length, pos))
        offset = self.unpack(symbols, "<Q", 40)[0]
        size, count = self.unpack(symbols, "<HH", 58)
        require(size >= 64 and 0 < count < 4096, "invalid SDK ELF symbol sections")
        self.take(symbols, offset, size * count)
        sections = [self.unpack(symbols, "<IIQQQQIIQQ", offset + i * size) for i in range(count)]
        for section in sections:
            if section[1] != 2:
                continue
            require(section[9] >= 24 and section[5] % section[9] == 0 and 0 < section[6] < count, "invalid SDK ELF symbol table")
            self.take(symbols, section[4], section[5])
            names = sections[section[6]]
            require(names[1] == 3, "SDK ELF symbol names are not strings")
            raw = self.take(symbols, names[4], names[5])
            for pos in range(section[4], section[4] + section[5], section[9]):
                name, info, _, index, value, length = self.unpack(symbols, "<IBBHQQ", pos)
                if info & 15 != 2 or not index:
                    continue
                require(name < len(raw), "SDK ELF symbol name escapes table")
                end = raw.find(b"\0", name)
                require(end >= name, "unterminated SDK ELF symbol")
                self.symbols.setdefault(raw[name:end].decode(), set()).add(value)
        self.symbol_addresses = sorted({address for values in self.symbols.values() for address in values})

    @staticmethod
    def take(data, offset, size):
        require(0 <= offset <= offset + size <= len(data), "SDK ELF extent escapes input")
        return data[offset : offset + size]

    @classmethod
    def unpack(cls, data, fmt, offset):
        return struct.unpack(fmt, cls.take(data, offset, struct.calcsize(fmt)))

    def symbol(self, name):
        values = self.symbols.get(name, set())
        require(len(values) == 1, "missing/ambiguous SDK ELF function")
        return next(iter(values))

    def at(self, address, size):
        for start, length, offset in self.segments:
            if start <= address <= address + size <= start + length:
                return self.take(self.code, offset + address - start, size)
        raise ValueError("SDK address has no file-backed code/literal bytes")


def builtin_tags(code, symbols, declarations):
    """Derive tag names and IDs from native registration calls, without execution."""
    with code.open("rb") as first, symbols.open("rb") as second:
        with mmap.mmap(first.fileno(), 0, access=mmap.ACCESS_READ) as executable, mmap.mmap(second.fileno(), 0, access=mmap.ACCESS_READ) as names:
            image = Elf(executable, names)
            register = image.symbol("_ZN10TagManager11RegisterTagEjRKN4core12basic_stringIcNS0_20StringStorageDefaultIcEEEE")
            assign = image.symbol("_ZN4core20StringStorageDefaultIcE6assignEPKcm")
            calls = declarations.calls(image, "_ZN10TagManager32RegisterDefaultTagsAndLayerMasksEv")
            assignments = [pc for pc, target in calls if target == assign]
            output = {}
            for pc, target in calls:
                if target != register:
                    continue
                index = bisect_right(assignments, pc) - 1
                require(index >= 0, "SDK tag has no source string declaration")
                before = assignments[index]
                text = declarations.cstring(image, declarations.argument(image, before, 1))
                require(len(text.encode()) == declarations.argument(image, before, 2), "SDK tag string extent differs")
                identity = declarations.argument(image, pc, 1)
                require(text not in output and identity not in output.values(), "duplicate SDK tag")
                output[text] = identity
            require(output and "Untagged" in output and "MainCamera" in output, "SDK built-in tag declarations absent")
            return output
