import { describe, expect, it } from 'vitest'
import { makeRoute } from '../../test/fixtures'
import { riskSummary } from './riskSummary'

describe('riskSummary', () => {
  it('lists Severe and High miles and the average', () => {
    const route = makeRoute({
      totals: {
        severe_mi: 9.6,
        high_mi: 20.2,
        no_travel_mi: 0,
        unknown_mi: 0,
        average_risk: 0.1234,
      },
    })
    expect(riskSummary(route)).toBe('10 Severe mi · 20 High mi · avg risk 0.12')
  })

  it('mentions miles without a forecast', () => {
    const route = makeRoute({
      totals: { severe_mi: 0, high_mi: 0, no_travel_mi: 0, unknown_mi: 12.4, average_risk: 0 },
    })
    expect(riskSummary(route)).toBe(
      '0 Severe mi · 0 High mi · avg risk 0.00 · 12 mi without forecast',
    )
  })

  it('says the risk is unknown without any forecast', () => {
    const route = makeRoute({
      totals: { severe_mi: 0, high_mi: 0, no_travel_mi: 0, unknown_mi: 400, average_risk: null },
    })
    expect(riskSummary(route)).toBe('Weather risk unknown')
  })
})
