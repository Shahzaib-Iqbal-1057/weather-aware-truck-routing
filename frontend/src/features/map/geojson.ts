import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type { Checkpoint, Place, RiskLevelKey, RouteId, RouteResult } from '../../api/types'
import { formatClock, formatDuration, formatWeather } from '../../lib/format'
import { riskStyle } from '../../lib/risk'

export interface RouteProperties {
  id: RouteId
  selected: boolean
}

export interface EndpointProperties {
  role: 'origin' | 'destination'
  label: string
}

export function routeFeatures(
  routes: RouteResult[],
  selectedId: RouteId | null,
): FeatureCollection<LineString, RouteProperties> {
  return {
    type: 'FeatureCollection',
    features: routes.map((route): Feature<LineString, RouteProperties> => ({
      type: 'Feature',
      properties: { id: route.id, selected: route.id === selectedId },
      geometry: { type: 'LineString', coordinates: route.geometry },
    })),
  }
}

export function endpointFeatures(
  origin: Place | null,
  destination: Place | null,
): FeatureCollection<Point, EndpointProperties> {
  const features: Feature<Point, EndpointProperties>[] = []
  if (origin) features.push(endpoint('origin', origin))
  if (destination) features.push(endpoint('destination', destination))
  return { type: 'FeatureCollection', features }
}

function endpoint(
  role: EndpointProperties['role'],
  place: Place,
): Feature<Point, EndpointProperties> {
  return {
    type: 'Feature',
    properties: { role, label: place.label },
    geometry: { type: 'Point', coordinates: [place.lon, place.lat] },
  }
}

/** [[west, south], [east, north]] around every route, or null when there are none. */
export function routesBounds(routes: RouteResult[]): [[number, number], [number, number]] | null {
  let west = Infinity
  let south = Infinity
  let east = -Infinity
  let north = -Infinity
  for (const route of routes) {
    for (const [lon, lat] of route.geometry) {
      west = Math.min(west, lon)
      east = Math.max(east, lon)
      south = Math.min(south, lat)
      north = Math.max(north, lat)
    }
  }
  return Number.isFinite(west)
    ? [
        [west, south],
        [east, north],
      ]
    : null
}

export interface PointLabelProperties {
  /** Shown when the point is hovered or tapped. */
  label: string
}

export interface CheckpointProperties extends PointLabelProperties {
  level: RiskLevelKey
}

export interface RestStopProperties extends PointLabelProperties {
  kind: 'break' | 'rest'
}

/** The selected route's checkpoints, with their risk level and a label for the popup. */
export function checkpointFeatures(
  route: RouteResult | null,
  timeZone: string,
): FeatureCollection<Point, CheckpointProperties> {
  return {
    type: 'FeatureCollection',
    features: (route?.checkpoints ?? []).map((checkpoint) => ({
      type: 'Feature',
      properties: { level: checkpoint.risk.level, label: checkpointLabel(checkpoint, timeZone) },
      geometry: { type: 'Point', coordinates: checkpoint.position },
    })),
  }
}

/** "Mile 120 · Tue 9:45 AM CDT", then "High risk: Gusts 57.3 mph", then the weather summary. */
export function checkpointLabel(checkpoint: Checkpoint, timeZone: string): string {
  const where = `Mile ${Math.round(checkpoint.mile)} · ${formatClock(checkpoint.eta_utc, timeZone)}`
  const { label } = riskStyle(checkpoint.risk.level)
  const why = checkpoint.risk.reasons.length ? `: ${checkpoint.risk.reasons.join(', ')}` : ''
  const risk = checkpoint.risk.level === 'unknown' ? 'Risk unknown' : `${label} risk${why}`
  return `${where}\n${risk}\n${formatWeather(checkpoint.weather)}`
}

/** The selected route's required driver stops, labelled with their kind and times. */
export function restStopFeatures(
  route: RouteResult | null,
  timeZone: string,
): FeatureCollection<Point, RestStopProperties> {
  return {
    type: 'FeatureCollection',
    features: (route?.rest_stops ?? []).map((stop) => {
      const duration = formatDuration(
        (Date.parse(stop.ends_utc) - Date.parse(stop.starts_utc)) / 1000,
      )
      const what = stop.kind === 'rest' ? `${duration} rest` : `${duration} break`
      return {
        type: 'Feature',
        properties: {
          kind: stop.kind,
          label: `${what} · ${formatClock(stop.starts_utc, timeZone)} – ${formatClock(stop.ends_utc, timeZone)}`,
        },
        geometry: { type: 'Point', coordinates: stop.position },
      }
    }),
  }
}
