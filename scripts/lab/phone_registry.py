"""Static owner-SDK metadata reading; never executes the SDK or generates roots yet."""

from bisect import bisect_right
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


PROFILE = "unity-2021.3.45f2-macos-arm64"
BINARY_SHA256 = "906123118e45d56c6bcf20f3776ed2373417553042500714023daeb9e53058e8"


class MachO:
    """Bounded thin little-endian ARM64 Mach-O reader, using no native libraries."""

    def __init__(self, data):
        self.data = data
        if len(data) < 32:
            raise ValueError("Truncated Mach-O header")
        magic, cpu, subtype, kind, commands, size, flags, reserved = struct.unpack_from("<IiiIIIII", data)
        if magic != 0xFEEDFACF or cpu != 0x100000C or kind != 2 or commands > 4096:
            raise ValueError("Expected a thin ARM64 little-endian SDK executable")
        self.segments, self.symbols, self.sections = [], {}, []
        self.take(32, size)
        position, symtab = 32, None
        for _ in range(commands):
            self.take(position, 8)
            command, length = struct.unpack_from("<II", data, position)
            if length < 8 or length % 8 or position + length > 32 + size:
                raise ValueError("Invalid Mach-O load command")
            if command == 0x19:
                if length < 72:
                    raise ValueError("Truncated 64-bit segment")
                vm, virtual_size, offset, file_size = struct.unpack_from("<QQQQ", data, position + 24)
                if file_size > virtual_size:
                    raise ValueError("Segment file bytes exceed virtual size")
                self.take(offset, file_size)
                if file_size and any(vm < old_vm + old_size and old_vm < vm + file_size for old_vm, old_size, old_offset in self.segments):
                    raise ValueError("Overlapping file-backed virtual segments")
                if file_size:
                    self.segments.append((vm, file_size, offset))
                section_count = struct.unpack_from("<I", data, position + 64)[0]
                if length != 72 + section_count * 80:
                    raise ValueError("Malformed SDK segment section table")
                for index in range(section_count):
                    item = position + 72 + index * 80
                    name, segment, address, section_size, file_offset = struct.unpack_from("<16s16sQQI", data, item)
                    if name.rstrip(b"\0") == b"__text" and segment.rstrip(b"\0") == b"__TEXT":
                        if not (vm <= address and address + section_size <= vm + file_size) or file_offset != offset + address - vm or section_size % 4:
                            raise ValueError("SDK instruction section escapes its segment")
                        self.take(file_offset, section_size)
                        self.sections.append((address, section_size, file_offset))
            elif command == 2:
                if length != 24 or symtab is not None:
                    raise ValueError("Malformed or duplicate symbol table")
                symtab = struct.unpack_from("<IIII", data, position + 8)
            position += length
        if position != 32 + size or symtab is None or not self.segments:
            raise ValueError("Incomplete SDK load-command/symbol contract")
        offset, count, strings_offset, strings_size = symtab
        self.take(offset, count * 16)
        strings = self.take(strings_offset, strings_size)
        for index in range(count):
            name_offset, kind, section, description, value = struct.unpack_from("<IBBHQ", data, offset + index * 16)
            if kind & 0xE0 or kind & 0x0E != 0x0E:
                continue
            if name_offset >= len(strings):
                raise ValueError("Symbol string offset escapes its table")
            end = strings.find(b"\0", name_offset)
            if end < 0:
                raise ValueError("Unterminated symbol name")
            name = strings[name_offset:end].decode("utf-8")
            self.symbols.setdefault(name, set()).add(value)
        self.symbol_addresses = sorted({value for values in self.symbols.values() for value in values})

    def take(self, offset, size):
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise ValueError("Mach-O range escapes input bytes")
        return self.data[offset : offset + size]

    def symbol(self, name):
        values = self.symbols.get(name, set())
        if len(values) != 1:
            raise ValueError("Missing or ambiguous required SDK symbol")
        return next(iter(values))

    def at(self, address, size):
        for vm, length, offset in self.segments:
            if vm <= address and address + size <= vm + length:
                return self.take(offset + address - vm, size)
        raise ValueError("SDK virtual address is not file backed")

    def string(self, address):
        for vm, length, offset in self.segments:
            if vm <= address < vm + length:
                raw = self.at(address, min(1024, vm + length - address))
                end = raw.find(b"\0")
                if end < 0:
                    raise ValueError("Unterminated SDK metadata string")
                result = raw[:end].decode("utf-8")
                if result and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:<> ,.*]*", result):
                    raise ValueError("Unexpected SDK metadata string")
                return result
        raise ValueError("SDK string address is not file backed")


def static_records(image):
    records, pointers = [], {}
    for symbol in sorted(image.symbols):
        if not re.fullmatch(r"__ZL\d+[A-Za-z0-9_]+_TypeRegistrationDesc", symbol):
            continue
        address = image.symbol(symbol)
        words = struct.unpack("<14Q", image.at(address, 112))
        name, namespace, module = (image.string(words[index]) for index in (2, 3, 4))
        if not name or module != "undefined" or words[10] in pointers:
            raise ValueError("SDK registration-record layout differs")
        row = {
            "symbol": symbol,
            "self": words[10],
            "parent": words[0],
            "name": name,
            "nativeNamespace": namespace,
            "qualifiedName": (namespace + "::" if namespace else "") + name,
            "module": None,
        }
        pointers[words[10]] = row
        records.append(row)
    if not records or len({row["qualifiedName"] for row in records}) != len(records):
        raise ValueError("Missing or duplicate SDK registration names")
    for row in records:
        parent = pointers.get(row["parent"])
        row["baseName"] = parent["name"] if parent else None
        row["base_resolved"] = row["parent"] == 0 or parent is not None
    return records


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def constant_calls(image, name):
    """Bounded static constant propagation, not SDK execution or CPU emulation.

    Only straight-line address/argument materialization is accepted. Unknown
    instructions/branches refuse; calls discard caller-saved values.
    """
    start = image.symbol(name)
    following = [value for values in image.symbols.values() for value in values if value > start]
    if not following:
        raise ValueError("Missing bounded SDK function end")
    end = min(following)
    if end - start > 65536 or (end - start) % 4:
        raise ValueError("Unqualified SDK function extent")
    registers, calls = [None] * 32, []
    for pc in range(start, end, 4):
        word = struct.unpack("<I", image.at(pc, 4))[0]
        rd, rn = word & 31, (word >> 5) & 31
        if word & 0x9F000000 in (0x10000000, 0x90000000):
            immediate = signed(((word >> 5) & 0x7FFFF) << 2 | ((word >> 29) & 3), 21)
            registers[rd] = (pc & ~4095) + immediate * 4096 if word & 0x80000000 else pc + immediate
        elif word & 0x7F000000 in (0x11000000, 0x51000000):
            immediate = ((word >> 10) & 4095) << (12 if word & 0x400000 else 0)
            value = registers[rn]
            registers[rd] = None if value is None else value + (-immediate if word & 0x40000000 else immediate)
            if registers[rd] is not None and not word & 0x80000000:
                registers[rd] &= 0xFFFFFFFF
        elif word & 0x7FE0FFE0 == 0x2A0003E0:
            rm = (word >> 16) & 31
            registers[rd] = 0 if rm == 31 else registers[rm]
            if registers[rd] is not None and not word & 0x80000000:
                registers[rd] &= 0xFFFFFFFF
        elif word & 0x7F800000 in (0x12800000, 0x52800000, 0x72800000):
            shift = ((word >> 21) & 3) * 16
            immediate = ((word >> 5) & 65535) << shift
            kind = word & 0x7F800000
            if kind == 0x52800000:
                registers[rd] = immediate
            elif kind == 0x12800000:
                registers[rd] = ~immediate
            else:
                registers[rd] = None if registers[rd] is None else (registers[rd] & ~(65535 << shift)) | immediate
            if registers[rd] is not None:
                registers[rd] &= 0xFFFFFFFFFFFFFFFF if word & 0x80000000 else 0xFFFFFFFF
        elif word & 0x7E000000 == 0x28000000:
            if word & 0x800000:  # Pre/post-index writeback changes the base.
                registers[rn] = None
            if word & 0x400000:  # LDP values come from runtime stack state.
                registers[rd] = registers[(word >> 10) & 31] = None
        elif word & 0xFFC00000 == 0xF9000000:
            pass  # STR does not establish a new argument register value.
        elif word & 0xFC000000 in (0x94000000, 0x14000000):
            target = pc + signed(word & 0x3FFFFFF, 26) * 4
            calls.append({"pc": pc, "target": target, "arguments": registers[:8]})
            if word & 0xFC000000 == 0x14000000:
                return calls
            registers[:19] = [None] * 19
            registers[30] = None
        elif word & 0xFFFFFC1F == 0xD65F0000:
            return calls
        elif word == 0xD503201F:
            pass
        else:
            raise ValueError(f"Unqualified SDK registration instruction at {pc:x}: {word:08x}")
        registers[31] = None
    raise ValueError("SDK registration function has no qualified terminal branch")


def module_assignments(image):
    reverse = {}
    for symbol, values in image.symbols.items():
        if re.fullmatch(r"__Z\d+RegisterUnityClassI.+EvPKc", symbol):
            reverse.setdefault(image.symbol(symbol), []).append(symbol)
    assignments, functions = {}, []
    for symbol in sorted(image.symbols):
        match = re.fullmatch(r"__Z\d+RegisterModuleClassesGenerated_([A-Za-z0-9_]+)v", symbol)
        if not match:
            continue
        calls = constant_calls(image, symbol)
        functions.append(symbol)
        for call in calls:
            targets = reverse.get(call["target"], [])
            if len(targets) != 1 or call["arguments"][0] is None:
                raise ValueError("Unknown SDK module-registration call/argument")
            module = image.string(call["arguments"][0])
            if module != match[1]:
                raise ValueError("SDK module literal and registration identity differ")
            encoded = re.fullmatch(r"__Z\d+RegisterUnityClassI(.+)EvPKc", targets[0]).group(1)
            pointer = image.symbol("__ZN13TypeContainerI" + encoded + "E4rttiE")
            if pointer in assignments and assignments[pointer] != module:
                raise ValueError("Conflicting SDK native module assignments")
            assignments[pointer] = module
    if not functions:
        raise ValueError("No SDK module-registration functions")
    return assignments, functions


def direct_calls(image, targets):
    """Index direct branches in the declared code section, never raw data bytes."""
    if len(image.sections) != 1:
        raise ValueError("Expected one bounded SDK instruction section")
    address, size, offset = image.sections[0]
    found = []
    for index in range(0, size, 4):
        word = struct.unpack_from("<I", image.data, offset + index)[0]
        if word & 0x7C000000 != 0x14000000:
            continue
        pc = address + index
        target = pc + signed(word & 0x3FFFFFF, 26) * 4
        if target in targets:
            found.append((pc, target))
    return found


def argument_block_start(image, pc):
    addresses = getattr(image, "symbol_addresses", None)
    if addresses is None:
        addresses = sorted({value for values in image.symbols.values() for value in values})
    index = bisect_right(addresses, pc)
    if index == 0 or index == len(addresses):
        return None
    start, end = addresses[index - 1 : index + 1]
    if end - start > 65536 or (end - start) % 4:
        return None
    block = start
    for position in range(start, end, 4):
        word = struct.unpack("<I", image.at(position, 4))[0]
        target = None
        if word & 0xFC000000 == 0x14000000:
            target = position + signed(word & 0x3FFFFFF, 26) * 4
        elif word & 0xFF000010 == 0x54000000 or word & 0x7E000000 == 0x34000000:
            target = position + signed((word >> 5) & 0x7FFFF, 19) * 4
        elif word & 0x7E000000 == 0x36000000:
            target = position + signed((word >> 5) & 0x3FFF, 14) * 4
        if target is not None:
            if position < pc:
                block = max(block, position + 4)
            if start <= target <= pc:
                block = max(block, target)
    return block


def call_argument(image, pc, register, start=None, budget=128):
    """Conservative backwards constant slicing within one straight-line block.

    A branch, unknown definition/instruction, runtime load or exhausted bound
    yields unknown. Callee-saved constants may cross calls under AAPCS64.
    No control-flow path is selected and no SDK function is executed.
    """
    if register == 31:
        return None
    if start is None:
        start = argument_block_start(image, pc)
    if start is None or pc < start or pc - start > 65536 or budget <= 0:
        return None
    for position in range(pc - 4, start - 1, -4):
        budget -= 1
        if budget <= 0:
            return None
        word = struct.unpack("<I", image.at(position, 4))[0]
        rd, rn = word & 31, (word >> 5) & 31
        if word & 0x9F000000 in (0x10000000, 0x90000000):
            if rd == register:
                immediate = signed(((word >> 5) & 0x7FFFF) << 2 | ((word >> 29) & 3), 21)
                return (position & ~4095) + immediate * 4096 if word & 0x80000000 else position + immediate
        elif word & 0x7F000000 in (0x11000000, 0x51000000):
            if rd == register:
                value = call_argument(image, position, rn, start, budget)
                if value is None:
                    return None
                immediate = ((word >> 10) & 4095) << (12 if word & 0x400000 else 0)
                value += -immediate if word & 0x40000000 else immediate
                return value & (0xFFFFFFFFFFFFFFFF if word & 0x80000000 else 0xFFFFFFFF)
        elif word & 0x7FE0FFE0 == 0x2A0003E0:
            if rd == register:
                rm = (word >> 16) & 31
                value = 0 if rm == 31 else call_argument(image, position, rm, start, budget)
                return value if value is None or word & 0x80000000 else value & 0xFFFFFFFF
        elif word & 0x7F800000 in (0x12800000, 0x52800000, 0x72800000):
            if rd == register:
                shift = ((word >> 21) & 3) * 16
                immediate, kind = ((word >> 5) & 65535) << shift, word & 0x7F800000
                if kind == 0x52800000:
                    value = immediate
                elif kind == 0x12800000:
                    value = ~immediate
                else:
                    value = call_argument(image, position, register, start, budget)
                    if value is None:
                        return None
                    value = (value & ~(65535 << shift)) | immediate
                return value & (0xFFFFFFFFFFFFFFFF if word & 0x80000000 else 0xFFFFFFFF)
        elif word & 0x7E000000 == 0x28000000:
            if word & 0x800000 and rn == register or word & 0x400000 and register in (rd, (word >> 10) & 31):
                return None
        elif word & 0xFFC00000 == 0xF9000000:
            pass
        elif word & 0xFC000000 == 0x94000000:
            if register < 19 or register == 30:
                return None
        elif word == 0xD503201F:
            pass
        else:
            return None
    return None


def direct_module_assignments(image):
    targets = {}
    for symbol in image.symbols:
        if re.fullmatch(r"__Z\d+RegisterUnityClassI.+EvPKc", symbol):
            address = image.symbol(symbol)
            if address in targets:
                raise ValueError("Ambiguous SDK typed registration callee")
            targets[address] = symbol
    assignments, unresolved = {}, []
    for pc, target in direct_calls(image, targets):
        value = call_argument(image, pc, 0)
        if value is None:
            unresolved.append(pc)
            continue
        module = image.string(value)
        encoded = re.fullmatch(r"__Z\d+RegisterUnityClassI(.+)EvPKc", targets[target]).group(1)
        pointer = image.symbol("__ZN13TypeContainerI" + encoded + "E4rttiE")
        if pointer in assignments and assignments[pointer] != module:
            raise ValueError("Conflicting direct SDK module assignments")
        assignments[pointer] = module
    return assignments, unresolved


def inspect(binary, output):
    binary, output = map(Path, (binary, output))
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary; inspect drift before selecting a profile")
    image = MachO(data)
    records = static_records(image)
    if len(records) != 305:
        raise ValueError("Pinned SDK static-record count differs")
    modules, functions = module_assignments(image)
    if len(functions) != 73 or len(modules) != 235:
        raise ValueError("Pinned SDK generated-module registration coverage differs")
    direct, unresolved = direct_module_assignments(image)
    if unresolved or set(direct) != {row["self"] for row in records} or any(direct.get(pointer) != module for pointer, module in modules.items()):
        raise ValueError("Pinned SDK direct/generated module registrations differ or remain unresolved")
    modules = direct
    for row in records:
        row["module"] = modules[row["self"]]
    helper = Path(__file__).with_name("phone_registry_literals.py")
    specification = importlib.util.spec_from_file_location("_phone_registry_literals", helper)
    literals = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(literals)  # Authored tool code; never SDK code.
    records += literals.extra_records(image, call_argument, direct_calls)
    parents = {row["self"]: row for row in records}
    if len(records) != 318 or len(parents) != 318 or len({row["qualifiedName"] for row in records}) != 318:
        raise ValueError("Pinned SDK native registration identity set differs")
    for row in records:
        parent = parents.get(row["parent"])
        row["base_resolved"] = row["parent"] == 0 or parent is not None
        row["baseName"] = parent["name"] if parent else "" if row["parent"] == 0 else None
        row["baseModule"] = parent["module"] if parent else "" if row["parent"] == 0 else None
        if not row["base_resolved"] or row["module"] is None:
            raise ValueError("Pinned SDK native hierarchy remains unresolved")
    if hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA256:
        raise ValueError("SDK binary changed during metadata inspection")
    result = {
        "profile": PROFILE,
        "binary_sha256": BINARY_SHA256,
        "reader_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "literal_reader_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        "executes_sdk": False,
        "root_generation_qualified": False,
        "module_registration_functions": functions,
        "counts": {
            "static_records": 305,
            "literal_records": 13,
            "native_records": len(records),
            "module_resolved": sum(row["module"] is not None for row in records),
            "base_resolved": sum(row["base_resolved"] for row in records),
        },
        "records": records,
    }
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


def inspect_action(request):
    """Stage and inspect an explicitly selected owner SDK; retain failures privately."""
    from common import ROOT, WORK, now

    value = json.loads(Path(request).read_text())
    if not isinstance(value, dict) or set(value) != {"binary"} or not isinstance(value["binary"], str) or not Path(value["binary"]).is_absolute():
        raise ValueError("Expected an explicit absolute owner SDK binary path")
    binary = Path(value["binary"]).resolve(strict=True)
    if hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary; refuse before staging")
    destination = WORK / "experiments/phone-registry" / now()
    destination.mkdir(parents=True, exist_ok=False)
    result = {
        "success": False,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "request": value,
        "executes_sdk": False,
    }
    try:
        shutil.copyfile(__file__, destination / "reader.py")
        shutil.copyfile(Path(__file__).with_name("phone_registry_literals.py"), destination / "phone_registry_literals.py")
        shutil.copyfile(binary, destination / "owner-sdk")
        inputs = {name: hashlib.sha256((destination / name).read_bytes()).hexdigest() for name in ("reader.py", "phone_registry_literals.py", "owner-sdk")}
        if inputs["owner-sdk"] != BINARY_SHA256:
            raise ValueError("SDK changed while staging the private input")
        (destination / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
        with (destination / "host.log").open("x") as log:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", str(destination / "reader.py"), str(destination / "owner-sdk"), str(destination / "registry.json")],
                cwd=destination,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
        if completed.returncode:
            raise RuntimeError(f"SDK registry reader exit {completed.returncode}")
        report = json.loads((destination / "registry.json").read_text())
        result.update(
            success=True,
            input_sha256=inputs,
            registry_sha256=hashlib.sha256((destination / "registry.json").read_bytes()).hexdigest(),
            counts=report["counts"],
            root_generation_qualified=False,
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result["failure"] = str(error)
    (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result | {"evidence": str(destination)}, indent=2))
    if not result["success"]:
        raise RuntimeError("SDK registry inspection failed; retain its private evidence")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Expected OWNER_SDK_BINARY NEW_PRIVATE_REPORT.json")
    report = inspect(*sys.argv[1:])
    print(json.dumps({"profile": report["profile"], "records": len(report["records"]), "root_generation_qualified": False}))
