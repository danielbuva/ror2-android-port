"""Read a pinned SDK's normal-path class-search metadata; never execute SDK code.

This is bounded data-flow inspection, not a CPU emulator, runtime or root
generator. No namespace list, assembly template or captured mapping is embedded.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


def support(name):
    spec = importlib.util.spec_from_file_location("_wrapper_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Authored sibling tooling only.
    return module


registry = support("phone_registry")
literals = support("phone_registry_literals")
FUNCTION = "__ZL30FindScriptingClassForClassNamePKcS0_"
FORMATTER = "__Z12FormatStringPKcz"
LOOKUP = "__Z29scripting_class_from_fullnamePKcS0_S0_"


def cstring(image, address):
    raw = bytearray()
    for offset in range(256):
        value = image.at(address + offset, 1)[0]
        if value == 0:
            return raw.decode("ascii")
        raw.append(value)
    raise ValueError("Unterminated search metadata string")


def move(word):
    return (word >> 16) & 31 if word & 0xFFE0FFE0 == 0xAA0003E0 else None


def compare_immediate(word):
    if word & 0x7F00001F != 0x7100001F:
        return None
    return (word >> 5) & 31, ((word >> 10) & 4095) << (12 if word & 0x400000 else 0)


def effects(word):
    known = literals.integer_writes(word)
    if known is not None:
        return known
    if word & 0xFFE00C00 == 0x9A800000:  # Integer CSEL; flags are unchanged.
        return {word & 31}
    if compare_immediate(word) is not None or word & 0x7F20001F == 0x6B00001F:
        return set()  # CMP changes flags only, never SP or an integer register.
    return None


class SearchReader:
    def __init__(self, image, function=FUNCTION, formatter=FORMATTER, lookup=LOOKUP):
        self.image = image
        self.words = literals.function_words(image, function)
        self.start = min(self.words)
        self.edges = literals.graph(self.words)
        if any(target <= pc for pc, targets in self.edges.items() for target in targets):
            raise ValueError("Backward search control flow is unsupported")
        self.dominance = literals.dominators(self.edges)
        self.writes = {pc: effects(word) for pc, word in self.words.items()}
        self.formatter, self.lookup = image.symbol(formatter), image.symbol(lookup)
        returns = [pc for pc, word in self.words.items() if word == 0xD65F03C0]
        if len(returns) != 1:
            raise ValueError("Search function must have one bounded normal return")
        self.return_pc = min(returns)

    def definition(self, use, register):
        if use not in self.dominance or not 0 <= register < 31:
            raise ValueError("Unreachable search operand or invalid register")
        for pc in range(use - 4, self.start - 1, -4):
            changes = self.writes[pc]
            if changes is None:
                raise ValueError("Unknown instruction before search operand")
            if register in changes:
                if pc not in self.dominance[use]:
                    raise ValueError("Search operand definition can be skipped")
                return pc
        return None

    def parameter(self, use, register, budget=64):
        if budget <= 0 or register == 31:
            return None
        pc = self.definition(use, register)
        if pc is None:
            return register
        source = move(self.words[pc])
        return self.parameter(pc, source, budget - 1) if source is not None else None

    def stack_offset(self, use, register, budget=64):
        if register == 31:
            return 0  # decode() separately proves one fixed frame through all uses.
        if budget <= 0:
            raise ValueError("Search stack-address budget exhausted")
        pc = self.definition(use, register)
        if pc is None:
            return None
        word = self.words[pc]
        source = move(word)
        if source is not None:
            # ORR/MOV register 31 is XZR. Only memory/immediate-address base
            # operands use that encoding for SP; zero is not a stack origin.
            return None if source == 31 else self.stack_offset(pc, source, budget - 1)
        if word & 0xFF000000 in (0x91000000, 0xD1000000):
            base = self.stack_offset(pc, (word >> 5) & 31, budget - 1)
            amount = ((word >> 10) & 4095) << (12 if word & 0x400000 else 0)
            return None if base is None else base + (-amount if word & 0x40000000 else amount)
        return None

    def constant(self, use, register):
        def retained(pc):
            result = {}
            for saved in range(19, 29):
                definition = self.definition(pc, saved)
                if definition is not None:
                    value = registry.call_argument(self.image, definition + 4, saved)
                    if value is not None:
                        result[saved] = (definition, value)
            return result

        return registry.call_argument(self.image, use, register, retained=retained)

    def load(self, use, register, budget=64):
        if budget <= 0:
            raise ValueError("Search load-address budget exhausted")
        pc = self.definition(use, register)
        if pc is None:
            raise ValueError("Missing search pointer load")
        word = self.words[pc]
        source = move(word)
        if source is not None:
            return self.load(pc, source, budget - 1)
        if word & 0x3FC00000 != 0x39400000:
            raise ValueError("Search pointer is not an unsigned literal/stack load")
        width, base = 1 << ((word >> 30) & 3), (word >> 5) & 31
        offset = ((word >> 10) & 4095) * width
        stack = self.stack_offset(pc, base)
        if stack is not None:
            return "stack", stack + offset, width
        address = self.constant(pc, base)
        if address is None:
            raise ValueError("Unresolved search global address")
        return "global", address + offset, width

    def pointer_string(self, use, register):
        kind, address, width = self.load(use, register)
        if kind != "global" or width != 8 or address % 8:
            raise ValueError("Search string is not a file-backed pointer slot")
        pointer = struct.unpack("<Q", self.image.at(address, 8))[0]
        return cstring(self.image, pointer), address

    def comparison(self, use):
        for pc in range(use - 4, max(self.start - 1, use - 32), -4):
            word = self.words[pc]
            found = compare_immediate(word)
            if found is not None:
                return pc, *found
            if not (
                word & 0xFF000000 == 0x91000000
                or move(word) is not None
                or word & 0x9F000000 in (0x10000000, 0x90000000)
                or word & 0x3FC00000 == 0x39400000
                or word == 0xD503201F
            ):
                raise ValueError("Unqualified flags before string selection")
        raise ValueError("Missing string-selection comparison")

    def formatted_pointer(self, use, register, buffer):
        pc = self.definition(use, register)
        if pc is None:
            return None
        word = self.words[pc]
        source = move(word)
        if source is not None:
            return self.formatted_pointer(pc, source, buffer)
        if word & 0xFFE00C00 != 0x9A800000:
            return None
        if (word >> 12) & 15 != 0 or self.stack_offset(pc, (word >> 5) & 31) != buffer:
            raise ValueError("Unqualified formatted-string selector")
        if self.load(pc, (word >> 16) & 31) != ("stack", buffer, 8):
            raise ValueError("Formatted-string heap pointer comes from another object")
        comparison, tag, value = self.comparison(pc)
        kind, offset, width = self.load(comparison, tag)  # At comparison, before a later register reuse.
        if kind != "stack" or width != 1 or not buffer + 8 <= offset < self.frame or not 0 <= value <= 255:
            raise ValueError("Unqualified formatted-string tag")
        return offset, value

    def result_origin(self, use, register, budget=64):
        if budget <= 0 or register == 31:
            return None
        pc = self.definition(use, register)
        if pc is None:
            return None
        word = self.words[pc]
        source = move(word)
        if source is not None:
            return self.result_origin(pc, source, budget - 1)
        if register == 0 and word & 0xFC000000 == 0x94000000 and pc + registry.signed(word & 0x3FFFFFF, 26) * 4 == self.lookup:
            return pc
        return None

    def decode(self):
        calls = {
            pc: pc + registry.signed(word & 0x3FFFFFF, 26) * 4 for pc, word in self.words.items() if pc < self.return_pc and word & 0xFC000000 == 0x94000000
        }
        lookups = [pc for pc, target in calls.items() if target == self.lookup]
        formats = [pc for pc, target in calls.items() if target == self.formatter]
        if not 1 <= len(lookups) <= 256 or len(formats) != 1 or formats[0] >= lookups[0]:
            raise ValueError("Unqualified formatter/search call coverage")
        formatted = formats[0]
        first = self.words[self.start]
        self.frame = (first >> 10) & 4095
        if first & 0xFFC003FF != 0xD10003FF or not 0 < self.frame <= 4096 or self.frame % 16:
            raise ValueError("Unqualified fixed search frame")
        guards = []
        for pc in range(self.start, lookups[-1] + 4, 4):
            word, changes = self.words[pc], self.writes[pc]
            if changes is None or pc != self.start and 31 in changes:
                raise ValueError("Unknown instruction or changing search frame")
            if pc in calls and calls[pc] not in (self.formatter, self.lookup):
                raise ValueError("Unexpected call in search sequence")
            if word & 0xFF000000 == 0xB5000000:
                guards.append((pc, pc + registry.signed((word >> 5) & 0x7FFFF, 19) * 4, word & 31))
            elif word & 0xFC000000 == 0x14000000 or word & 0xFF000010 == 0x54000000 or word & 0x7E000000 in (0x34000000, 0x36000000):
                raise ValueError("Unqualified search branch")
            if pc > formatted and literals.store(word) is not None:
                raise ValueError("Potential search-buffer/global alias write")
        if len(guards) != len(lookups) - 1 or len({target for _, target, _ in guards}) != 1:
            raise ValueError("Search success/fallthrough coverage differs")
        exit_pc = guards[0][1]
        if not lookups[-1] < exit_pc < self.return_pc or exit_pc not in self.words:
            raise ValueError("Invalid common search exit")
        buffer = self.stack_offset(formatted, 8)
        if buffer is None or not 8 <= buffer < self.frame:
            raise ValueError("Missing formatted-string result storage")
        writes = []
        for pc in range(self.start, formatted, 4):
            for base, offset, width, register, vector in literals.store(self.words[pc]) or []:
                origin = self.stack_offset(pc, base)
                if origin is None:
                    raise ValueError("Potential variadic-argument alias write")
                offset += origin
                if offset < 8 and 0 < offset + width:
                    writes.append((pc, offset, width, register, vector))
        if not writes:
            raise ValueError("Missing Darwin variadic module argument")
        pc, offset, width, register, vector = writes[-1]
        if pc not in self.dominance[formatted] or (offset, width, vector) != (0, 8, False) or self.parameter(pc, register) != 1:
            raise ValueError("Unproven Darwin variadic module argument")
        format_address = self.constant(formatted, 0)
        template = cstring(self.image, format_address) if format_address is not None else ""
        if template.count("%s") != 1 or template.count("%") != 1 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*\.dll", template.replace("%s", "Authored")):
            raise ValueError("Unsupported assembly-name format")
        returned = self.definition(self.return_pc, 0)
        saved = move(self.words[returned]) if returned is not None else None
        if saved is None or not 19 <= saved <= 28:
            raise ValueError("Search result is not returned from a preserved register")
        for index, (guard, target, register) in enumerate(guards):
            if (
                not lookups[index] < guard < lookups[index + 1]
                or self.result_origin(guard, register) != lookups[index]
                or self.result_origin(guard, saved) != lookups[index]
            ):
                raise ValueError("Success guard/result does not correspond to this lookup")
        tail = range(lookups[-1] + 4, exit_pc, 4)
        if any(move(self.words[pc]) is None and self.words[pc] != 0xD503201F for pc in tail):
            raise ValueError("Unqualified final search-result transfer")
        copies = [pc for pc in tail if saved in self.writes[pc]]
        if len(copies) != 1 or self.result_origin(copies[0], move(self.words[copies[0]])) != lookups[-1]:
            raise ValueError("Final lookup result is not preserved")
        ancestors, pending = set(), [returned]
        predecessors = {pc: [] for pc in self.words}
        for pc, targets in self.edges.items():
            for target in targets:
                predecessors[target].append(pc)
        while pending:
            pc = pending.pop()
            if pc >= exit_pc and pc not in ancestors:
                ancestors.add(pc)
                pending.extend(predecessors[pc])
        for pc in ancestors - {returned}:
            changes = self.writes[pc]
            if changes is None or saved in changes:
                raise ValueError("Search result can be overwritten before return")
        rows, tags = [], set()
        for pc in lookups:
            if pc not in self.dominance or self.parameter(pc, 2) != 0:
                raise ValueError("Unproven original native-name argument")
            namespace, slot = self.pointer_string(pc, 1)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", namespace):
                raise ValueError("Invalid namespace metadata")
            tag = self.formatted_pointer(pc, 0, buffer)
            if tag is not None:
                tags.add(tag)
                assembly = {"kind": "module-format", "template": template}
            else:
                name, assembly_slot = self.pointer_string(pc, 0)
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*\.dll", name):
                    raise ValueError("Invalid fixed assembly metadata")
                assembly = {"kind": "literal", "name": name, "slot": assembly_slot}
            rows.append({"call": pc, "namespace": namespace, "namespace_slot": slot, "assembly": assembly})
        if len(tags) != 1:
            raise ValueError("Inconsistent formatted-string storage selection")
        return {"normal_path_qualified": True, "lookup_sequence": rows}


def inspect(binary, output):
    binary, output = Path(binary), Path(output)
    if output.exists():
        raise FileExistsError("Refuse to replace a search report")
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary")
    report = SearchReader(registry.MachO(data)).decode()
    report.update(profile=registry.PROFILE, binary_sha256=registry.BINARY_SHA256, executes_sdk=False, root_generation_qualified=False)
    if hashlib.sha256(binary.read_bytes()).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("SDK changed during search metadata inspection")
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return report


def inspect_action(request):
    from common import ROOT, WORK, now

    value = json.loads(Path(request).read_text())
    if not isinstance(value, dict) or set(value) != {"binary"} or not isinstance(value["binary"], str) or not Path(value["binary"]).is_absolute():
        raise ValueError("Expected an explicit absolute owner SDK binary path")
    binary = Path(value["binary"]).resolve(strict=True)
    if hashlib.sha256(binary.read_bytes()).hexdigest() != registry.BINARY_SHA256:
        raise ValueError("Unknown owner SDK binary; refuse before staging")
    destination = WORK / "experiments/phone-wrapper-search" / now()
    destination.mkdir(parents=True, exist_ok=False)
    result = {
        "success": False,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "request": value,
        "executes_sdk": False,
    }
    try:
        for name in ("phone_wrapper_search.py", "phone_registry.py", "phone_registry_literals.py"):
            shutil.copyfile(Path(__file__).with_name(name), destination / name)
        shutil.copyfile(binary, destination / "owner-sdk")
        inputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()}
        if inputs["owner-sdk"] != registry.BINARY_SHA256:
            raise ValueError("SDK changed during staging")
        (destination / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
        with (destination / "host.log").open("x") as log:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", str(destination / "phone_wrapper_search.py"), str(destination / "owner-sdk"), str(destination / "search.json")],
                cwd=destination,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
        if completed.returncode:
            raise RuntimeError("Search reader exit " + str(completed.returncode))
        report = json.loads((destination / "search.json").read_text())
        result.update(
            success=True,
            inputs=inputs,
            search_sha256=hashlib.sha256((destination / "search.json").read_bytes()).hexdigest(),
            lookups=len(report["lookup_sequence"]),
            root_generation_qualified=False,
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result["failure"] = str(error)
    (destination / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result | {"evidence": str(destination)}, indent=2))
    if not result["success"]:
        raise RuntimeError("SDK search inspection failed; preserve its evidence")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Expected OWNER_SDK_BINARY NEW_PRIVATE_REPORT.json")
    report = inspect(*sys.argv[1:])
    print(json.dumps({"lookups": len(report["lookup_sequence"]), "root_generation_qualified": False}))
