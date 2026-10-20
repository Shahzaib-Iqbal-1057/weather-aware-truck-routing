import { describe, expect, it } from 'vitest'
import type { Place, RouteResult } from '../../api/types'
import { makeRoute } from '../../test/fixtures'
import {
  checkpointFeatures,
  endpointFeatures,
  restStopFeatures,
  routeFeatures,
  routesBounds,
} from './geojson'

const ROUTES: RouteResult[] = [
  makeRoute({
    id: 'A',
    geometry: [
      [-105, 39.7],
      [-104.8, 38.8],
    ],
  }),
  makeRoute({
    id: 'B',
    geometry: [
      [-105, 39.7],
      [-105.2, 39.0],
      [-104.8, 38.8],
    ],
  }),
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

describe('checkpointFeatures', () => {
  it('labels each checkpoint with its mile and ETA on the departure clock', () => {
    const route = makeRoute({
      checkpoints: [{ position: [-96.8, 32.78], mile: 120.4, eta_utc: '2026-10-20T14:45:00Z' }],
    })

    const [feature] = checkpointFeatures(route, 'America/Chicago').features

    expect(feature.properties.label).toBe('Mile 120 · Tue 9:45 AM CDT')
    expect(feature.geometry.coordinates).toEqual([-96.8, 32.78])
  })

  it('is empty when no route is selected', () => {
    expect(checkpointFeatures(null, 'UTC').features).toEqual([])
  })
})

describe('restStopFeatures', () => {
  it('labels stops with their length and times', () => {
    const route = makeRoute({
      rest_stops: [
        {
          kind: 'rest',
          position: [-100, 36],
          mile: 790,
          starts_utc: '2026-10-21T00:30:00Z',
          ends_utc: '2026-10-21T10:30:00Z',
        },
      ],
    })

    const [feature] = restStopFeatures(route, 'America/Chicago').features

    expect(feature.properties).toEqual({
      kind: 'rest',
      label: '10 h rest · Tue 7:30 PM CDT – Wed 5:30 AM CDT',
    })
  })
})
