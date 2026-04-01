#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pythonCli = resolve(here, '../python/cli.py')

if (!existsSync(pythonCli)) {
  console.error(`monospace-pretext-font: missing Python CLI at ${pythonCli}`)
  process.exit(1)
}

const python = process.env.PYTHON ?? process.env.PYTHON3 ?? 'python3'
const result = spawnSync(python, [pythonCli, ...process.argv.slice(2)], {
  stdio: 'inherit',
})

if (result.error) {
  console.error(`monospace-pretext-font: failed to run ${python}: ${result.error.message}`)
  process.exit(1)
}

process.exit(result.status ?? 1)
