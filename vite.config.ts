import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vite'

const repoRoot = dirname(fileURLToPath(import.meta.url))
const demoRoot = resolve(repoRoot, 'demo')
const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1]
const base =
  process.env.GITHUB_ACTIONS === 'true' && repoName ? `/${repoName}/` : '/'

export default defineConfig({
  root: demoRoot,
  base,
  server: {
    fs: {
      allow: [repoRoot],
    },
  },
  preview: {
    host: '127.0.0.1',
  },
  build: {
    outDir: resolve(repoRoot, 'site-dist'),
    emptyOutDir: true,
  },
})
