"""Verify the host comparison sends etcpak the expected blocks and channels."""

import ctypes
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools/phone-build/accepted-output"
with patch.object(sys, "path", [str(TOOLS), *sys.path]):
    from texture_compare import Etcpak


class EtcpakComparisonTest(unittest.TestCase):
    def test_contiguous_bgra_blocks_in_row_major_order(self):
        captured = []

        def encode_block(source, output, alpha):
            captured.append((source, alpha))
            ctypes.memset(output, len(captured), 16)

        adapter = Etcpak.__new__(Etcpak)
        adapter.encode_block = encode_block
        rgba = b"".join(bytes((i, i + 64, i + 128, i + 192)) for i in range(64))
        expected_blocks = []
        for start in (0, 4, 32, 36):
            positions = [start + y * 8 + x for y in range(4) for x in range(4)]
            expected_blocks.append(b"".join(bytes((i + 128, i + 64, i, i + 192)) for i in positions))

        for alpha, size in ((False, 8), (True, 16)):
            captured.clear()
            result = adapter.encode(rgba, 8, 8, alpha)
            self.assertEqual(captured, [(block, alpha) for block in expected_blocks])
            self.assertEqual(result, b"".join(bytes([i]) * size for i in range(1, 5)))
