import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { HeatmapControl } from './HeatmapControl'

type Status = 'loading' | 'ready' | 'busy' | 'error'

function Harness({
  enabled = true,
  status = 'ready',
  hours = 4,
  onEnable = () => {},
}: {
  enabled?: boolean
  status?: Status
  hours?: number
  onEnable?: () => void
}) {
  const [hour, setHour] = useState(0)
  return (
    <HeatmapControl
      enabled={enabled}
      onEnable={onEnable}
      hour={hour}
      onHourChange={setHour}
      hours={hours}
      startUtc="2026-10-21T15:00:00Z"
      timeZone="America/Los_Angeles"
      status={status}
      hasWeather={hour === 2}
    />
  )
}

describe('HeatmapControl', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('offers to turn the weather map on', () => {
    const onEnable = vi.fn()
    render(<Harness enabled={false} onEnable={onEnable} />)
    fireEvent.click(screen.getByRole('button', { name: 'Show weather map (next 48 h)' }))
    expect(onEnable).toHaveBeenCalled()
  })

  it('shows the hour on the departure clock and says when nothing is happening', () => {
    render(<Harness />)
    expect(screen.getByText(/Weather at Wed 8:00 AM PDT/)).toBeInTheDocument()
    expect(screen.getByText(/no significant weather in the corridor/)).toBeInTheDocument()

    fireEvent.change(screen.getByRole('slider'), { target: { value: '2' } })

    expect(screen.getByText(/Weather at Wed 10:00 AM PDT/)).toBeInTheDocument()
    expect(screen.queryByText(/no significant weather/)).not.toBeInTheDocument()
  })

  it('plays forward one hour every half second and stops at the end', () => {
    render(<Harness hours={3} />)
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))

    act(() => vi.advanceTimersByTime(500))
    expect(screen.getByRole('slider')).toHaveValue('1')
    act(() => vi.advanceTimersByTime(500))
    expect(screen.getByRole('slider')).toHaveValue('2')
    act(() => vi.advanceTimersByTime(2000))
    expect(screen.getByRole('slider')).toHaveValue('2')
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
  })

  it('is disabled while loading and says so', () => {
    render(<Harness status="loading" />)
    expect(screen.getByRole('slider')).toBeDisabled()
    expect(screen.getByText('Loading weather map…')).toBeInTheDocument()
  })
})
