import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeRoute } from '../../test/fixtures'
import { RouteList } from './RouteList'

const H = 3600
const SEVERE_ON_A = {
  totals: { severe_mi: 40, high_mi: 10, no_travel_mi: 0, unknown_mi: 0, average_risk: 0.6 },
}
const ROUTES = [
  // 12 h 20 min of driving: 30-min break + 10-h rest, arriving the next morning.
  makeRoute({
    id: 'A',
    distance_mi: 889.3,
    driving_time_s: 12 * H + 20 * 60,
    trip_time_s: 22 * H + 50 * 60,
    arrival_utc: '2026-10-21T11:50:00Z',
    ...SEVERE_ON_A,
  }),
  makeRoute({
    id: 'B',
    distance_mi: 799.6,
    driving_time_s: 12 * H + 48 * 60,
    trip_time_s: 23 * H + 18 * 60,
    arrival_utc: '2026-10-21T12:18:00Z',
  }),
]

function renderList(onSelect = vi.fn(), notes: string[] = []) {
  render(
    <RouteList
      routes={ROUTES}
      notes={notes}
      selectedId="A"
      onSelect={onSelect}
      timeZone="America/Chicago"
      destinationName="Denver"
      recommendation={{
        route_id: 'B',
        reason: 'Route B: fewer Severe miles than A (0 vs 40); 28 min slower than A.',
      }}
    />,
  )
  return screen.getAllByRole('button')
}

describe('RouteList', () => {
  it('shows arrival on the departure clock, driving and rest time, and distance', () => {
    const [first, second] = renderList()

    expect(first).toHaveTextContent(
      'Route AFastestArrives Wed 6:50 AM CDT12 h 20 min driving + 10 h 30 min rest · 889 mi',
    )
    expect(second).toHaveTextContent('Route BRecommended+28 minArrives Wed 7:18 AM CDT')
  })

  it('omits rest when the trip needs none', () => {
    render(
      <RouteList
        routes={[makeRoute({ driving_time_s: 2 * H, trip_time_s: 2 * H })]}
        notes={[]}
        selectedId="A"
        onSelect={() => {}}
        timeZone="America/Chicago"
        destinationName="Denver"
        recommendation={{ route_id: 'A', reason: 'Route A: the only truck route for this trip.' }}
      />,
    )
    expect(screen.getByRole('button')).toHaveTextContent('2 h driving · 100 mi')
  })

  it('marks the selected route and reports clicks', () => {
    const onSelect = vi.fn()
    const [first, second] = renderList(onSelect)

    expect(first).toHaveAttribute('aria-pressed', 'true')
    expect(second).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(second)
    expect(onSelect).toHaveBeenCalledWith('B')
  })

  it('moves focus to the results when a plan arrives', () => {
    renderList()
    expect(screen.getByRole('heading', { name: 'Routes' })).toHaveFocus()
  })

  it('shows notes such as a shortfall in distinct routes', () => {
    renderList(vi.fn(), ['Only 2 distinct truck routes exist for this trip.'])
    expect(
      screen.getByText('Only 2 distinct truck routes exist for this trip.'),
    ).toBeInTheDocument()
  })
})

describe('RouteList rest note', () => {
  const restAt = (mile: number) =>
    makeRoute({
      distance_mi: 795.4,
      rest_stops: [
        {
          kind: 'rest',
          position: [-84.4, 33.7],
          mile,
          starts_utc: '2026-10-21T00:00:00Z',
          ends_utc: '2026-10-21T10:00:00Z',
        },
      ],
    })

  function renderRoute(route: ReturnType<typeof makeRoute>) {
    render(
      <RouteList
        routes={[route]}
        notes={[]}
        selectedId="A"
        onSelect={() => {}}
        timeZone="America/Chicago"
        destinationName="Atlanta"
        recommendation={{ route_id: 'A', reason: 'Route A: the only truck route for this trip.' }}
      />,
    )
  }

  it('explains a 10-hour rest just before the destination', () => {
    renderRoute(restAt(793.8))
    expect(
      screen.getByText(
        'Includes a 10 h rest 2 mi before Atlanta: the 11-hour driving limit runs out first.',
      ),
    ).toBeInTheDocument()
  })

  it('says nothing extra when the rest is well before the destination', () => {
    renderRoute(restAt(700))
    expect(screen.queryByText(/before Atlanta/)).not.toBeInTheDocument()
  })
})

describe('RouteList recommendation', () => {
  it('shows the recommended route and why, above the cards', () => {
    renderList()
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Recommended: Route B')
    expect(status).toHaveTextContent('fewer Severe miles than A (0 vs 40)')
  })

  it('shows each route’s risk totals', () => {
    const [first] = renderList()
    expect(first).toHaveTextContent('40 Severe mi · 10 High mi · avg risk 0.60')
  })

  it('says when nothing is recommended and still lists the routes', () => {
    render(
      <RouteList
        routes={[
          makeRoute({
            totals: {
              severe_mi: 0,
              high_mi: 0,
              no_travel_mi: 20,
              unknown_mi: 0,
              average_risk: 0.4,
            },
          }),
        ]}
        notes={[]}
        selectedId="A"
        onSelect={() => {}}
        timeZone="America/Chicago"
        destinationName="Denver"
        recommendation={{
          route_id: null,
          reason:
            'Every route crosses No Travel conditions, so none is recommended. Consider a later departure.',
        }}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('No route recommended')
    expect(screen.getByRole('button')).toHaveTextContent('No Travel conditions on 20 mi')
  })
})
