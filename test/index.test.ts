import { afterEach, describe, expect, it } from 'vitest'

import { monospaceElement } from '../src/index.js'

describe('monospaceElement', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('wraps each grapheme in a fixed-width cell', async () => {
    const root = document.createElement('div')
    root.textContent = 'Wim'
    document.body.appendChild(root)

    await monospaceElement(root, {
      waitForFonts: false,
      measureGrapheme: (grapheme) => {
        if (grapheme === 'W') return 18
        if (grapheme === 'i') return 5
        return 12
      },
      sampleText: 'Wim',
    })

    const wrapper = root.querySelector('[data-pretext-monospace-wrapper]')
    expect(wrapper).not.toBeNull()

    const cells = Array.from(root.querySelectorAll('[data-pretext-monospace-cell]'))
    expect(cells).toHaveLength(3)
    expect(cells.map((cell) => (cell as HTMLElement).style.width)).toEqual([
      '18px',
      '18px',
      '18px',
    ])
  })

  it('collapses normal white-space before building cells', async () => {
    const root = document.createElement('div')
    root.style.whiteSpace = 'normal'
    root.textContent = 'A   B'
    document.body.appendChild(root)

    await monospaceElement(root, {
      waitForFonts: false,
      measureGrapheme: () => 10,
      sampleText: 'AB ',
    })

    const cells = Array.from(root.querySelectorAll('[data-pretext-monospace-cell]'))
    expect(cells).toHaveLength(3)
    expect(cells.map((cell) => cell.textContent)).toEqual(['A', ' ', 'B'])
  })

  it('restores the original text nodes', async () => {
    const root = document.createElement('div')
    root.textContent = 'Restore me'
    document.body.appendChild(root)

    const controller = await monospaceElement(root, {
      waitForFonts: false,
      measureGrapheme: () => 8,
      sampleText: 'Restore me',
    })

    expect(root.textContent).toBe('Restore me')
    expect(root.querySelector('[data-pretext-monospace-wrapper]')).not.toBeNull()

    controller.restore()

    expect(root.textContent).toBe('Restore me')
    expect(root.querySelector('[data-pretext-monospace-wrapper]')).toBeNull()
  })
})
