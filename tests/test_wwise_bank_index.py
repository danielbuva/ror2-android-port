import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from wwise_bank_index import embedded_media


def chunk(tag, body):
    return tag + struct.pack("<I", len(body)) + body


class WwiseBankIndexTests(unittest.TestCase):
    def test_didx_identifies_embedded_media_and_subsong_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            bank = Path(temporary) / "fixture.bnk"
            didx = struct.pack("<III", 17, 0, 3) + struct.pack("<III", 29, 3, 2)
            bank.write_bytes(chunk(b"BKHD", b"\0" * 4) + chunk(b"DIDX", didx) + chunk(b"DATA", b"abcde"))
            self.assertEqual(embedded_media(bank), [{"id": 17, "subsong": 1, "bytes": 3}, {"id": 29, "subsong": 2, "bytes": 2}])
            bank.write_bytes(chunk(b"BKHD", b"\0" * 4) + chunk(b"DIDX", didx) + chunk(b"DATA", b"abcd"))
            with self.assertRaisesRegex(ValueError, "exceeds DATA"):
                embedded_media(bank)


if __name__ == "__main__":
    unittest.main()
