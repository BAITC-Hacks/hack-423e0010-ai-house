import { spawn } from 'node:child_process'

const commands = [
  ['node_modules/vite/bin/vite.js', ...process.argv.slice(2)],
  ['--env-file-if-exists=.env.server', '--import', 'tsx', 'server/index.ts'],
]
const children = commands.map((args) => spawn(process.execPath, args, { stdio: 'inherit' }))
let closing = false
function close(code = 0) {
  if (closing) return
  closing = true
  for (const child of children) child.kill('SIGTERM')
  process.exitCode = code
}
for (const child of children) {
  child.on('error', () => close(1))
  child.on('exit', (code) => { if (!closing) close(code || 0) })
}
process.on('SIGINT', () => close())
process.on('SIGTERM', () => close())
