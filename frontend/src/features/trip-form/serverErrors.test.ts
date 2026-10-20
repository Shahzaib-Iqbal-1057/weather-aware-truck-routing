import { describe, expect, it } from 'vitest'
import { toFormErrors } from './serverErrors'

describe('toFormErrors', () => {
  it('maps API field names to form fields', () => {
    const result = toFormErrors({
      cargo_weight_lb: ['Cargo weight must be between 0 and 45,000 lb.'],
      departure_local: ['Departure time is in the past.'],
      origin: { lat: ['Ensure this value is less than or equal to 90.'] },
    })

    expect(result.fields).toEqual({
      cargoWeightLb: 'Cargo weight must be between 0 and 45,000 lb.',
      departureLocal: 'Departure time is in the past.',
      origin: 'This location is not valid.',
    })
    expect(result.general).toBeNull()
  })

  it('collects unknown errors as a general message', () => {
    expect(toFormErrors({ non_field_errors: ['Something went wrong.'] }).general).toBe(
      'Something went wrong.',
    )
  })
})
