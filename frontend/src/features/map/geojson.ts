import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type { Place, RouteId, RouteResult } from '../../api/types'

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
