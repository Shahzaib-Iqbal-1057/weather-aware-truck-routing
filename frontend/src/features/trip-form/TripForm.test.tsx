import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TripForm } from './TripForm'

function renderForm(serverErrors = {}) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TripForm
        onSubmit={() => {}}
        isSubmitting={false}
        serverErrors={serverErrors}
        generalError={null}
      />
    </QueryClientProvider>,
  )
}

describe('TripForm', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps the default departure at "now" while the form stays open', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T15:05:00Z'))
    renderForm()
    const departure = screen.getByLabelText(/^Departure/) as HTMLInputElement
    const first = departure.value

    act(() => {
      vi.advanceTimersByTime(20 * 60_000)
    })

    expect(departure.value).not.toBe(first)
    expect(Date.parse(departure.value) - Date.parse(first)).toBe(15 * 60_000) // :15 → :30
  })

  it('stops following the clock once the user picks a departure', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T15:05:00Z'))
    renderForm()
    const departure = screen.getByLabelText(/^Departure/) as HTMLInputElement
    fireEvent.change(departure, { target: { value: '2026-10-22T09:00' } })

    act(() => {
      vi.advanceTimersByTime(20 * 60_000)
    })

    expect(departure.value).toBe('2026-10-22T09:00')
  })

  it('hides a server error once the user edits that field', () => {
    renderForm({ cargoWeightLb: 'Cargo weight must be between 0 and 45,000 lb.' })
    expect(screen.getByText('Cargo weight must be between 0 and 45,000 lb.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Cargo weight (lb)'), { target: { value: '30000' } })

    expect(screen.queryByText(/Cargo weight must be between/)).not.toBeInTheDocument()
  })

  it('keeps server errors on fields the user has not touched', () => {
    renderForm({ departureLocal: 'Departure time is in the past.' })

    fireEvent.change(screen.getByLabelText('Cargo weight (lb)'), { target: { value: '30000' } })

    expect(screen.getByText('Departure time is in the past.')).toBeInTheDocument()
  })
})
