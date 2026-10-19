import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { RouteResult } from '../../api/types'
import { RouteList } from './RouteList'

const ROUTES: RouteResult[] = [
  { id: 'A', distance_mi: 882.3, travel_time_s: 12 * 3600, traffic_delay_s: 720, geometry: [] },
  { id: 'B', distance_mi: 799.6, travel_time_s: 12.5 * 3600, traffic_delay_s: 0, geometry: [] },
]

describe('RouteList', () => {
  it('shows each route with its time, distance and difference from the fastest', () => {
    render(<RouteList routes={ROUTES} notes={[]} selectedId="A" onSelect={() => {}} />)

    const [first, second] = screen.getAllByRole('button')
    expect(first).toHaveTextContent('Route AFastest12 h · 882 mi · 12 min traffic')
    expect(second).toHaveTextContent('Route B+30 min12 h 30 min · 800 mi')
  })

  it('marks the selected route and reports clicks', () => {
    const onSelect = vi.fn()
    render(<RouteList routes={ROUTES} notes={[]} selectedId="A" onSelect={onSelect} />)

    const [first, second] = screen.getAllByRole('button')
    expect(first).toHaveAttribute('aria-pressed', 'true')
    expect(second).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(second)
    expect(onSelect).toHaveBeenCalledWith('B')
  })

  it('shows notes such as a shortfall in distinct routes', () => {
    render(
      <RouteList
        routes={ROUTES}
        notes={['Only 2 distinct truck routes exist for this trip.']}
        selectedId="A"
        onSelect={() => {}}
      />,
    )
    expect(
      screen.getByText('Only 2 distinct truck routes exist for this trip.'),
    ).toBeInTheDocument()
  })
})
