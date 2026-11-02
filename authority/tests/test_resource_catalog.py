import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("catalog_resources", Path(__file__).resolve().parents[1] / "tools/catalog_resources.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CatalogTests(unittest.TestCase):
    def binary(self, count=2, pages=b"a.png\0b.png\0"):
        common = b"\0" * 8 + struct.pack("<H", count) + b"\0" * 5
        return b"BMF\x03" + struct.pack("<BI", 2, len(common)) + common + struct.pack("<BI", 3, len(pages)) + pages

    def test_binary_multi_page_font(self):
        self.assertEqual(module.font_pages(self.binary()), ["a.png", "b.png"])

    def test_binary_page_count_mismatch(self):
        with self.assertRaises(ValueError):
            module.font_pages(self.binary(1))

    def test_truncated_binary_block(self):
        with self.assertRaises(ValueError):
            module.font_pages(self.binary()[:-1])

    def test_text_and_xml_fonts(self):
        self.assertEqual(module.font_pages(b'page id=0 file="image.png"\n'), ["image.png"])
        self.assertEqual(module.font_pages(b'<font><pages><page file="image.png"/></pages></font>'), ["image.png"])

    def test_animation_metadata_and_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            resources = game / "mods/test/resources/gfx"
            resources.mkdir(parents=True)
            image = resources / "test.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            sprite = resources / "test.anm2"
            sprite.write_text('<AnimatedActor><Content><Spritesheets><Spritesheet Path="test.png"/></Spritesheets></Content><Animations DefaultAnimation="Idle"><Animation Name="Idle" FrameNum="1"/></Animations></AnimatedActor>')
            result = module.catalog(game, [str(sprite.relative_to(game))], [])
            record = result["resources"][0]
            self.assertEqual(record["animations"], {"Idle": 1})
            self.assertEqual(record["aliases"], ["gfx/test.anm2"])
            self.assertEqual(len(record["files"]), 2)
            self.assertTrue(all(len(f["sha256"]) == 64 for f in record["files"]))

    def test_dependency_escape_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            game = parent / "game"
            game.mkdir()
            (parent / "outside.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            (game / "escape.anm2").write_text('<AnimatedActor><Content><Spritesheets><Spritesheet Path="../outside.png"/></Spritesheets></Content><Animations DefaultAnimation="Idle"><Animation Name="Idle" FrameNum="1"/></Animations></AnimatedActor>')
            with self.assertRaisesRegex(ValueError, "outside game root"):
                module.catalog(game, ["escape.anm2"], [])

    def test_legacy_layer_timeline_exceeds_declared_frame_count(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            (game / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            (game / "cursor.anm2").write_text('<AnimatedActor><Content><Spritesheets><Spritesheet Path="image.png"/></Spritesheets></Content><Animations DefaultAnimation="Cursor"><Animation Name="Cursor" FrameNum="1"><RootAnimation><Frame Delay="1"/></RootAnimation><LayerAnimations><LayerAnimation><Frame Delay="2"/><Frame Delay="3"/></LayerAnimation></LayerAnimations></Animation></Animations></AnimatedActor>')
            record = module.catalog(game, ["cursor.anm2"], [])["resources"][0]
            self.assertEqual(record["animations"], {"Cursor": 5})
            self.assertEqual(record["declared_frames"], {"Cursor": 1})
            self.assertEqual(record["aliases"], ["cursor.anm2"])

    def test_invalid_animation_delay_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            (game / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            (game / "cursor.anm2").write_text('<AnimatedActor><Content><Spritesheets><Spritesheet Path="image.png"/></Spritesheets></Content><Animations DefaultAnimation="Cursor"><Animation Name="Cursor" FrameNum="1"><RootAnimation><Frame Delay="0"/></RootAnimation></Animation></Animations></AnimatedActor>')
            with self.assertRaisesRegex(ValueError, "Invalid animation timeline"):
                module.catalog(game, ["cursor.anm2"], [])

    def test_empty_animation_preserves_zero_declaration(self):
        metadata, _ = module.sprite_metadata(b'<AnimatedActor><Content/><Animations DefaultAnimation="Empty"><Animation Name="Empty" FrameNum="0"/></Animations></AnimatedActor>')
        self.assertEqual(metadata["declared_frames"], {"Empty": 0})
        self.assertEqual(metadata["animations"], {"Empty": 1})

    def test_duplicate_layer_id_refused(self):
        with self.assertRaisesRegex(ValueError, "sprite layers"):
            module.sprite_metadata(b'<AnimatedActor><Content><Layers><Layer Id="1"/><Layer Id="1"/></Layers></Content><Animations DefaultAnimation="Idle"><Animation Name="Idle" FrameNum="1"/></Animations></AnimatedActor>')


if __name__ == "__main__":
    unittest.main()
