# monospace-pretext

`monospace-pretext` now has two layers:

- a browser preview effect built on [`@chenglou/pretext`](https://www.npmjs.com/package/@chenglou/pretext)
- a real font-production pipeline built on Python `fontTools`, `ufoLib2`, and `ufo2ft`

The browser effect is useful for experiments. The serious path is the UFO-first workspace flow because it produces actual font files, policy files, and a proof page that loads the generated font directly.

## Install

```sh
npm install monospace-pretext
pip install -r python/requirements.txt
```

## UFO-First Workspace

Initialize a workspace from a source TTF:

```sh
npx monospace-pretext-font init-workspace ./MyFont.ttf
```

Equivalent local repo command:

```sh
npm run font:init-workspace -- ./MyFont.ttf
```

That creates:

- `project.yaml`
- `sources/original.ttf`
- `sources/<font-name>-source.ufo`
- `policies/glyph-classes.yaml`
- `policies/rules.yaml`
- `policies/overrides.yaml`
- empty `build/` and `proof/` directories

Build the workspace:

```sh
npx monospace-pretext-font build-workspace ./MyFont-workspace
```

Equivalent local repo command:

```sh
npm run font:build-workspace -- ./MyFont-workspace
```

That emits:

- `build/<font-name>-mono.ufo`
- `build/<font-name>-mono.ttf`
- `build/<font-name>-mono.woff2`
- `proof/index.html`

The proof page loads the actual generated font file, not the DOM preview effect.

Useful workspace flags:

- `init-workspace --workspace ./custom-dir`
- `init-workspace --family-suffix Mono`
- `build-workspace --output-dir ./artifacts`
- `build-workspace --keep-hinting`
- `build-workspace --no-woff2`

## Direct Font Generator

The older direct generator still exists for quick drafts:

```sh
npx monospace-pretext-font ./MyFont.ttf --output ./MyFontMono.ttf
```

Equivalent local repo command:

```sh
npm run font:generate -- ./MyFont.ttf --output ./MyFontMono.ttf
```

Useful options:

```sh
npx monospace-pretext-font ./MyFont.ttf \
  --width-mode percentile \
  --percentile 0.9 \
  --outline-mode normalize \
  --normalization-strength 0.75 \
  --fill-ratio 0.82
```

CLI flags:

- `--target-width`: explicit shared advance width in font units.
- `--width-mode`: `max`, `average`, `median`, or `percentile`.
- `--outline-mode`: `preserve`, `fit`, or `normalize`.
- `--normalization-strength`: how hard `normalize` pulls outlines toward the target width.
- `--fill-ratio`: how much of the advance width the outline should occupy after normalization.
- `--family-suffix`: suffix appended to the generated family name.

## Policy Files

`policies/glyph-classes.yaml` groups glyphs into classes such as `uppercase`, `lowercase`, `digits`, `punctuation`, `symbols`, `whitespace`, and `marks`.

`policies/rules.yaml` controls class-level behavior:

- target width mode
- percentile
- outline mode
- normalization strength
- fill ratio
- skip flags
- per-class overrides

`policies/overrides.yaml` is for per-glyph exceptions such as spacing glyphs and punctuation.

The intended loop is:

1. Initialize a workspace.
2. Edit `policies/rules.yaml` and `policies/overrides.yaml`.
3. Rebuild the workspace.
4. Open `proof/index.html` and evaluate the generated font.

## Browser Preview

```ts
import { monospacePage } from 'monospace-pretext'

await monospacePage({
  observe: true,
})
```

Or scope it to one element:

```ts
import { monospaceElement } from 'monospace-pretext'

const hero = document.querySelector('.hero-copy')
if (hero instanceof HTMLElement) {
  await monospaceElement(hero)
}
```

## API

### `monospacePage(options?)`

Processes `document.body` and returns a controller:

```ts
type MonospaceController = {
  refresh(): Promise<void>
  restore(): void
  observe(): void
  disconnect(): void
}
```

### `monospaceElement(element, options?)`

Processes a specific subtree and returns the same controller.

### `createPretextMeasurer()`

Returns the default grapheme width measurer backed by `@chenglou/pretext`.

## Browser Options

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

- `ignoreSelector`: skips `script`, `style`, form controls, canvas/svg, and elements marked with `data-pretext-monospace-ignore`.
- `observe`: when `true`, a `MutationObserver` re-runs the effect after DOM changes.
- `waitForFonts`: waits for `document.fonts.ready` before measuring. Default is `true`.
- `sampleText`: seed glyph set used to establish a consistent cell width per font.
- `mode`: `optical` by default. `optical` recenters glyphs, uses a softer cell width, and narrows spaces. `strict` forces one hard width for every grapheme cell.
- `cellWidthPercentile`: controls how aggressive optical mode is. Lower values reduce spacing further. Default is `0.72`.
- `spaceScale`: optical-mode space width as a fraction of the base cell width. Default is `0.55`.
- `measureGrapheme`: overrides the measurement function. The default uses Pretext.

## Support Boundary

- Workspace and direct generation currently support `glyf`-based TrueType/OpenType fonts.
- Zero-width combining marks are preserved.
- Hinting is dropped by default after outline edits.
- CFF/CFF2 source fonts are not yet supported.
- The generated fonts are drafts. They are structurally real fonts, but not a substitute for hand-drawn professional monospace design.
- The browser mode is still a DOM rewrite effect. It is useful for previews, not the final font output.

## Development

```sh
npm install
pip install -r python/requirements.txt
npm run demo
npm run check
```
