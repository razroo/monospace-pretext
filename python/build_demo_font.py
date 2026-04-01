#!/usr/bin/env python3

from __future__ import annotations

import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont

from monospace_font_tools import GenerationOptions, generate_monospace_font


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FONT = REPO_ROOT / "demo" / "fonts" / "source" / "Roboto-Regular.ttf"
OUTPUT_WOFF2 = REPO_ROOT / "demo" / "fonts" / "generated" / "Roboto-DemoMono.woff2"


def build_demo_font() -> None:
    OUTPUT_WOFF2.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        output_ttf = Path(tmpdir) / "Roboto-DemoMono.ttf"
        report = generate_monospace_font(
            GenerationOptions(
                input_path=SOURCE_FONT,
                output_path=output_ttf,
                width_mode="percentile",
                percentile=0.9,
                outline_mode="normalize",
                normalization_strength=0.72,
                fill_ratio=0.84,
                family_suffix="DemoMono",
                keep_hinting=False,
            )
        )
        woff2_font = TTFont(output_ttf)
        woff2_font.flavor = "woff2"
        woff2_font.save(OUTPUT_WOFF2)

    print(f"Built demo font: {OUTPUT_WOFF2}")
    print(f"Target width: {report['target_width']}")
    print(f"Glyphs changed: {report['glyphs_changed']}")


if __name__ == "__main__":
    build_demo_font()
