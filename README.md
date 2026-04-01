# monospace-pretext

`monospace-pretext` is a repo for turning proportional typography into monospace-like typography in two different ways:

- a browser-side preview effect powered by [`@chenglou/pretext`](https://www.npmjs.com/package/@chenglou/pretext)
- a real font-generation pipeline powered by Python `fontTools`, `ufoLib2`, and `ufo2ft`

Those two parts solve different problems.

- The browser package is for fast visual experiments. It keeps the original font family and rewrites page text into equal-width grapheme cells.
- The Python pipeline is for producing actual font files. It rewrites glyph metrics and outlines, then emits generated fonts and proof artifacts.

If you want a strange, live browser effect, use the JS API. If you want a real font file, use the CLI.

## What This Repo Does

### 1. Browser Preview Layer

The JS package exports:

- `monospacePage()`
- `monospaceElement()`
- `createPretextMeasurer()`

It uses Pretext to measure rendered grapheme widths in the active font, then wraps text nodes in fixed-width cells so a proportional font behaves like a fake monospace font inside the browser.

This is not font engineering. It is a DOM transformation.

### 2. Direct Font Generator

The Python CLI can generate a draft monospaced font directly from a source `glyf`-based TTF/OTF.

It:

- opens the source font with `fontTools`
- derives a target advance width
- horizontally transforms outlines
- rewrites `hmtx` metrics
- updates fixed-pitch metadata
- writes a new font file

This is useful for quick one-shot drafts.

### 3. UFO-First Workspace Pipeline

The more serious path is the workspace flow.

It:

- initializes a workspace from a source font
- exports a source UFO
- derives glyph classes
- writes editable policy files
- rebuilds a generated UFO and compiled font from those policies
- emits a proof page that loads the generated font directly

This is the repo’s current “production” path.

## How It Works

### Browser Effect

The browser effect in [src/index.ts](/Users/charlie/Razroo/monospace-pretext/src/index.ts) works like this:

1. Wait for fonts to load.
2. Walk text nodes under a root element.
3. Split text into graphemes.
4. Measure each grapheme width with Pretext.
5. Choose a cell width for the current font.
6. Replace the original text node with wrapper and cell spans.
7. Optionally observe mutations and reapply the effect.

There are two layout modes:

- `strict`: force one hard cell width for every grapheme
- `optical`: use softer cell sizing, center glyphs, and narrow spaces so text stays more readable

### Direct Font Generation

The direct generator in [monospace_font_tools.py](/Users/charlie/Razroo/monospace-pretext/python/monospace_font_tools.py) works like this:

1. Load a source font with `TTFont`.
2. Collect spacing glyphs and their widths.
3. Resolve a shared target width with `max`, `average`, `median`, or `percentile`.
4. Measure glyph bounds.
5. Transform outlines horizontally with `preserve`, `fit`, or `normalize`.
6. Rewrite horizontal metrics and metadata.
7. Save the generated font.

### Workspace Pipeline

The workspace system in [workspace_tools.py](/Users/charlie/Razroo/monospace-pretext/python/workspace_tools.py) adds iteration and policy control:

1. `init-workspace` copies the original font into a workspace.
2. It exports a source UFO.
3. It classifies glyphs into groups like `uppercase`, `lowercase`, `digits`, `punctuation`, `symbols`, `whitespace`, and `marks`.
4. It writes `rules.yaml` and `overrides.yaml` so widths and outline behavior can be tuned by class or by glyph.
5. `build-workspace` applies those policies to the UFO.
6. It compiles a TTF with `ufo2ft`, optionally emits WOFF2, and writes a proof HTML page.

The proof page loads the actual generated font file, not the browser DOM effect.

## Install

For the browser package:

```sh
npm install monospace-pretext
```

For the font pipeline:

```sh
pip install -r python/requirements.txt
```

## Quick Start

### Browser API

```ts
import { monospacePage } from 'monospace-pretext'

await monospacePage({
  observe: true,
  mode: 'optical',
})
```

Or scope it to one subtree:

```ts
import { monospaceElement } from 'monospace-pretext'

const hero = document.querySelector('.hero')
if (hero instanceof HTMLElement) {
  await monospaceElement(hero, { mode: 'optical' })
}
```

Run the demo:

```sh
npm install
npm run demo
```

Open the Vite URL it prints, usually `http://127.0.0.1:5173/`.

Build the static demo site:

```sh
npm run demo:build
npm run demo:preview
```

That writes the production demo to `site-dist/`.

### Direct Font Generator

```sh
npx monospace-pretext-font ./MyFont.ttf --output ./MyFontMono.ttf
```

Local repo command:

```sh
npm run font:generate -- ./MyFont.ttf --output ./MyFontMono.ttf
```

Example with explicit shaping controls:

```sh
npx monospace-pretext-font ./MyFont.ttf \
  --width-mode percentile \
  --percentile 0.9 \
  --outline-mode normalize \
  --normalization-strength 0.75 \
  --fill-ratio 0.82
```

### Workspace Flow

Initialize a workspace:

```sh
npx monospace-pretext-font init-workspace ./MyFont.ttf
```

Build it:

```sh
npx monospace-pretext-font build-workspace ./MyFont-workspace
```

Local repo commands:

```sh
npm run font:init-workspace -- ./MyFont.ttf
npm run font:build-workspace -- ./MyFont-workspace
```

That produces:

- `project.yaml`
- `sources/original.ttf`
- `sources/<font-name>-source.ufo`
- `policies/glyph-classes.yaml`
- `policies/rules.yaml`
- `policies/overrides.yaml`
- `build/<font-name>-mono.ufo`
- `build/<font-name>-mono.ttf`
- `build/<font-name>-mono.woff2`
- `proof/index.html`

## CLI Surface

The Node binary in [monospace-pretext-font.js](/Users/charlie/Razroo/monospace-pretext/bin/monospace-pretext-font.js) is a thin wrapper around the Python CLI in [cli.py](/Users/charlie/Razroo/monospace-pretext/python/cli.py).

Supported commands:

- `generate`
- `init-workspace`
- `build-workspace`

The direct `generate` form is backward-compatible, so this still works:

```sh
npx monospace-pretext-font ./MyFont.ttf --output ./MyFontMono.ttf
```

Useful direct-generator flags:

- `--target-width`
- `--width-mode max|average|median|percentile`
- `--percentile`
- `--outline-mode preserve|fit|normalize`
- `--normalization-strength`
- `--fill-ratio`
- `--family-suffix`
- `--keep-hinting`

Useful workspace flags:

- `init-workspace --workspace ./custom-dir`
- `init-workspace --family-suffix Mono`
- `build-workspace --output-dir ./artifacts`
- `build-workspace --keep-hinting`
- `build-workspace --no-woff2`

## Browser API

`monospacePage()` processes `document.body` and returns:

```ts
type MonospaceController = {
  refresh(): Promise<void>
  restore(): void
  observe(): void
  disconnect(): void
}
```

`monospaceElement()` processes a single subtree and returns the same controller.

`createPretextMeasurer()` returns the default grapheme-width measurer backed by Pretext.

Browser options:

```ts
type MonospaceOptions = {
  root?: Document | Element | DocumentFragment | ShadowRoot
  ignoreSelector?: string
  observe?: boolean
  waitForFonts?: boolean
  sampleText?: string
  mode?: 'strict' | 'optical'
  cellWidthPercentile?: number
  spaceScale?: number
  measureGrapheme?: (grapheme: string, font: string) => number
  segmenter?: Intl.Segmenter
}
```

- `ignoreSelector` skips nodes like `script`, `style`, form controls, canvas, svg, and anything marked with `data-pretext-monospace-ignore`
- `observe` reruns the effect after DOM mutations
- `waitForFonts` waits for `document.fonts.ready`
- `sampleText` seeds width measurement
- `mode` picks `strict` or `optical`
- `cellWidthPercentile` controls optical-mode aggressiveness
- `spaceScale` narrows spaces in optical mode
- `measureGrapheme` lets you replace the default Pretext-backed measurer

## Repo Layout

- [src/index.ts](/Users/charlie/Razroo/monospace-pretext/src/index.ts): browser effect implementation
- [demo/index.html](/Users/charlie/Razroo/monospace-pretext/demo/index.html): demo shell
- [demo/main.ts](/Users/charlie/Razroo/monospace-pretext/demo/main.ts): demo behavior and styling
- [vite.config.ts](/Users/charlie/Razroo/monospace-pretext/vite.config.ts): Vite config for local demo development and GitHub Pages production builds
- [deploy-pages.yml](/Users/charlie/Razroo/monospace-pretext/.github/workflows/deploy-pages.yml): GitHub Actions workflow that publishes the demo to GitHub Pages
- [python/monospace_font_tools.py](/Users/charlie/Razroo/monospace-pretext/python/monospace_font_tools.py): direct font generator
- [python/workspace_tools.py](/Users/charlie/Razroo/monospace-pretext/python/workspace_tools.py): workspace init/build pipeline
- [python/cli.py](/Users/charlie/Razroo/monospace-pretext/python/cli.py): CLI entrypoint
- [python_tests/test_generator.py](/Users/charlie/Razroo/monospace-pretext/python_tests/test_generator.py): direct-generator tests
- [python_tests/test_workspace.py](/Users/charlie/Razroo/monospace-pretext/python_tests/test_workspace.py): workspace tests

## GitHub Pages

The repo now includes a GitHub Actions workflow that deploys the demo site from `main` to GitHub Pages.

One-time setup:

1. Open GitHub repository settings.
2. Go to Pages.
3. Under Build and deployment, set Source to `GitHub Actions`.

After that, pushes to `main` will build the demo with `npm run demo:build` and publish `site-dist/`.

The Vite base path is derived from `GITHUB_REPOSITORY` in [vite.config.ts](/Users/charlie/Razroo/monospace-pretext/vite.config.ts), so project Pages deployments resolve assets under `/<repo-name>/`.

## Current Limits

- Font generation currently supports `glyf`-based TrueType/OpenType fonts.
- CFF/CFF2 source fonts are not supported yet.
- Zero-width combining marks are preserved, but complex script quality is not the focus yet.
- Hinting is dropped by default after outline edits because the original hints are usually invalidated.
- The browser effect is intentionally fake. It rewrites DOM text and discards kerning/ligatures.
- The generated fonts are drafts. They are real fonts, but not a substitute for hand-drawn professional monospace design.

## Development

```sh
npm install
pip install -r python/requirements.txt
npm run demo:build
npm run check
```
