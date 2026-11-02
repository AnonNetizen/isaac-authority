import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
import itertools

spec = importlib.util.spec_from_file_location("packed_resources", Path(__file__).resolve().parents[1] / "tools/packed_resources.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackedTests(unittest.TestCase):
    def archive(self, root, data=b"synthetic packed fixture", flags=None, mode=2, checksum=None, length=None):
        encoder = zlib.compressobj(wbits=-15)
        block = encoder.compress(data) + encoder.flush()
        payload = struct.pack("<I", (len(block) | 0x80000000) if flags is None else flags) + block
        name = "resources/gfx/fixture.anm2"
        entry = struct.pack("<IIIII", *module.name_hash(name), 14, len(data) if length is None else length,
                            module.checksum(data) if checksum is None else checksum)
        file = Path(root) / "fixture.a"
        file.write_bytes(struct.pack("<7sBIH", b"ARCH000", mode, 14 + len(payload), 1) + payload + entry)
        return file, name

    def test_known_filename_hash_and_case(self):
        self.assertEqual(module.name_hash("resources/gfx/005.100_collectible.anm2"), (959448724, 683989295))
        self.assertEqual(module.name_hash("RESOURCES/GFX/005.100_collectible.anm2"), (959448724, 683989295))

    def test_isaac_primary_reference_vector_across_generation_boundary(self):
        # Compiled Gibbed.Rebirth ISAAC.cs, entry seed high=0x12345678.
        words = list(itertools.islice(module.isaac_words(0x12345678), 260))
        expected = [-1595671154, -367210024, -2027043610, -372532283,
                    -1436798756, -1699364975, -1620080497, 1443376482,
                    -1428608183, 76675107, 340326976, 1444825225]
        self.assertEqual(words[:8] + words[256:], [n & 0xffffffff for n in expected])

    def test_compressed_entry_and_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            file, name = self.archive(root)
            data, metadata = module.Archive(file).read(name)
            self.assertEqual(data, b"synthetic packed fixture")
            self.assertEqual(metadata["entry"], name)
            self.assertEqual(len(metadata["sha256"]), 64)
            self.assertEqual(len(metadata["archive_sha256"]), 64)

    def test_changed_checksum_refused(self):
        with tempfile.TemporaryDirectory() as root:
            file, name = self.archive(root, checksum=0)
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                module.Archive(file).read(name)

    def test_invalid_header_and_index_bounds(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "bad.a"
            for data in (b"short", struct.pack("<7sBIH", b"ARCH000", 2, 1000, 1)):
                file.write_bytes(data)
                with self.assertRaises(ValueError):
                    module.Archive(file)

    def test_oversized_block_refused(self):
        with tempfile.TemporaryDirectory() as root:
            file, name = self.archive(root, flags=0x80000801)
            with self.assertRaisesRegex(ValueError, "Invalid MiniZ block"):
                module.Archive(file).read(name)

    def test_expansion_length_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as root:
            file, name = self.archive(root, data=b"a" * 500, length=10)
            with self.assertRaisesRegex(ValueError, "decoded block"):
                module.Archive(file).read(name)

    def test_missing_final_block_refused(self):
        with tempfile.TemporaryDirectory() as root:
            file, name = self.archive(root, flags=3)
            with self.assertRaises((ValueError, zlib.error)):
                module.Archive(file).read(name)

    def test_unsupported_mode_and_entry_limit(self):
        with tempfile.TemporaryDirectory() as root:
            for mode, length, reason in ((1, 10, "compression mode"), (2, module.LIMIT + 1, "size limit")):
                file, name = self.archive(root, mode=mode, length=length)
                with self.assertRaisesRegex(ValueError, reason):
                    module.Archive(file).read(name)


if __name__ == "__main__":
    unittest.main()
