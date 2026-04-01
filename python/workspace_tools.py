from __future__ import annotations

import copy
import os
import shutil
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

from ufo2ft import compileTTF
from ufoLib2 import Font

from monospace_font_tools import (
    MonospaceGenerationError,
    OutlineMode,
    WidthMode,
    clamp,
    drop_hinting,
    get_best_name,
    interpolate_quantile,
    sanitize_postscript_name,
    update_font_metadata,
)


@dataclass(frozen=True)
class WorkspaceInitOptions:
    input_path: Path
    workspace_path: Path | None = None
    family_suffix: str = "Mono"


@dataclass(frozen=True)
class WorkspaceBuildOptions:
    workspace_path: Path
    output_dir: Path | None = None
    keep_hinting: bool = False
    emit_woff2: bool = True


def init_workspace(options: WorkspaceInitOptions) -> dict[str, str]:
    input_path = options.input_path.expanduser().resolve()
    if not input_path.exists():
        raise MonospaceGenerationError(f"input font not found: {input_path}")

    font = TTFont(input_path)
    if "glyf" not in font:
        raise MonospaceGenerationError(
            "workspace initialization currently supports only glyf-based fonts"
        )

    workspace_path = resolve_workspace_path(input_path, options.workspace_path)
    sources_dir = workspace_path / "sources"
    policies_dir = workspace_path / "policies"
    build_dir = workspace_path / "build"
    proof_dir = workspace_path / "proof"

    sources_dir.mkdir(parents=True, exist_ok=True)
    policies_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    proof_dir.mkdir(parents=True, exist_ok=True)

    original_copy = sources_dir / f"original{input_path.suffix.lower()}"
    if original_copy.resolve() != input_path:
        try:
            shutil.copy2(input_path, original_copy)
        except PermissionError:
            shutil.copyfile(input_path, original_copy)

    source_ufo_name = f"{input_path.stem}-source.ufo"
    source_ufo_path = sources_dir / source_ufo_name
    ufo = build_ufo_from_ttfont(font)
    ufo.save(source_ufo_path, overwrite=True)

    glyph_classes = derive_glyph_classes(font)
    write_yaml(policies_dir / "glyph-classes.yaml", {"classes": glyph_classes})
    write_yaml(policies_dir / "rules.yaml", default_rules())
    write_yaml(policies_dir / "overrides.yaml", {"glyphs": default_overrides()})

    project = {
        "version": 1,
        "workspaceName": input_path.stem,
        "familySuffix": options.family_suffix,
        "sourceFont": relative_to_workspace(workspace_path, original_copy),
        "sourceUfo": relative_to_workspace(workspace_path, source_ufo_path),
        "buildDir": "build",
        "proofDir": "proof",
        "outputFileName": f"{input_path.stem}-mono.ttf",
        "sourceFamilyName": get_best_name(font["name"], 16)
        or get_best_name(font["name"], 1)
        or input_path.stem,
        "sourceStyleName": get_best_name(font["name"], 17)
        or get_best_name(font["name"], 2)
        or "Regular",
    }
    write_yaml(workspace_path / "project.yaml", project)

    return {
        "workspace_path": str(workspace_path),
        "source_ufo_path": str(source_ufo_path),
        "project_path": str(workspace_path / "project.yaml"),
    }


def build_workspace(options: WorkspaceBuildOptions) -> dict[str, str | int | bool]:
    workspace_path = options.workspace_path.expanduser().resolve()
    project_path = workspace_path / "project.yaml"
    if not project_path.exists():
        raise MonospaceGenerationError(f"workspace missing project.yaml: {workspace_path}")

    project = read_yaml(project_path)
    policies = read_yaml(workspace_path / "policies" / "glyph-classes.yaml")
    rules = read_yaml(workspace_path / "policies" / "rules.yaml")
    overrides = read_yaml(workspace_path / "policies" / "overrides.yaml")

    source_ufo_path = workspace_path / project["sourceUfo"]
    if not source_ufo_path.exists():
        raise MonospaceGenerationError(f"workspace missing source UFO: {source_ufo_path}")

    source_ufo = Font.open(source_ufo_path)
    generated_ufo = copy.deepcopy(source_ufo)
    generated_ufo.info.familyName = f"{generated_ufo.info.familyName or project['sourceFamilyName']} {project['familySuffix']}".strip()
    generated_ufo.info.postscriptFontName = sanitize_postscript_name(
        f"{generated_ufo.info.familyName}-{generated_ufo.info.styleName or project['sourceStyleName']}"
    )

    build_dir = (options.output_dir.expanduser().resolve() if options.output_dir else workspace_path / project["buildDir"])
    build_dir.mkdir(parents=True, exist_ok=True)

    class_map = policies.get("classes", {})
    class_order = rules.get("classOrder", [])
    class_rules = rules.get("classes", {})
    defaults = rules.get("defaults", {})
    glyph_overrides = overrides.get("glyphs", {})

    target_width = resolve_ufo_target_width(generated_ufo, class_map, defaults)
    glyphs_changed = apply_workspace_policies(
        generated_ufo=generated_ufo,
        class_map=class_map,
        class_order=class_order,
        class_rules=class_rules,
        defaults=defaults,
        glyph_overrides=glyph_overrides,
        target_width=target_width,
    )

    generated_ufo_path = build_dir / f"{Path(project['outputFileName']).stem}.ufo"
    generated_ufo.save(generated_ufo_path, overwrite=True)

    built_ttf = compileTTF(generated_ufo, removeOverlaps=False)
    update_font_metadata(built_ttf, target_width, str(project.get("familySuffix", "Mono")))
    if not options.keep_hinting:
        drop_hinting(built_ttf)
    output_font_path = build_dir / project["outputFileName"]
    built_ttf.save(output_font_path)

    woff2_path = None
    if options.emit_woff2:
        woff2_font = TTFont(output_font_path)
        woff2_font.flavor = "woff2"
        woff2_path = output_font_path.with_suffix(".woff2")
        woff2_font.save(woff2_path)

    proof_dir = workspace_path / project["proofDir"]
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / "index.html"
    write_text(proof_path, render_proof_html(project, output_font_path, proof_path.parent))

    return {
        "workspace_path": str(workspace_path),
        "generated_ufo_path": str(generated_ufo_path),
        "output_font_path": str(output_font_path),
        "proof_path": str(proof_path),
        "target_width": target_width,
        "glyphs_changed": glyphs_changed,
        "woff2_emitted": bool(woff2_path),
    }


def resolve_workspace_path(input_path: Path, requested_workspace: Path | None) -> Path:
    if requested_workspace is not None:
        return requested_workspace.expanduser().resolve()
    return input_path.with_name(f"{input_path.stem}-workspace")


def relative_to_workspace(workspace_path: Path, target_path: Path) -> str:
    return str(target_path.relative_to(workspace_path))


def build_ufo_from_ttfont(font: TTFont) -> Font:
    ufo = Font()
    name_table = font["name"]
    best_cmap = font.getBestCmap() or {}
    unicodes_by_glyph: dict[str, list[int]] = {}
    for codepoint, glyph_name in best_cmap.items():
        unicodes_by_glyph.setdefault(glyph_name, []).append(codepoint)

    glyph_order = font.getGlyphOrder()
    ufo.glyphOrder = glyph_order
    ufo.info.familyName = get_best_name(name_table, 16) or get_best_name(name_table, 1) or "Generated Source"
    ufo.info.styleName = get_best_name(name_table, 17) or get_best_name(name_table, 2) or "Regular"
    ufo.info.unitsPerEm = getattr(font["head"], "unitsPerEm", 1000)
    ufo.info.ascender = getattr(font["hhea"], "ascent", None)
    ufo.info.descender = getattr(font["hhea"], "descent", None)
    ufo.info.capHeight = getattr(font["OS/2"], "sCapHeight", None) if "OS/2" in font else None
    ufo.info.xHeight = getattr(font["OS/2"], "sxHeight", None) if "OS/2" in font else None
    if "OS/2" in font:
        ufo.info.openTypeOS2WeightClass = getattr(font["OS/2"], "usWeightClass", None)
        ufo.info.openTypeOS2WidthClass = getattr(font["OS/2"], "usWidthClass", None)

    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"].metrics
    for glyph_name in glyph_order:
        glyph = ufo.newGlyph(glyph_name)
        glyph.width = hmtx[glyph_name][0]
        glyph.unicodes = sorted(unicodes_by_glyph.get(glyph_name, []))
        glyph_set[glyph_name].draw(glyph.getPen())

    return ufo


def derive_glyph_classes(font: TTFont) -> dict[str, list[str]]:
    classes: dict[str, list[str]] = {
        "uppercase": [],
        "lowercase": [],
        "digits": [],
        "punctuation": [],
        "symbols": [],
        "whitespace": [],
        "marks": [],
        "other": [],
    }
    best_cmap = font.getBestCmap() or {}
    unicode_by_glyph = {glyph_name: codepoint for codepoint, glyph_name in best_cmap.items()}

    for glyph_name in font.getGlyphOrder():
        if glyph_name == ".notdef":
            classes["other"].append(glyph_name)
            continue

        codepoint = unicode_by_glyph.get(glyph_name)
        if codepoint is None:
            classes["other"].append(glyph_name)
            continue

        category = unicodedata.category(chr(codepoint))
        if category in {"Mn", "Mc", "Me"}:
            classes["marks"].append(glyph_name)
        elif category.startswith("Z"):
            classes["whitespace"].append(glyph_name)
        elif category == "Nd":
            classes["digits"].append(glyph_name)
        elif category == "Lu":
            classes["uppercase"].append(glyph_name)
        elif category == "Ll":
            classes["lowercase"].append(glyph_name)
        elif category.startswith("P"):
            classes["punctuation"].append(glyph_name)
        elif category.startswith("S"):
            classes["symbols"].append(glyph_name)
        else:
            classes["other"].append(glyph_name)

    return classes


def default_rules() -> dict[str, Any]:
    return {
        "defaults": {
            "widthMode": "percentile",
            "percentile": 0.9,
            "targetWidthScale": 1.0,
            "outlineMode": "normalize",
            "normalizationStrength": 0.75,
            "fillRatio": 0.82,
            "skip": False,
        },
        "classOrder": [
            "marks",
            "whitespace",
            "digits",
            "uppercase",
            "lowercase",
            "punctuation",
            "symbols",
            "other",
        ],
        "classes": {
            "marks": {
                "skip": True,
            },
            "whitespace": {
                "outlineMode": "preserve",
            },
            "digits": {
                "fillRatio": 0.8,
                "normalizationStrength": 0.72,
            },
            "uppercase": {
                "fillRatio": 0.86,
                "normalizationStrength": 0.65,
            },
            "lowercase": {
                "fillRatio": 0.8,
                "normalizationStrength": 0.75,
            },
            "punctuation": {
                "fillRatio": 0.68,
                "normalizationStrength": 0.55,
            },
            "symbols": {
                "fillRatio": 0.78,
                "normalizationStrength": 0.7,
            },
        },
    }


def default_overrides() -> dict[str, dict[str, Any]]:
    return {
        "space": {
            "outlineMode": "preserve",
        },
        "period": {
            "fillRatio": 0.56,
        },
        "comma": {
            "fillRatio": 0.56,
        },
    }


def resolve_ufo_target_width(
    ufo: Font,
    class_map: dict[str, list[str]],
    defaults: dict[str, Any],
) -> int:
    widths: list[int] = []
    mark_set = set(class_map.get("marks", []))
    for glyph_name in ufo.glyphOrder:
        glyph = ufo[glyph_name]
        if glyph_name in mark_set or glyph.width <= 0 or glyph_name == ".notdef":
            continue
        widths.append(int(round(glyph.width)))

    if not widths:
        raise MonospaceGenerationError("workspace source UFO has no spacing glyphs")

    widths.sort()
    width_mode: WidthMode = defaults.get("widthMode", "percentile")
    percentile = clamp(float(defaults.get("percentile", 0.9)), 0.0, 1.0)
    if width_mode == "max":
        return widths[-1]
    if width_mode == "average":
        return max(1, int(round(sum(widths) / len(widths))))
    if width_mode == "median":
        middle = len(widths) // 2
        if len(widths) % 2 == 1:
            return widths[middle]
        return max(1, int(round((widths[middle - 1] + widths[middle]) / 2)))
    if width_mode == "percentile":
        return max(1, int(round(interpolate_quantile(widths, percentile))))
    raise MonospaceGenerationError(f"unsupported width mode in rules.yaml: {width_mode}")


def apply_workspace_policies(
    *,
    generated_ufo: Font,
    class_map: dict[str, list[str]],
    class_order: list[str],
    class_rules: dict[str, dict[str, Any]],
    defaults: dict[str, Any],
    glyph_overrides: dict[str, dict[str, Any]],
    target_width: int,
) -> int:
    class_sets = {class_name: set(glyph_names) for class_name, glyph_names in class_map.items()}
    glyphs_changed = 0

    for glyph_name in generated_ufo.glyphOrder:
        glyph = generated_ufo[glyph_name]
        glyph_policy = resolve_glyph_policy(
            glyph_name=glyph_name,
            defaults=defaults,
            class_sets=class_sets,
            class_order=class_order,
            class_rules=class_rules,
            glyph_overrides=glyph_overrides,
        )

        if bool(glyph_policy.get("skip", False)):
            continue

        target_width_scale = float(glyph_policy.get("targetWidthScale", 1.0))
        glyph_target_width = max(1, int(round(target_width * target_width_scale)))
        fill_ratio = clamp(float(glyph_policy.get("fillRatio", 0.82)), 0.1, 0.98)
        target_draw_width = max(1, int(round(glyph_target_width * fill_ratio)))
        outline_mode: OutlineMode = glyph_policy.get("outlineMode", "normalize")
        normalization_strength = clamp(
            float(glyph_policy.get("normalizationStrength", 0.75)),
            0.0,
            1.0,
        )

        bounds = measure_ufo_bounds(generated_ufo, glyph_name)
        if bounds is None:
            if int(round(glyph.width)) != glyph_target_width:
                glyph.width = glyph_target_width
                glyphs_changed += 1
            continue

        x_min, _, x_max, _ = bounds
        visible_width = x_max - x_min
        if visible_width <= 0:
            if int(round(glyph.width)) != glyph_target_width:
                glyph.width = glyph_target_width
                glyphs_changed += 1
            continue

        scale_x = resolve_workspace_scale_x(
            visible_width=visible_width,
            target_draw_width=target_draw_width,
            outline_mode=outline_mode,
            normalization_strength=normalization_strength,
        )
        center_x = (x_min + x_max) / 2
        dx = (glyph_target_width / 2) - (center_x * scale_x)
        if (
            int(round(glyph.width)) == glyph_target_width
            and abs(scale_x - 1.0) <= 1e-6
            and abs(dx) <= 1e-6
        ):
            continue

        transform_ufo_glyph(glyph, scale_x, dx)
        glyph.width = glyph_target_width
        glyphs_changed += 1

    return glyphs_changed


def resolve_workspace_scale_x(
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


def transform_ufo_glyph(glyph, scale_x: float, dx: float) -> None:
    recording_pen = RecordingPen()
    glyph.draw(recording_pen)
    anchors = list(glyph.anchors)
    glyph.clearContours()
    glyph.clearComponents()
    recording_pen.replay(TransformPen(glyph.getPen(), (scale_x, 0, 0, 1, dx, 0)))
    for anchor in anchors:
        anchor.x = int(round(anchor.x * scale_x + dx))


def measure_ufo_bounds(ufo: Font, glyph_name: str):
    pen = BoundsPen(ufo)
    ufo[glyph_name].draw(pen)
    return pen.bounds


def resolve_glyph_policy(
    *,
    glyph_name: str,
    defaults: dict[str, Any],
    class_sets: dict[str, set[str]],
    class_order: list[str],
    class_rules: dict[str, dict[str, Any]],
    glyph_overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    policy = dict(defaults)
    for class_name in class_order:
        if glyph_name in class_sets.get(class_name, set()):
            policy.update(class_rules.get(class_name, {}))
    policy.update(glyph_overrides.get(glyph_name, {}))
    return policy


def render_proof_html(project: dict[str, Any], output_font_path: Path, proof_dir: Path) -> str:
    generated_font_rel = relative_url(proof_dir, output_font_path)
    source_font_rel = relative_url(proof_dir, proof_dir.parent / project["sourceFont"])
    generated_family = f"{project['sourceFamilyName']} {project['familySuffix']}".strip()
    source_family = project["sourceFamilyName"]

    specimen_lines = [
        "WAVEFORM 2049 / glass orbit",
        "Rigid rhythm, proportional voice.",
        "0123456789 +-*/=%",
        "Sphinx of black quartz, judge my vow.",
    ]

    specimen_markup = "\n".join(
        f'        <p class="specimen-line">{line}</p>' for line in specimen_lines
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{generated_family} Proof</title>
    <style>
      @font-face {{
        font-family: "ProofSource";
        src: url("{source_font_rel}");
      }}
      @font-face {{
        font-family: "ProofGenerated";
        src: url("{generated_font_rel}");
      }}
      :root {{
        --bg: #f1ebdd;
        --ink: #181716;
        --muted: rgba(24, 23, 22, 0.6);
        --line: rgba(24, 23, 22, 0.12);
        --panel: rgba(255,255,255,0.72);
        --accent: #205442;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background:
          radial-gradient(circle at top left, rgba(32,84,66,0.08), transparent 34%),
          radial-gradient(circle at bottom right, rgba(186,95,52,0.08), transparent 28%),
          linear-gradient(180deg, #f8f3e9, #efe5d2);
        color: var(--ink);
        font-family: ui-sans-serif, system-ui, sans-serif;
      }}
      main {{
        width: min(1200px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 28px 0 36px;
      }}
      .hero, .panel {{
        border: 1px solid var(--line);
        border-radius: 28px;
        background: var(--panel);
        box-shadow: 0 18px 40px rgba(48, 33, 18, 0.08);
      }}
      .hero {{
        padding: 28px;
      }}
      .eyebrow {{
        margin: 0;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: var(--muted);
      }}
      .hero h1 {{
        margin: 12px 0 0;
        font-size: clamp(42px, 7vw, 78px);
        line-height: 0.94;
        font-family: "ProofGenerated", sans-serif;
      }}
      .hero p {{
        max-width: 72ch;
        font-size: 17px;
        line-height: 1.6;
        color: var(--muted);
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
        margin-top: 18px;
      }}
      .panel {{
        padding: 24px;
      }}
      .label {{
        margin: 0;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: var(--muted);
      }}
      .comparison {{
        margin-top: 16px;
        display: grid;
        gap: 16px;
      }}
      .comparison-block {{
        padding: 18px;
        border-radius: 20px;
        background: rgba(255,255,255,0.54);
        border: 1px solid rgba(24,23,22,0.08);
      }}
      .comparison-block h3 {{
        margin: 0 0 10px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        color: var(--muted);
      }}
      .comparison-block p {{
        margin: 0;
        font-size: 30px;
        line-height: 1.12;
      }}
      .source-font {{ font-family: "ProofSource", sans-serif; }}
      .generated-font {{ font-family: "ProofGenerated", monospace; }}
      .prose {{
        margin-top: 18px;
        font-size: 18px;
        line-height: 1.7;
      }}
      .metrics {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-top: 18px;
      }}
      .metric {{
        padding: 14px 16px;
        border-radius: 16px;
        background: rgba(32,84,66,0.05);
        border: 1px solid rgba(32,84,66,0.12);
      }}
      .metric strong {{
        display: block;
        font-size: 12px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.12em;
      }}
      .metric span {{
        display: block;
        margin-top: 6px;
        font-size: 22px;
        font-family: "ProofGenerated", monospace;
      }}
      .specimen-line {{
        margin: 0 0 10px;
        font-family: "ProofGenerated", monospace;
        font-size: clamp(26px, 4vw, 42px);
        line-height: 1.08;
      }}
      .note {{
        margin-top: 18px;
        font-size: 14px;
        line-height: 1.6;
        color: var(--muted);
      }}
      @media (max-width: 900px) {{
        .grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <p class="eyebrow">Generated Font Proof</p>
        <h1>{generated_family}</h1>
        <p>
          This proof page loads the actual generated font file, not the DOM monospace preview effect.
          Compare the original family against the generated output and use the workspace policies to iterate.
        </p>
      </section>

      <section class="grid">
        <article class="panel">
          <p class="label">Source vs Generated</p>
          <div class="comparison">
            <div class="comparison-block">
              <h3>{source_family}</h3>
              <p class="source-font">Typography can be made rigid without changing the typeface itself.</p>
            </div>
            <div class="comparison-block">
              <h3>{generated_family}</h3>
              <p class="generated-font">Typography can be made rigid without changing the typeface itself.</p>
            </div>
          </div>
          <p class="prose generated-font">
            Sphinx of black quartz, judge my vow. 0123456789. Pack the same rhythm into every advance width, then tune the policies until the texture feels intentional.
          </p>
        </article>

        <article class="panel">
          <p class="label">Specimen</p>
{specimen_markup}
          <div class="metrics">
            <div class="metric">
              <strong>Workspace</strong>
              <span>{project['workspaceName']}</span>
            </div>
            <div class="metric">
              <strong>Output</strong>
              <span>{output_font_path.name}</span>
            </div>
          </div>
          <p class="note">
            Edit <code>policies/rules.yaml</code> and <code>policies/overrides.yaml</code>, then rebuild the workspace to regenerate this proof.
          </p>
        </article>
      </section>
    </main>
  </body>
</html>
"""


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise MonospaceGenerationError(f"expected YAML mapping in {path}")
    return data


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def relative_url(from_dir: Path, target_path: Path) -> str:
    return Path(os.path.relpath(target_path, from_dir)).as_posix()
