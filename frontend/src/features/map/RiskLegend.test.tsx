import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RiskLegend } from './RiskLegend'

describe('RiskLegend', () => {
  it('names every risk level so colour is never the only cue', () => {
    render(<RiskLegend />)
    const legend = screen.getByRole('region', { name: 'Risk levels' })
    const items = within(legend)
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(items).toEqual(['Low', 'Moderate', 'High', 'Severe', 'No Travel', 'Unknown'])
  })
})
