import type { Feature, FeatureCollection, Point } from 'geojson'
import type { HeatmapResponse } from '../../api/types'

/** Per-hour level as a number (`h0` … `h47`): 0 Low … 4 No Travel, -1 no forecast. */
export type CellProperties = Record<string, number>

/** One point per cell with every hour's level, so moving the slider only restyles them. */
export function heatmapFeatures(
  heatmap: HeatmapResponse | undefined,
): FeatureCollection<Point, CellProperties> {
  if (!heatmap) return { type: 'FeatureCollection', features: [] }
  return {
    type: 'FeatureCollection',
    features: heatmap.cells.map((cell): Feature<Point, CellProperties> => {
      const properties: CellProperties = {}
      for (let hour = 0; hour < cell.levels.length; hour++) {
        const code = cell.levels[hour]
        properties[`h${hour}`] = code === '-' ? -1 : Number(code)
      }
      return { type: 'Feature', properties, geometry: { type: 'Point', coordinates: cell.center } }
    }),
  }
}

// MapLibre's world is 512 px wide at zoom 0 and doubles with each zoom level.
const WORLD_PX_AT_ZOOM_0 = 512
const MAX_ZOOM = 22

/**
 * Circle radius (px) for each zoom, so a cell's soft disc reaches its neighbours' centres and
 * the discs blend into one smooth field instead of a grid of squares. Web Mercator stretches
 * latitude by 1/cos(lat), so the radius is sized for the cells' average latitude.
 */
export function cellRadiusStops(heatmap: HeatmapResponse | undefined): [number, number] {
  if (!heatmap?.cells.length) return [0, 0]
  const meanLat =
    heatmap.cells.reduce((sum, cell) => sum + cell.center[1], 0) / heatmap.cells.length
  const pxPerDegree = WORLD_PX_AT_ZOOM_0 / 360
  const atZoom0 = (heatmap.cell_size_deg * pxPerDegree) / Math.cos((meanLat * Math.PI) / 180)
  return [atZoom0, atZoom0 * 2 ** MAX_ZOOM]
}

export const CELL_RADIUS_MAX_ZOOM = MAX_ZOOM

/** True if any cell is Moderate or worse at `hour`. */
export function hasWeatherAt(heatmap: HeatmapResponse | undefined, hour: number): boolean {
  return Boolean(heatmap?.cells.some((cell) => '1234'.includes(cell.levels[hour] ?? '')))
}
