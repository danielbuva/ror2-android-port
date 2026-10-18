"""Source-only contracts for the runtime config/report split; never reads work/."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools/unity/PortSession.cs"
TOKEN = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\w+|[^\s]')
PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">"}


def tokens(source):
    return [match[0] for match in TOKEN.finditer(source) if not match[0].startswith(("//", "/*"))]


def closing(parts, opening):
    end = PAIRS[parts[opening]]
    depth = 0
    for index in range(opening, len(parts)):
        if parts[index] == parts[opening]:
            depth += 1
        elif parts[index] == end:
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError(f"Unclosed {parts[opening]}")


def split_top_level(parts, separator):
    start = index = 0
    while index < len(parts):
        if parts[index] in PAIRS:
            index = closing(parts, index)
        elif parts[index] == separator:
            yield parts[start:index]
            start = index + 1
        index += 1
    if start < len(parts):
        yield parts[start:]


def fields(source, class_name):
    parts = tokens(source)
    start = next(index + 2 for index in range(len(parts) - 1) if parts[index : index + 2] == ["class", class_name])
    if parts[start] != "{":
        raise AssertionError(f"{class_name} must be an independent DTO")
    body = parts[start + 1 : closing(parts, start)]
    result = {}
    for declaration in split_top_level(body, ";"):
        index = 0
        while declaration[index] == "[":
            index = closing(declaration, index) + 1
        attributes = tuple(declaration[:index])
        if declaration[index] != "public":
            raise AssertionError(f"Expected public field: {declaration}")
        index += 1
        type_start = index
        while index < len(declaration):
            if declaration[index] in PAIRS:
                index = closing(declaration, index) + 1
            elif index + 1 == len(declaration) or declaration[index + 1] in (",", "="):
                break
            else:
                index += 1
        field_type = tuple(declaration[type_start:index])
        if not field_type or field_type[0] in ("static", "const", "class"):
            raise AssertionError(f"Expected instance field: {declaration}")
        for member in split_top_level(declaration[index:], ","):
            name = member[0]
            if not re.fullmatch(r"[A-Za-z_]\w*", name) or len(member) > 1 and member[1] != "=":
                raise AssertionError(f"Unsupported field declarator: {member}")
            if name in result:
                raise AssertionError(f"Duplicate field: {name}")
            result[name] = (attributes, field_type, tuple(member[2:]))
    return result


class SessionConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PROBE.read_text()
        cls.config = fields(cls.source, "SessionConfig")
        cls.report = fields(cls.source, "SessionReport")
        cls.sources = {path: path.read_text() for directory in ("tools", "android") for path in sorted((ROOT / directory).rglob("*.cs"))}
        cls.partials = {path: source for path, source in cls.sources.items() if "partial class PortSession" in source}

    def test_config_is_serializable_sealed_and_independent(self):
        self.assertRegex(self.source, r"\[Serializable\]\s+public\s+sealed\s+class\s+SessionConfig\s*\{")

    def test_fields_have_identical_attributes_types_and_initializers(self):
        self.assertEqual(len(self.config), 184)
        self.assertFalse(self.config.keys() - self.report.keys(), "Config contains a field absent from SessionReport")
        for name, declaration in self.config.items():
            with self.subTest(field=name):
                self.assertEqual(declaration, self.report[name])
        self.assertEqual(list(self.config), [name for name in self.report if name in self.config])

    def test_config_contains_exactly_the_fields_read_from_config(self):
        reads = set()
        for source in self.partials.values():
            reads.update(re.findall(r"\b(?:cfg|config|integratedStageConfig)\s*\.\s*(\w+)", source))
        # EntityStateConfiguration locals also use cfg, for fields absent from SessionReport.
        self.assertEqual(set(self.config), reads & self.report.keys())

    def test_runtime_resource_parses_use_session_config(self):
        parses = []
        # MovementBatchProbe is the unchanged resource/file name.
        pattern = re.compile(
            r'JsonUtility\s*\.\s*FromJson\s*<\s*(\w+)\s*>\s*\(\s*Resources\s*\.\s*Load\s*<\s*TextAsset\s*>\s*\(\s*"MovementBatchProbe"\s*\)\s*\.\s*text\s*\)'
        )
        for path, source in self.sources.items():
            parses.extend((path.name, match[1]) for match in pattern.finditer(source))
        self.assertEqual(len(parses), 11)
        self.assertEqual({type_name for _, type_name in parses}, {"SessionConfig"})

    def test_only_selection_json_is_parsed_as_result(self):
        # Restrict every SessionReport parse, also catching resource reads through aliases.
        parses = []
        for path, source in self.sources.items():
            parts = tokens(source)
            for index in range(len(parts) - 4):
                if parts[index : index + 4] != ["JsonUtility", ".", "FromJson", "<"]:
                    continue
                end_type = closing(parts, index + 3)
                type_name = parts[index + 4 : end_type]
                if type_name != ["PortSession", ".", "SessionReport"] and not (path in self.partials and type_name == ["SessionReport"]):
                    continue
                opening = end_type + 1
                self.assertEqual(parts[opening], "(")
                parses.append((path.name, parts[opening + 1 : closing(parts, opening)]))
        self.assertEqual(parses, [(PROBE.name, ["File", ".", "ReadAllText", "(", "path", ")"])])

    @unittest.skip("Runtime JSON keys inherit ignored work/ state; the clone has no authoritative tracked key inventory")
    def test_runtime_json_keys_cover_session_config(self):
        pass


class FieldParserTests(unittest.TestCase):
    def test_grouped_fields_attributes_nested_types_and_initializers(self):
        actual = fields(
            """class Fixture {
                [Marker("{},;")] public string a="x,y",b;
                public ExistingSpec[] specs;
                public int count=23;
                public List<ExistingSpec> values=new List<ExistingSpec>();
            }""",
            "Fixture",
        )
        self.assertEqual(list(actual), ["a", "b", "specs", "count", "values"])
        self.assertEqual(actual["a"], (("[", "Marker", "(", '"{},;"', ")", "]"), ("string",), ('"x,y"',)))
        self.assertEqual(actual["b"], (actual["a"][0], ("string",), ()))
        self.assertEqual(actual["specs"], ((), ("ExistingSpec", "[", "]"), ()))
        self.assertEqual(actual["count"], ((), ("int",), ("23",)))
        self.assertEqual(actual["values"][1], ("List", "<", "ExistingSpec", ">"))


if __name__ == "__main__":
    unittest.main()
