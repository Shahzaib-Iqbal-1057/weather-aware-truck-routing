import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeRoute } from '../../test/fixtures'
import { RouteList } from './RouteList'

const H = 3600
const ROUTES = [
  // 12 h 20 min of driving: 30-min break + 10-h rest, arriving the next morning.
  makeRoute({
    id: 'A',
    distance_mi: 889.3,
    driving_time_s: 12 * H + 20 * 60,
    trip_time_s: 22 * H + 50 * 60,
    arrival_utc: '2026-10-21T11:50:00Z',
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
    expect(second).toHaveTextContent('Route B+28 minArrives Wed 7:18 AM CDT')
  })

  it('omits rest when the trip needs none', () => {
    render(
      <RouteList
        routes={[makeRoute({ driving_time_s: 2 * H, trip_time_s: 2 * H })]}
        notes={[]}
        selectedId="A"
        onSelect={() => {}}
        timeZone="America/Chicago"
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

  it('shows notes such as a shortfall in distinct routes', () => {
    renderList(vi.fn(), ['Only 2 distinct truck routes exist for this trip.'])
    expect(
      screen.getByText('Only 2 distinct truck routes exist for this trip.'),
    ).toBeInTheDocument()
  })
})
