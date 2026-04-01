#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from monospace_font_tools import (
        GenerationOptions,
        MonospaceGenerationError,
        generate_monospace_font,
    )
    from workspace_tools import (
        WorkspaceBuildOptions,
        WorkspaceInitOptions,
        build_workspace,
        init_workspace,
    )
except ModuleNotFoundError as error:
    missing_module = error.name or "unknown module"
    print(
        "monospace-pretext-font: missing Python dependency. "
        "Install it with `pip install -r python/requirements.txt`. "
        f"(missing: {missing_module})",
        file=sys.stderr,
    )
    raise SystemExit(1)


SUBCOMMANDS = {"generate", "init-workspace", "build-workspace"}


def add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path, help="Path to the source .ttf or glyf-based .otf font.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path for the generated font. Defaults to '<input-stem>-mono<input-suffix>'.",
    )
    parser.add_argument(
        "--target-width",
        type=int,
        help="Explicit target advance width in font units. Skips auto-width selection.",
    )
    parser.add_argument(
        "--width-mode",
        choices=["max", "average", "median", "percentile"],
        default="percentile",
        help="How to derive the shared advance width when --target-width is omitted.",
    )
    parser.add_argument(
        "--percentile",
        type=float,
        default=0.9,
        help="Percentile used by --width-mode percentile. Express as 0..1.",
    )
    parser.add_argument(
        "--outline-mode",
        choices=["preserve", "fit", "normalize"],
        default="normalize",
        help="How to adapt outlines to the shared width.",
    )
    parser.add_argument(
        "--normalization-strength",
        type=float,
        default=0.75,
        help="How strongly normalize mode pulls outlines toward the shared width. 0..1.",
    )
    parser.add_argument(
        "--fill-ratio",
        type=float,
        default=0.82,
        help="Fraction of the advance width that normalized outlines should occupy.",
    )
    parser.add_argument(
        "--family-suffix",
        default="Mono",
        help="Suffix appended to the generated font family name.",
    )
    parser.add_argument(
        "--keep-hinting",
        action="store_true",
        help="Keep hinting tables. Off by default because outline edits usually invalidate existing hints.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the generation report as JSON.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monospace-pretext-font",
        description="Generate draft monospace fonts and UFO-first workspaces from glyf-based source fonts.",
    )
    subparsers = parser.add_subparsers(dest="command")

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a draft monospaced font directly from a source font.",
    )
    add_generate_arguments(generate_parser)

    init_workspace_parser = subparsers.add_parser(
        "init-workspace",
        help="Create a UFO-first workspace with policy files and source assets.",
    )
    init_workspace_parser.add_argument(
        "input",
        type=Path,
        help="Path to the source .ttf or glyf-based .otf font.",
    )
    init_workspace_parser.add_argument(
        "--workspace",
        type=Path,
        help="Directory for the generated workspace. Defaults to '<input-stem>-workspace'.",
    )
    init_workspace_parser.add_argument(
        "--family-suffix",
        default="Mono",
        help="Suffix appended to the generated family name during workspace builds.",
    )
    init_workspace_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the workspace report as JSON.",
    )

    build_workspace_parser = subparsers.add_parser(
        "build-workspace",
        help="Build a generated font, UFO, and proof page from a workspace.",
    )
    build_workspace_parser.add_argument(
        "workspace",
        type=Path,
        help="Path to a workspace created by init-workspace.",
    )
    build_workspace_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory for generated font artifacts. Defaults to '<workspace>/build'.",
    )
    build_workspace_parser.add_argument(
        "--keep-hinting",
        action="store_true",
        help="Keep hinting tables in the built font.",
    )
    build_workspace_parser.add_argument(
        "--no-woff2",
        action="store_true",
        help="Skip WOFF2 emission during workspace builds.",
    )
    build_workspace_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the build report as JSON.",
    )

    return parser


def normalize_argv(argv: list[str] | None) -> list[str]:
    normalized = list(sys.argv[1:] if argv is None else argv)
    if not normalized:
        return normalized
    first = normalized[0]
    if first in SUBCOMMANDS or first.startswith("-"):
        return normalized
    return ["generate", *normalized]


def print_report(report: dict[str, object], as_json: bool) -> int:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    for key, value in report.items():
        label = key.replace("_", " ").capitalize()
        print(f"{label}: {value}")
    return 0


def handle_generate(args: argparse.Namespace) -> int:
    options = GenerationOptions(
        input_path=args.input,
        output_path=args.output,
        target_width=args.target_width,
        width_mode=args.width_mode,
        percentile=args.percentile,
        outline_mode=args.outline_mode,
        normalization_strength=args.normalization_strength,
        fill_ratio=args.fill_ratio,
        family_suffix=args.family_suffix,
        keep_hinting=args.keep_hinting,
    )
    report = generate_monospace_font(options)
    return print_report(report, args.json)


def handle_init_workspace(args: argparse.Namespace) -> int:
    report = init_workspace(
        WorkspaceInitOptions(
            input_path=args.input,
            workspace_path=args.workspace,
            family_suffix=args.family_suffix,
        )
    )
    return print_report(report, args.json)


def handle_build_workspace(args: argparse.Namespace) -> int:
    report = build_workspace(
        WorkspaceBuildOptions(
            workspace_path=args.workspace,
            output_dir=args.output_dir,
            keep_hinting=args.keep_hinting,
            emit_woff2=not args.no_woff2,
        )
    )
    return print_report(report, args.json)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))

    if args.command is None:
        parser.print_help()
        return 1

    try:
        if args.command == "generate":
            return handle_generate(args)
        if args.command == "init-workspace":
            return handle_init_workspace(args)
        if args.command == "build-workspace":
            return handle_build_workspace(args)
        parser.error(f"unknown command: {args.command}")
    except MonospaceGenerationError as error:
        print(f"monospace-pretext-font: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
