import { prepareWithSegments } from '@chenglou/pretext'

const WRAPPER_ATTR = 'data-pretext-monospace-wrapper'
const CELL_ATTR = 'data-pretext-monospace-cell'
const DEFAULT_IGNORE_SELECTOR = [
  'script',
  'style',
  'noscript',
  'textarea',
  'input',
  'select',
  'option',
  'canvas',
  'svg',
  'math',
  'iframe',
  '[data-pretext-monospace-ignore]',
  `[${WRAPPER_ATTR}]`,
].join(', ')

export const DEFAULT_SAMPLE_TEXT =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=[]{}|;:\'",.<>/?~ '

export type GraphemeMeasurer = (grapheme: string, font: string) => number

export type MonospaceOptions = {
  root?: Document | Element | DocumentFragment | ShadowRoot
  ignoreSelector?: string
  observe?: boolean
  waitForFonts?: boolean
  sampleText?: string
  measureGrapheme?: GraphemeMeasurer
  segmenter?: Intl.Segmenter
}

export type MonospaceController = {
  refresh: () => Promise<void>
  restore: () => void
  observe: () => void
  disconnect: () => void
}

type WhiteSpaceMode =
  | 'normal'
  | 'nowrap'
  | 'pre'
  | 'pre-wrap'
  | 'pre-line'
  | 'break-spaces'

type ResolvedOptions = {
  ignoreSelector: string
  observe: boolean
  waitForFonts: boolean
  sampleText: string
  measureGrapheme: GraphemeMeasurer
  segmenter: Intl.Segmenter | undefined
}

type Replacement = {
  textNode: Text
  wrapper: HTMLSpanElement
}

type FontMetrics = {
  cellWidth: number
  sampleReady: boolean
  graphemeWidths: Map<string, number>
}

type ControllerState = {
  document: Document
  root: ParentNode & Node
  options: ResolvedOptions
  replacements: Replacement[]
  fontMetrics: Map<string, FontMetrics>
  observer: MutationObserver | null
  observing: boolean
  queuedRefresh: boolean
}

export async function monospacePage(
  options: Omit<MonospaceOptions, 'root'> = {},
): Promise<MonospaceController> {
  assertBrowser()
  const root = document.body ?? document.documentElement
  return createController(root, { ...options, root })
}

export async function monospaceElement(
  element: Element,
  options: Omit<MonospaceOptions, 'root'> = {},
): Promise<MonospaceController> {
  return createController(element, { ...options, root: element })
}

export function createPretextMeasurer(): GraphemeMeasurer {
  const widthCache = new Map<string, number>()

  return (grapheme, font) => {
    const whiteSpace = needsVisibleWhiteSpaceMeasurement(grapheme)
      ? { whiteSpace: 'pre-wrap' as const }
      : undefined
    const cacheKey = `${font}\u0000${whiteSpace?.whiteSpace ?? 'normal'}\u0000${grapheme}`
    const cached = widthCache.get(cacheKey)

    if (cached !== undefined) {
      return cached
    }

    const prepared = prepareWithSegments(grapheme, font, whiteSpace)
    const width = prepared.widths[0] ?? 0
    widthCache.set(cacheKey, width)
    return width
  }
}

async function createController(
  rawRoot: MonospaceOptions['root'],
  options: MonospaceOptions,
): Promise<MonospaceController> {
  const { document: ownerDocument, root } = resolveRoot(rawRoot)
  const state: ControllerState = {
    document: ownerDocument,
    root,
    options: {
      ignoreSelector: options.ignoreSelector ?? DEFAULT_IGNORE_SELECTOR,
      observe: options.observe ?? false,
      waitForFonts: options.waitForFonts ?? true,
      sampleText: options.sampleText ?? DEFAULT_SAMPLE_TEXT,
      measureGrapheme: options.measureGrapheme ?? createPretextMeasurer(),
      segmenter: options.segmenter ?? createSegmenter(),
    },
    replacements: [],
    fontMetrics: new Map(),
    observer: null,
    observing: false,
    queuedRefresh: false,
  }

  const controller: MonospaceController = {
    refresh: () => refresh(state),
    restore: () => restore(state),
    observe: () => {
      startObserving(state)
    },
    disconnect: () => {
      stopObserving(state)
    },
  }

  await controller.refresh()

  if (state.options.observe) {
    controller.observe()
  }

  return controller
}

async function refresh(state: ControllerState): Promise<void> {
  const resumeObservation = state.observing
  stopObserving(state)

  restore(state)

  if (state.options.waitForFonts) {
    await waitForFonts(state.document)
  }

  for (const textNode of collectTextNodes(state)) {
    applyToTextNode(state, textNode)
  }

  if (resumeObservation) {
    startObserving(state)
  }
}

function restore(state: ControllerState): void {
  for (let index = state.replacements.length - 1; index >= 0; index -= 1) {
    const replacement = state.replacements[index]
    replacement?.wrapper.replaceWith(replacement.textNode)
  }
  state.replacements = []
}

function startObserving(state: ControllerState): void {
  if (state.observer !== null) {
    observeRoot(state)
    state.observing = true
    return
  }

  state.observer = new MutationObserver(() => {
    queueRefresh(state)
  })
  observeRoot(state)
  state.observing = true
}

function stopObserving(state: ControllerState): void {
  state.observer?.disconnect()
  state.observing = false
}

function queueRefresh(state: ControllerState): void {
  if (state.queuedRefresh) {
    return
  }

  state.queuedRefresh = true
  queueMicrotask(async () => {
    state.queuedRefresh = false

    try {
      await refresh(state)
    } catch (error) {
      console.error('monospace-pretext failed to refresh after a DOM mutation.', error)
    }
  })
}

function observeRoot(state: ControllerState): void {
  if (state.observer === null) {
    return
  }

  state.observer.observe(state.root, {
    childList: true,
    subtree: true,
    characterData: true,
  })
}

function collectTextNodes(state: ControllerState): Text[] {
  const textNodes: Text[] = []
  const nodeFilter = state.document.defaultView?.NodeFilter

  if (nodeFilter === undefined) {
    return textNodes
  }

  const walker = state.document.createTreeWalker(state.root, nodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!(node instanceof Text)) {
        return nodeFilter.FILTER_SKIP
      }

      const parent = node.parentElement
      if (parent === null) {
        return nodeFilter.FILTER_SKIP
      }

      if (parent.isContentEditable) {
        return nodeFilter.FILTER_SKIP
      }

      if (parent.closest(state.options.ignoreSelector) !== null) {
        return nodeFilter.FILTER_SKIP
      }

      if (node.data.length === 0) {
        return nodeFilter.FILTER_SKIP
      }

      return nodeFilter.FILTER_ACCEPT
    },
  })

  let current = walker.nextNode()
  while (current !== null) {
    if (current instanceof Text) {
      textNodes.push(current)
    }
    current = walker.nextNode()
  }

  return textNodes
}

function applyToTextNode(state: ControllerState, textNode: Text): void {
  const parent = textNode.parentElement
  const view = state.document.defaultView

  if (parent === null || view === null) {
    return
  }

  const computedStyle = view.getComputedStyle(parent)
  if (computedStyle.display === 'none' || computedStyle.visibility === 'hidden') {
    return
  }

  const renderedText = normalizeTextForWhiteSpace(textNode.data, normalizeWhiteSpace(computedStyle.whiteSpace))
  if (renderedText.length === 0) {
    return
  }

  const graphemes = segmentText(renderedText, state.options.segmenter)
  if (graphemes.length === 0) {
    return
  }

  const font = toCanvasFont(computedStyle)
  if (font.length === 0) {
    return
  }

  const cellWidth = resolveCellWidth(state, font, graphemes)
  if (cellWidth <= 0) {
    return
  }

  const wrapper = renderWrapper(state, renderedText, graphemes, font, cellWidth)
  textNode.replaceWith(wrapper)
  state.replacements.push({ textNode, wrapper })
}

function renderWrapper(
  state: ControllerState,
  renderedText: string,
  graphemes: string[],
  font: string,
  cellWidth: number,
): HTMLSpanElement {
  const wrapper = state.document.createElement('span')
  wrapper.setAttribute(WRAPPER_ATTR, '')
  wrapper.setAttribute('role', 'text')
  wrapper.setAttribute('aria-label', renderedText)
  wrapper.style.display = 'inline'
  wrapper.style.font = 'inherit'
  wrapper.style.lineHeight = 'inherit'
  wrapper.style.letterSpacing = '0'
  wrapper.style.wordSpacing = '0'
  wrapper.style.textTransform = 'inherit'
  wrapper.style.color = 'inherit'
  wrapper.style.textDecoration = 'inherit'
  wrapper.style.unicodeBidi = 'isolate'

  for (const grapheme of graphemes) {
    if (grapheme === '\n') {
      wrapper.appendChild(state.document.createElement('br'))
      continue
    }

    const cell = state.document.createElement('span')
    const width = grapheme === '\t' ? Math.max(cellWidth, getGraphemeWidth(state, font, grapheme)) : cellWidth

    cell.setAttribute(CELL_ATTR, '')
    cell.setAttribute('aria-hidden', 'true')
    cell.textContent = grapheme
    cell.style.display = 'inline-block'
    cell.style.width = formatPx(width)
    cell.style.minWidth = formatPx(width)
    cell.style.whiteSpace = 'pre'
    cell.style.font = 'inherit'
    cell.style.lineHeight = 'inherit'
    cell.style.verticalAlign = 'baseline'

    wrapper.appendChild(cell)
  }

  return wrapper
}

function resolveCellWidth(state: ControllerState, font: string, graphemes: string[]): number {
  const metrics = getFontMetrics(state, font)
  ensureFontSampleMeasured(state, font, metrics)

  for (const grapheme of graphemes) {
    if (grapheme === '\n') {
      continue
    }

    const width = getGraphemeWidth(state, font, grapheme)
    if (width > metrics.cellWidth) {
      metrics.cellWidth = width
    }
  }

  return metrics.cellWidth
}

function ensureFontSampleMeasured(
  state: ControllerState,
  font: string,
  metrics: FontMetrics,
): void {
  if (metrics.sampleReady) {
    return
  }

  for (const grapheme of segmentText(state.options.sampleText, state.options.segmenter)) {
    if (grapheme === '\n') {
      continue
    }

    const width = getGraphemeWidth(state, font, grapheme)
    if (width > metrics.cellWidth) {
      metrics.cellWidth = width
    }
  }

  metrics.sampleReady = true
}

function getFontMetrics(state: ControllerState, font: string): FontMetrics {
  const cached = state.fontMetrics.get(font)
  if (cached !== undefined) {
    return cached
  }

  const metrics: FontMetrics = {
    cellWidth: 0,
    sampleReady: false,
    graphemeWidths: new Map(),
  }
  state.fontMetrics.set(font, metrics)
  return metrics
}

function getGraphemeWidth(state: ControllerState, font: string, grapheme: string): number {
  const metrics = getFontMetrics(state, font)
  const cached = metrics.graphemeWidths.get(grapheme)

  if (cached !== undefined) {
    return cached
  }

  const width = Math.max(0, state.options.measureGrapheme(grapheme, font))
  metrics.graphemeWidths.set(grapheme, width)
  return width
}

function resolveRoot(rawRoot: MonospaceOptions['root']): {
  document: Document
  root: ParentNode & Node
} {
  if (rawRoot === undefined) {
    assertBrowser()
    return { document, root: document.body ?? document.documentElement }
  }

  if (rawRoot instanceof Document) {
    return { document: rawRoot, root: rawRoot.body ?? rawRoot.documentElement }
  }

  if (rawRoot instanceof ShadowRoot) {
    return { document: rawRoot.ownerDocument, root: rawRoot }
  }

  return { document: rawRoot.ownerDocument, root: rawRoot }
}

function normalizeTextForWhiteSpace(text: string, whiteSpace: WhiteSpaceMode): string {
  const normalizedLineBreaks = text.replace(/\r\n?/g, '\n')

  switch (whiteSpace) {
    case 'pre':
    case 'pre-wrap':
    case 'break-spaces':
      return normalizedLineBreaks
    case 'pre-line':
      return normalizedLineBreaks
        .replace(/[ \t\f\v]+/g, ' ')
        .replace(/ *\n */g, '\n')
    case 'normal':
    case 'nowrap':
    default:
      return normalizedLineBreaks.replace(/[ \t\f\v\n]+/g, ' ')
  }
}

function normalizeWhiteSpace(value: string): WhiteSpaceMode {
  switch (value) {
    case 'pre':
    case 'pre-wrap':
    case 'pre-line':
    case 'nowrap':
    case 'break-spaces':
      return value
    default:
      return 'normal'
  }
}

function toCanvasFont(style: CSSStyleDeclaration): string {
  const fontStyle = style.fontStyle || 'normal'
  const fontVariantCaps = style.fontVariantCaps || 'normal'
  const fontWeight = style.fontWeight || '400'
  const fontStretch = style.fontStretch || 'normal'
  const fontSize = style.fontSize || '16px'
  const fontFamily = style.fontFamily || 'sans-serif'

  const parts = [
    fontStyle,
    fontVariantCaps,
    fontWeight,
    fontStretch,
    fontSize,
    fontFamily,
  ].filter((part) => part.length > 0 && part !== 'normal')

  return parts.join(' ').trim()
}

function segmentText(text: string, segmenter: Intl.Segmenter | undefined): string[] {
  if (text.length === 0) {
    return []
  }

  if (segmenter === undefined) {
    return Array.from(text)
  }

  return Array.from(segmenter.segment(text), (entry) => entry.segment)
}

function formatPx(value: number): string {
  return `${value.toFixed(3)}px`
}

function needsVisibleWhiteSpaceMeasurement(grapheme: string): boolean {
  return /^[\s\u0009\u000a\u000d]+$/u.test(grapheme)
}

function createSegmenter(): Intl.Segmenter | undefined {
  if (typeof Intl === 'undefined' || typeof Intl.Segmenter === 'undefined') {
    return undefined
  }

  return new Intl.Segmenter(undefined, { granularity: 'grapheme' })
}

async function waitForFonts(ownerDocument: Document): Promise<void> {
  const fontSet = ownerDocument.fonts
  if (fontSet === undefined) {
    return
  }

  try {
    await fontSet.ready
  } catch {
    // Ignore font loading errors and continue with the current font state.
  }
}

function assertBrowser(): void {
  if (typeof document === 'undefined') {
    throw new Error('monospace-pretext can only run in a browser environment.')
  }
}
