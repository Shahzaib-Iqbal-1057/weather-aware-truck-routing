import { describe, expect, it, vi } from 'vitest'
import { makeRoute } from '../../test/fixtures'
import { createRouteBubble, routeBubbleText } from './routeBubble'

const ROUTE = makeRoute({ id: 'B', driving_time_s: 13 * 3600, trip_time_s: 23 * 3600 + 30 * 60 })

describe('route bubble', () => {
  it('shows the route letter and door-to-door time', () => {
    expect(routeBubbleText(ROUTE)).toBe('B · 23 h 30 min')
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
