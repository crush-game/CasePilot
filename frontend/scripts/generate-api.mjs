import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import openapiTS, { astToString } from 'openapi-typescript'

const frontend = fileURLToPath(new URL('..', import.meta.url))
const root = resolve(frontend, '..')
const python = resolve(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const schema = execFileSync(python, [resolve(root, 'scripts/export_openapi.py'), '--stdout'], {
  cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' }, windowsHide: true,
})
const types = '/** Generated from the backend OpenAPI schema. Do not edit manually. */\n' + astToString(await openapiTS(JSON.parse(schema)))
for (const [path, value] of [[resolve(frontend, 'openapi.json'), schema], [resolve(frontend, 'src/types/openapi.ts'), types]]) {
  if (process.argv.includes('--check')) {
    if (readFileSync(path, 'utf8').replaceAll('\r\n', '\n') !== value.replaceAll('\r\n', '\n')) {
      throw new Error('API 契约已变化，请运行 npm run api:generate 并提交生成文件。')
    }
  } else writeFileSync(path, value, 'utf8')
}
console.log(process.argv.includes('--check') ? 'API 契约与生成类型一致。' : 'API 契约和类型已生成。')
