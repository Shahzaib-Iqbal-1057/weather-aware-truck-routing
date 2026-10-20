import { describe, expect, it } from 'vitest'
import type { Place, RouteResult } from '../../api/types'
import { endpointFeatures, routeFeatures, routesBounds } from './geojson'

const ROUTES: RouteResult[] = [
  {
    id: 'A',
    distance_mi: 10,
    travel_time_s: 600,
    traffic_delay_s: 0,
    geometry: [
      [-105, 39.7],
      [-104.8, 38.8],
    ],
    label_position: [-104.9, 39.2],
  },
  {
    id: 'B',
    distance_mi: 12,
    travel_time_s: 700,
    traffic_delay_s: 0,
    geometry: [
      [-105, 39.7],
      [-105.2, 39.0],
      [-104.8, 38.8],
    ],
    label_position: [-105.2, 39.0],
  },
]

const DENVER: Place = { label: 'Denver, CO', lat: 39.7, lon: -105, kind: 'city', timezone: null }

describe('routeFeatures', () => {
  it('marks only the selected route', () => {
    const collection = routeFeatures(ROUTES, 'B')
    expect(collection.features.map((f) => f.properties)).toEqual([
      { id: 'A', selected: false },
      { id: 'B', selected: true },
    ])
    expect(collection.features[1].geometry.coordinates).toEqual(ROUTES[1].geometry)
  })
})

describe('endpointFeatures', () => {
  it('includes only the places that are set, as [lon, lat] points', () => {
    const collection = endpointFeatures(DENVER, null)
    expect(collection.features).toHaveLength(1)
    expect(collection.features[0].properties.role).toBe('origin')
    expect(collection.features[0].geometry.coordinates).toEqual([-105, 39.7])
  })
})

describe('routesBounds', () => {
  it('covers every route', () => {
    expect(routesBounds(ROUTES)).toEqual([
      [-105.2, 38.8],
      [-104.8, 39.7],
    ])
  })

  it('is null without routes', () => {
    expect(routesBounds([])).toBeNull()
  })
})
