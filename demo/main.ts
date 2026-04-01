import { monospaceElement, type MonospaceController, type MonospaceMode } from '../src/index'

const style = document.createElement('style')
style.textContent = `
  :root {
    --bg: #f4efe4;
    --ink: #151515;
    --muted: rgba(21, 21, 21, 0.62);
    --card: rgba(255, 252, 247, 0.84);
    --line: rgba(21, 21, 21, 0.12);
    --accent: #c85c35;
    --accent-2: #214634;
    --shadow: 0 24px 60px rgba(63, 39, 18, 0.12);
  }

  * {
    box-sizing: border-box;
  }

  html {
    min-height: 100%;
    background:
      radial-gradient(circle at top left, rgba(200, 92, 53, 0.12), transparent 34%),
      radial-gradient(circle at bottom right, rgba(33, 70, 52, 0.14), transparent 28%),
      linear-gradient(180deg, #fbf6eb, #efe6d5);
  }

  body {
    margin: 0;
    color: var(--ink);
    font-family: "IBM Plex Sans", sans-serif;
  }

  button,
  textarea {
    font: inherit;
  }

  .page-shell {
    width: min(1180px, calc(100vw - 40px));
    margin: 0 auto;
    padding: 32px 0 48px;
  }

  .hero {
    padding: 28px;
    border: 1px solid var(--line);
    border-radius: 28px;
    background: linear-gradient(135deg, rgba(255, 250, 242, 0.88), rgba(248, 239, 221, 0.72));
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .eyebrow,
  .section-label,
  .specimen-name {
    margin: 0;
    font-size: 12px;
    line-height: 1.2;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
  }

  .display {
    margin: 14px 0 0;
    max-width: 14ch;
    font-family: "Archivo Black", sans-serif;
    font-size: clamp(42px, 8vw, 82px);
    line-height: 0.96;
    font-weight: 400;
  }

  .lede {
    margin: 18px 0 0;
    max-width: 62ch;
    font-size: 18px;
    line-height: 1.6;
    color: var(--muted);
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 22px;
  }

  .mode-note {
    margin: 14px 0 0;
    max-width: 72ch;
    font-size: 14px;
    line-height: 1.5;
    color: var(--muted);
  }

  .controls button {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 11px 16px;
    background: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    transition: transform 160ms ease, background 160ms ease;
  }

  .controls button:hover {
    transform: translateY(-1px);
    background: rgba(255, 255, 255, 0.8);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 18px;
    margin-top: 20px;
  }

  .card {
    border: 1px solid var(--line);
    border-radius: 24px;
    background: var(--card);
    box-shadow: var(--shadow);
    padding: 24px;
    backdrop-filter: blur(10px);
  }

  .article-card {
    grid-column: span 6;
  }

  .lab-card {
    grid-column: span 6;
  }

  .specimen-card {
    grid-column: span 12;
  }

  .article-title {
    margin: 18px 0 0;
    font-family: "Merriweather", serif;
    font-size: clamp(28px, 4vw, 44px);
    line-height: 1.12;
    font-weight: 700;
  }

  .article-copy,
  .editable-preview,
  .editor-label {
    margin: 18px 0 0;
    font-size: 17px;
    line-height: 1.7;
    color: var(--muted);
  }

  .quote {
    margin: 26px 0 0;
    padding-left: 18px;
    border-left: 3px solid rgba(200, 92, 53, 0.5);
    font-family: "Merriweather", serif;
    font-size: 26px;
    line-height: 1.32;
  }

  textarea {
    width: 100%;
    min-height: 140px;
    margin-top: 16px;
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 16px;
    resize: vertical;
    background: rgba(255, 255, 255, 0.72);
  }

  .editable-preview {
    padding: 22px 24px;
    border-radius: 18px;
    background: rgba(33, 70, 52, 0.06);
    color: var(--accent-2);
    font-family: "IBM Plex Sans", sans-serif;
    font-size: 19px;
    line-height: 1.35;
    font-weight: 500;
  }

  .editable-preview [data-pretext-monospace-wrapper] {
    display: inline-flex !important;
    flex-wrap: wrap;
    gap: 1px 0;
  }

  .editable-preview [data-pretext-monospace-cell] {
    box-shadow: inset 0 0 0 1px rgba(33, 70, 52, 0.08);
    background: rgba(255, 255, 255, 0.42);
    border-radius: 4px;
  }

  .specimen-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
    margin-top: 16px;
  }

  .specimen {
    padding: 20px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.58);
    border: 1px solid rgba(21, 21, 21, 0.08);
  }

  .specimen-line {
    margin: 12px 0 0;
  }

  .specimen-display {
    font-family: "Archivo Black", sans-serif;
    font-size: clamp(24px, 3vw, 38px);
    line-height: 1.06;
  }

  .specimen-serif {
    font-family: "Merriweather", serif;
    font-size: 20px;
    line-height: 1.34;
    font-style: italic;
  }

  .specimen-sans {
    font-family: "IBM Plex Sans", sans-serif;
    font-size: 22px;
    line-height: 1.35;
    font-weight: 300;
  }

  @media (max-width: 900px) {
    .article-card,
    .lab-card,
    .specimen-card {
      grid-column: span 12;
    }

    .specimen-grid {
      grid-template-columns: 1fr;
    }
  }
`
document.head.appendChild(style)

const textarea = document.getElementById('demo-input')
const preview = document.getElementById('editable-preview')
const toggleButton = document.getElementById('toggle-effect')
const modeButton = document.getElementById('toggle-mode')
const refreshButton = document.getElementById('refresh-effect')
const modeNote = document.getElementById('mode-note')

if (!(textarea instanceof HTMLTextAreaElement)) {
  throw new Error('#demo-input not found')
}

if (!(preview instanceof HTMLElement)) {
  throw new Error('#editable-preview not found')
}

if (!(toggleButton instanceof HTMLButtonElement)) {
  throw new Error('#toggle-effect not found')
}

if (!(modeButton instanceof HTMLButtonElement)) {
  throw new Error('#toggle-mode not found')
}

if (!(refreshButton instanceof HTMLButtonElement)) {
  throw new Error('#refresh-effect not found')
}

if (!(modeNote instanceof HTMLElement)) {
  throw new Error('#mode-note not found')
}

let controllers: MonospaceController[] = []
let enabled = true
let currentMode: MonospaceMode = 'optical'

async function applyEffect(): Promise<void> {
  restoreControllers()
  const targets = Array.from(document.querySelectorAll('[data-demo-target]'))
  controllers = await Promise.all(
    targets.map((target) =>
      monospaceElement(target, {
        observe: true,
        mode: currentMode,
      }),
    ),
  )
}

function restoreControllers(): void {
  for (const controller of controllers) {
    controller.disconnect()
    controller.restore()
  }
  controllers = []
}

function syncModeUI(): void {
  modeButton.textContent =
    currentMode === 'optical' ? 'Switch to strict mode' : 'Switch to optical mode'
  modeNote.textContent =
    currentMode === 'optical'
      ? 'Optical mode uses softer cell widths, centers glyphs in each cell, and trims spaces so paragraphs stay readable.'
      : 'Strict mode forces one fixed advance width per grapheme cell. It is more literal and usually looks harsher in body copy.'
}

textarea.addEventListener('input', () => {
  preview.textContent = textarea.value
})

toggleButton.addEventListener('click', async () => {
  enabled = !enabled

  if (enabled) {
    await applyEffect()
    toggleButton.textContent = 'Disable effect'
    return
  }

  restoreControllers()
  toggleButton.textContent = 'Enable effect'
})

modeButton.addEventListener('click', async () => {
  currentMode = currentMode === 'optical' ? 'strict' : 'optical'
  syncModeUI()

  if (enabled) {
    await applyEffect()
  }
})

refreshButton.addEventListener('click', async () => {
  if (!enabled) {
    return
  }
  await Promise.all(controllers.map((controller) => controller.refresh()))
})

syncModeUI()
await applyEffect()
