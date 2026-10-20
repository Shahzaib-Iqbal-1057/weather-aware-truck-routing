import { describe, expect, it } from 'vitest'
import type { Place, RouteResult } from '../../api/types'
import { makeRoute } from '../../test/fixtures'
import {
  checkpointFeatures,
  checkpointLabel,
  endpointFeatures,
  restStopFeatures,
  riskStretchFeatures,
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

describe('riskStretchFeatures', () => {
  it("draws every route's risky stretches, marking the selected route", () => {
    const geometry: [number, number][] = [
      [-105, 39.5],
      [-105, 39.2],
    ]
    const routes = [
      makeRoute({ id: 'A', risk_stretches: [{ level: 'high', from_mi: 10, to_mi: 30, geometry }] }),
      makeRoute({
        id: 'B',
        risk_stretches: [{ level: 'severe', from_mi: 0, to_mi: 5, geometry }],
      }),
    ]

    const collection = riskStretchFeatures(routes, 'B')

    expect(collection.features.map((f) => f.properties)).toEqual([
      { id: 'A', selected: false, level: 'high' },
      { id: 'B', selected: true, level: 'severe' },
    ])
    expect(collection.features[0].geometry.coordinates).toEqual(geometry)
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
  it('labels each checkpoint with its mile, ETA on the departure clock and weather', () => {
    const route = makeRoute({
      checkpoints: [
        {
          position: [-96.8, 32.78],
          mile: 120.4,
          eta_utc: '2026-10-20T14:45:00Z',
          weather: {
            forecast_hour_utc: '2026-10-20T15:00:00Z',
            wind_mph: 18.4,
            gust_mph: 31.2,
            rain_in_per_hr: 0.12,
            snow_in_per_hr: 0,
            temperature_f: 54,
            conditions: 'Light rain',
          },
          risk: { level: 'moderate', reasons: ['Rain 0.12 in/hr'] },
        },
      ],
    })

    const [feature] = checkpointFeatures(route, 'America/Chicago').features

    expect(feature.properties.label).toBe(
      'Mile 120 · Tue 9:45 AM CDT\nModerate risk: Rain 0.12 in/hr\nLight rain, 54°F · wind 18.4 mph (gusts 31.2) · rain 0.12 in/hr',
    )
    expect(feature.geometry.coordinates).toEqual([-96.8, 32.78])
    expect(feature.properties.level).toBe('moderate')
  })

  it('is empty when no route is selected', () => {
    expect(checkpointFeatures(null, 'UTC').features).toEqual([])
  })

  it('keeps the ends, every fifth Low checkpoint and anything riskier when zoomed out', () => {
    const levels = ['low', 'low', 'moderate', 'low', 'low', 'low', 'low', 'low'] as const
    const route = makeRoute({
      checkpoints: levels.map((level, i) => ({
        position: [-100, 35 + i / 10],
        mile: i * 10,
        eta_utc: '2026-10-20T14:00:00Z',
        weather: null,
        risk: { level, reasons: [] },
      })),
    })

    const kept = checkpointFeatures(route, 'UTC').features.map((f) => f.properties.keepZoomedOut)

    expect(kept).toEqual([true, false, true, false, false, true, false, true])
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

describe('checkpointLabel', () => {
  const base = {
    position: [-96.8, 32.78] as [number, number],
    mile: 10,
    eta_utc: '2026-10-20T14:45:00Z',
  }

  it('says Low risk without reasons for calm weather', () => {
    const label = checkpointLabel(
      {
        ...base,
        weather: {
          forecast_hour_utc: '2026-10-20T15:00:00Z',
          wind_mph: 7,
          gust_mph: null,
          rain_in_per_hr: 0,
          snow_in_per_hr: 0,
          temperature_f: null,
          conditions: null,
        },
        risk: { level: 'low', reasons: [] },
      },
      'America/Chicago',
    )
    expect(label.split('\n')[1]).toBe('Low risk')
  })

  it('says the risk is unknown without a forecast', () => {
    const label = checkpointLabel(
      { ...base, weather: null, risk: { level: 'unknown', reasons: ['No forecast'] } },
      'America/Chicago',
    )
    expect(label.split('\n').slice(1)).toEqual(['Risk unknown', 'Weather unavailable'])
  })
})
