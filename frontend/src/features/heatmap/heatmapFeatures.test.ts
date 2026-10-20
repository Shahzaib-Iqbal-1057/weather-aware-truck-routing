import { describe, expect, it } from 'vitest'
import type { HeatmapResponse } from '../../api/types'
import { hasWeatherAt, heatmapFeatures } from './heatmapFeatures'

const HEATMAP: HeatmapResponse = {
  start_utc: '2026-10-21T15:00:00Z',
  hours: 3,
  cell_size_deg: 0.5,
  cells_in_corridor: 10,
  cells: [{ center: [-111.25, 35.25], levels: '02-' }],
}

describe('heatmapFeatures', () => {
  it('turns each cell into a square around its center', () => {
    const [cell] = heatmapFeatures(HEATMAP).features
    expect(cell.geometry.coordinates[0]).toEqual([
      [-111.5, 35],
      [-111, 35],
      [-111, 35.5],
      [-111.5, 35.5],
      [-111.5, 35],
    ])
  })

  it('stores every hour as a number property, -1 for no forecast', () => {
    const [cell] = heatmapFeatures(HEATMAP).features
    expect(cell.properties).toEqual({ h0: 0, h1: 2, h2: -1 })
  })

  it('is empty without data', () => {
    expect(heatmapFeatures(undefined).features).toEqual([])
  })
})

describe('hasWeatherAt', () => {
  it('is true only for hours where some cell is Moderate or worse', () => {
    expect(hasWeatherAt(HEATMAP, 0)).toBe(false)
    expect(hasWeatherAt(HEATMAP, 1)).toBe(true)
    expect(hasWeatherAt(HEATMAP, 2)).toBe(false)
  })
})
