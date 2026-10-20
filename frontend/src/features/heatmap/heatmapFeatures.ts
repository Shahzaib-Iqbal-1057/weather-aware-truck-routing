import type { Feature, FeatureCollection, Polygon } from 'geojson'
import type { HeatmapResponse } from '../../api/types'

/** Per-hour level as a number (`h0` … `h47`): 0 Low … 4 No Travel, -1 no forecast. */
export type CellProperties = Record<string, number>

/** Square cells with every hour's level, so moving the slider only restyles them. */
export function heatmapFeatures(
  heatmap: HeatmapResponse | undefined,
): FeatureCollection<Polygon, CellProperties> {
  if (!heatmap) return { type: 'FeatureCollection', features: [] }
  const half = heatmap.cell_size_deg / 2
  return {
    type: 'FeatureCollection',
    features: heatmap.cells.map((cell): Feature<Polygon, CellProperties> => {
      const [lon, lat] = cell.center
      const properties: CellProperties = {}
      for (let hour = 0; hour < cell.levels.length; hour++) {
        const code = cell.levels[hour]
        properties[`h${hour}`] = code === '-' ? -1 : Number(code)
      }
      return {
        type: 'Feature',
        properties,
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [lon - half, lat - half],
              [lon + half, lat - half],
              [lon + half, lat + half],
              [lon - half, lat + half],
              [lon - half, lat - half],
            ],
          ],
        },
      }
    }),
  }
}

/** True if any cell is Moderate or worse at `hour`. */
export function hasWeatherAt(heatmap: HeatmapResponse | undefined, hour: number): boolean {
  return Boolean(heatmap?.cells.some((cell) => '1234'.includes(cell.levels[hour] ?? '')))
}
