import { z } from 'zod'
import { profileSchema } from '../domain/selection'
import sourceCatalog from './catalog.json'

// Imported verbatim fields from the provided anonymized CSV; see scripts/import_catalog.py.
export const demoCatalog = z
  .array(profileSchema.extend({ busy_dates: z.array(z.iso.date()) }))
  .parse(sourceCatalog)
