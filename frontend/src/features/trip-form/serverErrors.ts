import type { ValidationErrorBody } from '../../api/types'
import type { TripFormErrors, TripFormField } from './validation'

const API_TO_FORM_FIELD: Record<string, TripFormField> = {
  origin: 'origin',
  destination: 'destination',
  departure_local: 'departureLocal',
  weight_lb: 'weightLb',
}

/** Map a DRF 400 body onto form fields. Anything unrecognised goes into `general`. */
export function toFormErrors(body: unknown): { fields: TripFormErrors; general: string | null } {
  const fields: TripFormErrors = {}
  const general: string[] = []
  if (body && typeof body === 'object') {
    for (const [key, value] of Object.entries(body as ValidationErrorBody)) {
      const message = Array.isArray(value) ? value[0] : 'This location is not valid.'
      const field = API_TO_FORM_FIELD[key]
      if (field) fields[field] = message
      else general.push(message)
    }
  }
  return { fields, general: general.length ? general.join(' ') : null }
}
