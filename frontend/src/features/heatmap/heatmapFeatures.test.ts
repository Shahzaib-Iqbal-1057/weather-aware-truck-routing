import { describe, expect, it } from 'vitest'
import type { HeatmapResponse } from '../../api/types'
import { cellLevelsAt, cellRadiusStops, hasWeatherAt, heatmapFeatures } from './heatmapFeatures'

const HEATMAP: HeatmapResponse = {
  start_utc: '2026-10-21T15:00:00Z',
  hours: 3,
  cell_size_deg: 0.5,
  cells_in_corridor: 10,
  cells: [{ center: [-111.25, 35.25], levels: '02-' }],
}

describe('heatmapFeatures', () => {
  it('puts one point at each cell center', () => {
    const [cell] = heatmapFeatures(HEATMAP).features
    expect(cell.geometry.coordinates).toEqual([-111.25, 35.25])
  })

  it("numbers the cells so the map can set each one's level", () => {
    expect(heatmapFeatures(HEATMAP).features.map((f) => f.id)).toEqual([0])
  })

  it('is empty without data', () => {
    expect(heatmapFeatures(undefined).features).toEqual([])
  })
})

describe('cellLevelsAt', () => {
  it("gives each cell's level at an hour as a number, -1 for no forecast", () => {
    expect([0, 1, 2].map((hour) => cellLevelsAt(HEATMAP, hour))).toEqual([[0], [2], [-1]])
  })
})

describe('cellRadiusStops', () => {
  it('is one cell tall on screen at zoom 0 and doubles with every zoom level', () => {
    const [atZoom0, atZoom22] = cellRadiusStops(HEATMAP)
    const cellHeightPx = (0.5 * 512) / 360 / Math.cos((35.25 * Math.PI) / 180)
    expect(atZoom0).toBeCloseTo(cellHeightPx)
    expect(atZoom22 / atZoom0).toBe(2 ** 22)
  })

  it('is zero without cells', () => {
    expect(cellRadiusStops(undefined)).toEqual([0, 0])
  })
})

describe('hasWeatherAt', () => {
  it('is true only for hours where some cell is Moderate or worse', () => {
    expect(hasWeatherAt(HEATMAP, 0)).toBe(false)
    expect(hasWeatherAt(HEATMAP, 1)).toBe(true)
    expect(hasWeatherAt(HEATMAP, 2)).toBe(false)
  })
})
