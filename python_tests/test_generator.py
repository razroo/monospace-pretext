from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_CLI = REPO_ROOT / "python" / "cli.py"


class MonospaceFontGeneratorTests(unittest.TestCase):
    def test_generator_makes_spacing_glyphs_share_one_advance_width(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_font = tmp_path / "fixture.ttf"
            output_font = tmp_path / "fixture-mono.ttf"
            build_fixture_font(source_font)

            subprocess.run(
                [
                    sys.executable,
                    str(PYTHON_CLI),
                    str(source_font),
                    "--output",
                    str(output_font),
                    "--width-mode",
                    "max",
                    "--outline-mode",
                    "normalize",
                    "--normalization-strength",
                    "1",
                ],
                check=True,
                cwd=REPO_ROOT,
            )

            generated = TTFont(output_font)
            metrics = generated["hmtx"].metrics
            self.assertEqual(metrics["space"][0], metrics["A"][0])
            self.assertEqual(metrics["A"][0], metrics["i"][0])
            self.assertEqual(generated["post"].isFixedPitch, 1)

            source = TTFont(source_font)
            self.assertLess(source["hmtx"].metrics["i"][0], generated["hmtx"].metrics["i"][0])

            source_bounds = glyph_bounds(source, "i")
            generated_bounds = glyph_bounds(generated, "i")
            self.assertIsNotNone(source_bounds)
            self.assertIsNotNone(generated_bounds)
            assert source_bounds is not None
            assert generated_bounds is not None
            self.assertGreater(generated_bounds[2] - generated_bounds[0], source_bounds[2] - source_bounds[0])


def build_fixture_font(path: Path) -> None:
    upem = 1000
    fb = FontBuilder(upem, isTTF=True)
    glyph_order = [".notdef", "space", "A", "i"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({32: "space", 65: "A", 105: "i"})
    fb.setupGlyf(
        {
            ".notdef": rectangle_glyph(0, 0, 600, 700),
            "space": empty_glyph(),
            "A": rectangle_glyph(50, 0, 650, 700),
            "i": rectangle_glyph(100, 0, 220, 700),
        }
    )
    fb.setupHorizontalMetrics(
        {
            ".notdef": (700, 0),
            "space": (280, 0),
            "A": (700, 0),
            "i": (280, 0),
        }
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(
        {
            "familyName": "Fixture Sans",
            "styleName": "Regular",
            "uniqueFontIdentifier": "Fixture Sans Regular",
            "fullName": "Fixture Sans Regular",
            "psName": "FixtureSans-Regular",
            "version": "Version 1.000",
        }
    )
    fb.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.save(path)


def empty_glyph():
    pen = TTGlyphPen(None)
    return pen.glyph()


def rectangle_glyph(x0: int, y0: int, x1: int, y1: int):
    pen = TTGlyphPen(None)
    pen.moveTo((x0, y0))
    pen.lineTo((x1, y0))
    pen.lineTo((x1, y1))
    pen.lineTo((x0, y1))
    pen.closePath()
    return pen.glyph()


def glyph_bounds(font: TTFont, glyph_name: str):
    glyph = font["glyf"][glyph_name]
    glyph.recalcBounds(font["glyf"])
    return (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)


if __name__ == "__main__":
    unittest.main()
