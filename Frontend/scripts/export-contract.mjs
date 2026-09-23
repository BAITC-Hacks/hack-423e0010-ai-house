import { writeFile } from 'node:fs/promises'
import { z } from 'zod'
import { requestSchema, responseSchema } from '../src/domain/selection.ts'

for (const [name, schema] of [
  ['request', requestSchema],
  ['response', responseSchema],
]) {
  const json = z.toJSONSchema(schema, { target: 'draft-2020-12' })
  await writeFile(
    new URL(`../docs/${name}.schema.json`, import.meta.url),
    JSON.stringify(json, null, 2) + '\n',
  )
}
console.log('Exported request and response JSON Schemas.')
