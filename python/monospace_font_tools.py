from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

WidthMode = Literal["max", "average", "median", "percentile"]
OutlineMode = Literal["preserve", "fit", "normalize"]


class MonospaceGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GenerationOptions:
    input_path: Path
    output_path: Path | None = None
    target_width: int | None = None
    width_mode: WidthMode = "percentile"
    percentile: float = 0.9
    outline_mode: OutlineMode = "normalize"
    normalization_strength: float = 0.75
    fill_ratio: float = 0.82
    family_suffix: str = "Mono"
    keep_hinting: bool = False


def generate_monospace_font(options: GenerationOptions) -> dict[str, object]:
    input_path = options.input_path.expanduser().resolve()
    if not input_path.exists():
        raise MonospaceGenerationError(f"input font not found: {input_path}")

    font = TTFont(input_path)
    if "glyf" not in font:
        raise MonospaceGenerationError(
            "only glyf-based TrueType/OpenType fonts are supported right now"
        )

    output_path = resolve_output_path(input_path, options.output_path)
    glyph_set = font.getGlyphSet()
    glyf = font["glyf"]
    hmtx = font["hmtx"].metrics
    unicode_by_glyph = build_unicode_map(font)
    spacing_glyphs = [
        glyph_name
        for glyph_name in font.getGlyphOrder()
        if is_spacing_glyph(glyph_name, hmtx[glyph_name][0], unicode_by_glyph)
    ]
    if not spacing_glyphs:
        raise MonospaceGenerationError("no spacing glyphs found in the source font")

    target_width = resolve_target_width(font, spacing_glyphs, hmtx, options)
    target_draw_width = max(1, int(round(target_width * clamp(options.fill_ratio, 0.1, 0.98))))

    glyphs_changed = 0
    for glyph_name in font.getGlyphOrder():
        advance_width, left_side_bearing = hmtx[glyph_name]

        if not is_spacing_glyph(glyph_name, advance_width, unicode_by_glyph):
            continue

        bounds = measure_bounds(glyph_set, glyph_name)
        if bounds is None:
            if advance_width != target_width or left_side_bearing != 0:
                hmtx[glyph_name] = (target_width, 0)
                glyphs_changed += 1
            continue

        x_min, _, x_max, _ = bounds
        visible_width = x_max - x_min
        if visible_width <= 0:
            if advance_width != target_width or left_side_bearing != 0:
                hmtx[glyph_name] = (target_width, 0)
                glyphs_changed += 1
            continue

        scale_x = resolve_scale_x(
            visible_width=visible_width,
            target_draw_width=target_draw_width,
            outline_mode=options.outline_mode,
            normalization_strength=clamp(options.normalization_strength, 0.0, 1.0),
        )
        center_x = (x_min + x_max) / 2
        translated_center_x = target_width / 2
        dx = translated_center_x - (center_x * scale_x)

        if (
            advance_width == target_width
            and left_side_bearing == int(round(x_min))
            and math.isclose(scale_x, 1.0, rel_tol=1e-6, abs_tol=1e-6)
            and math.isclose(dx, 0.0, rel_tol=1e-6, abs_tol=1e-6)
        ):
            continue

        new_glyph = transform_glyph(glyph_set, glyph_name, glyf, scale_x, dx)
        glyf[glyph_name] = new_glyph
        hmtx[glyph_name] = (target_width, getattr(new_glyph, "xMin", 0))
        glyphs_changed += 1

    update_font_metadata(font, target_width, options.family_suffix)
    if not options.keep_hinting:
        drop_hinting(font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(output_path)

    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "target_width": target_width,
        "glyphs_changed": glyphs_changed,
        "outline_mode": options.outline_mode,
    }


def resolve_output_path(input_path: Path, requested_output: Path | None) -> Path:
    if requested_output is not None:
        return requested_output.expanduser().resolve()

    return input_path.with_name(f"{input_path.stem}-mono{input_path.suffix}")


def build_unicode_map(font: TTFont) -> dict[str, int]:
    best_cmap = font.getBestCmap() or {}
    return {glyph_name: codepoint for codepoint, glyph_name in best_cmap.items()}


def is_spacing_glyph(
    glyph_name: str,
    advance_width: int,
    unicode_by_glyph: dict[str, int],
) -> bool:
    if glyph_name == ".notdef":
        return False
    if advance_width <= 0:
        return False

    codepoint = unicode_by_glyph.get(glyph_name)
    if codepoint is None:
        return True

    category = unicodedata.category(chr(codepoint))
    return category not in {"Mn", "Me", "Cf"}


def resolve_target_width(
    font: TTFont,
    spacing_glyphs: list[str],
    hmtx: dict[str, tuple[int, int]],
    options: GenerationOptions,
) -> int:
    if options.target_width is not None:
        return max(1, int(options.target_width))

    widths = sorted(hmtx[glyph_name][0] for glyph_name in spacing_glyphs if hmtx[glyph_name][0] > 0)
    if not widths:
        raise MonospaceGenerationError("could not derive a target width from the source font")

    if options.width_mode == "max":
        return widths[-1]
    if options.width_mode == "average":
        return max(1, int(round(sum(widths) / len(widths))))
    if options.width_mode == "median":
        middle = len(widths) // 2
        if len(widths) % 2 == 1:
            return widths[middle]
        return max(1, int(round((widths[middle - 1] + widths[middle]) / 2)))
    if options.width_mode == "percentile":
        return max(1, int(round(interpolate_quantile(widths, clamp(options.percentile, 0.0, 1.0)))))

    raise MonospaceGenerationError(f"unsupported width mode: {options.width_mode}")


def measure_bounds(glyph_set, glyph_name: str):
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.bounds


def resolve_scale_x(
    *,
    visible_width: float,
    target_draw_width: int,
    outline_mode: OutlineMode,
    normalization_strength: float,
) -> float:
    if outline_mode == "preserve":
        return 1.0

    if outline_mode == "fit":
        if visible_width <= target_draw_width:
            return 1.0
        return target_draw_width / visible_width

    normalized_width = visible_width + ((target_draw_width - visible_width) * normalization_strength)
    return max(0.1, normalized_width / visible_width)


def transform_glyph(glyph_set, glyph_name: str, glyf, scale_x: float, dx: float):
    recording_pen = DecomposingRecordingPen(glyph_set)
    glyph_set[glyph_name].draw(recording_pen)

    tt_pen = TTGlyphPen(glyph_set)
    recording_pen.replay(TransformPen(tt_pen, (scale_x, 0, 0, 1, dx, 0)))
    glyph = tt_pen.glyph()
    glyph.recalcBounds(glyf)
    return glyph


def update_font_metadata(font: TTFont, target_width: int, family_suffix: str) -> None:
    if "post" in font:
        font["post"].isFixedPitch = 1
    if "hhea" in font:
        font["hhea"].advanceWidthMax = target_width
    if "OS/2" in font:
        font["OS/2"].xAvgCharWidth = target_width
        panose = getattr(font["OS/2"], "panose", None)
        if panose is not None and hasattr(panose, "bProportion"):
            panose.bProportion = 9

    rename_font(font, family_suffix.strip() or "Mono")


def rename_font(font: TTFont, family_suffix: str) -> None:
    if "name" not in font:
        return

    name_table = font["name"]
    family_name = get_best_name(name_table, 16) or get_best_name(name_table, 1) or "Generated Mono"
    style_name = get_best_name(name_table, 17) or get_best_name(name_table, 2) or "Regular"
    if family_name.endswith(family_suffix):
        new_family_name = family_name
    else:
        new_family_name = f"{family_name} {family_suffix}".strip()
    full_name = f"{new_family_name} {style_name}".strip()
    postscript_name = sanitize_postscript_name(full_name)

    for record in list(name_table.names):
        if record.nameID in {1, 16}:
            record.string = _encode_name(new_family_name, record)
        elif record.nameID in {4, 18}:
            record.string = _encode_name(full_name, record)
        elif record.nameID == 6:
            record.string = _encode_name(postscript_name, record)


def get_best_name(name_table, name_id: int) -> str | None:
    for platform_id, plat_enc_id, lang_id in (
        (3, 1, 0x409),
        (1, 0, 0),
    ):
        value = name_table.getName(name_id, platform_id, plat_enc_id, lang_id)
        if value is not None:
            return str(value)
    return None


def sanitize_postscript_name(value: str) -> str:
    compact = "".join(ch for ch in value if ch.isalnum())
    return compact[:63] or "GeneratedMono"


def _encode_name(value: str, record) -> bytes:
    if record.isUnicode():
        return value.encode("utf_16_be")
    return value.encode("mac_roman", errors="replace")


def drop_hinting(font: TTFont) -> None:
    for table_tag in ("fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX"):
        if table_tag in font:
            del font[table_tag]


def interpolate_quantile(sorted_values: list[int], percentile: float) -> float:
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * percentile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    ratio = position - lower_index
    return lower_value + ((upper_value - lower_value) * ratio)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
