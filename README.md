# monospace-pretext

`monospace-pretext` rewrites page text into fixed-width grapheme cells while keeping the original font family. It uses [`@chenglou/pretext`](https://www.npmjs.com/package/@chenglou/pretext) to measure each grapheme width, then expands every grapheme in a font to the same advance width.

This is a browser-side DOM effect. It is best suited to experimental typography, landing pages, art directions, and one-off visual treatments.

## Install

```sh
npm install monospace-pretext
```

## Usage

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

Returns the default grapheme width measurer backed by `@chenglou/pretext`. This is mainly useful if you want to compose your own processing flow.

## Options

```ts
type MonospaceOptions = {
  root?: Document | Element | DocumentFragment | ShadowRoot
  ignoreSelector?: string
  observe?: boolean
  waitForFonts?: boolean
  sampleText?: string
  measureGrapheme?: (grapheme: string, font: string) => number
  segmenter?: Intl.Segmenter
}
```

- `ignoreSelector`: defaults to skipping `script`, `style`, form controls, canvas/svg, and any element marked with `data-pretext-monospace-ignore`.
- `observe`: when `true`, a `MutationObserver` re-runs the effect after DOM changes.
- `waitForFonts`: waits for `document.fonts.ready` before measuring. Default is `true`.
- `sampleText`: seed glyph set used to establish a consistent cell width per font.
- `measureGrapheme`: overrides the measurement function. The default uses Pretext.

## Caveats

- This rewrites text nodes into `<span>` cells. It is not a drop-in replacement for every production UI surface.
- Ligatures and kerning are intentionally lost because each grapheme is rendered in its own fixed-width cell.
- White-space collapsing is approximated for `normal`, `nowrap`, and `pre-line`. It is accurate enough for decorative text, not for exact browser text layout emulation.
- Form controls, canvas, SVG, and other non-text DOM surfaces are not transformed.

## Development

```sh
npm install
npm run demo
npm run check
```
