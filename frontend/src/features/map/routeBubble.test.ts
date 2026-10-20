import { describe, expect, it, vi } from 'vitest'
import type { RouteResult } from '../../api/types'
import { createRouteBubble, routeBubbleText } from './routeBubble'

const ROUTE: RouteResult = {
  id: 'B',
  distance_mi: 879,
  travel_time_s: 13 * 3600 + 50 * 60,
  traffic_delay_s: 0,
  geometry: [],
  label_position: [-97.5, 35.4],
}

describe('route bubble', () => {
  it('shows the route letter and travel time', () => {
    expect(routeBubbleText(ROUTE)).toBe('B · 13 h 50 min')
  })

  it('is a button that reports its route when clicked', () => {
    const onSelect = vi.fn()
    const bubble = createRouteBubble(ROUTE, false, onSelect)

    bubble.click()

    expect(bubble.tagName).toBe('BUTTON')
    expect(bubble).toHaveAttribute('aria-pressed', 'false')
    expect(onSelect).toHaveBeenCalledWith('B')
  })

  it('marks the selected route', () => {
    expect(createRouteBubble(ROUTE, true, () => {})).toHaveAttribute('aria-pressed', 'true')
  })
})
