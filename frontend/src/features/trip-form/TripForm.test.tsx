import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
