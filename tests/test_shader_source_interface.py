"""Public-safe synthetic contracts for recovered shader input binding."""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts/lab"))
from shader_source import bind_hlsl  # noqa: E402


class ShaderSourceInterfaceTests(unittest.TestCase):
    def layout(self):
        return {"buffers": [], "textures": []}

    def test_measured_noperspective_system_input_is_preserved(self):
        source = (
            "void main(noperspective float4 position : SV_POSITION0, "
            "float2 uv : TEXCOORD0, out precise float4 color : SV_Target0) "
            "{ color = float4(uv, position.xy); }"
        )
        bound, parameters, *_ = bind_hlsl(source, self.layout(), "mapped")
        self.assertIn("noperspective float4 position : SV_POSITION0", bound)
        self.assertEqual(parameters[0]["semantic"], "SV_POSITION0")
        self.assertEqual(parameters[1]["semantic"], "TEXCOORD0")

    def test_unqualified_inputs_keep_the_existing_contract(self):
        source = "void main(float2 uv : TEXCOORD0, out float4 color : SV_Target0) { color=0; }"
        bound, parameters, *_ = bind_hlsl(source, self.layout(), "mapped")
        self.assertEqual([p["semantic"] for p in parameters], ["TEXCOORD0", "SV_Target0"])
        self.assertNotIn("noperspective", bound)

    def test_noperspective_output_is_rejected(self):
        source = "void main(out noperspective float4 position : SV_POSITION0) { position=0; }"
        with self.assertRaisesRegex(RuntimeError, "noperspective I/O contract"):
            bind_hlsl(source, self.layout(), "mapped")

    def test_noperspective_varying_is_rejected_without_link_contract(self):
        source = "void main(noperspective float2 uv : TEXCOORD0) { }"
        with self.assertRaisesRegex(RuntimeError, "noperspective I/O contract"):
            bind_hlsl(source, self.layout(), "mapped")

    def test_other_interpolation_qualifiers_remain_unsupported(self):
        source = "void main(centroid float2 uv : TEXCOORD0) { }"
        with self.assertRaisesRegex(RuntimeError, "Unmeasured shader I/O shape"):
            bind_hlsl(source, self.layout(), "mapped")


if __name__ == "__main__":
    unittest.main()
