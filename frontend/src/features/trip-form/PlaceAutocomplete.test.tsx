import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Place } from '../../api/types'
import { PlaceAutocomplete } from './PlaceAutocomplete'

const RESULTS: Place[] = [
  { label: 'Springfield, MO', lat: 37.2, lon: -93.3, kind: 'city', timezone: 'America/Chicago' },
  { label: 'Springfield, IL', lat: 39.8, lon: -89.6, kind: 'city', timezone: 'America/Chicago' },
]

function Harness({ onChange }: { onChange: (place: Place | null) => void }) {
  const [value, setValue] = useState<Place | null>(null)
  return (
    <PlaceAutocomplete
      label="Origin"
      value={value}
      onChange={(place) => {
        setValue(place)
        onChange(place)
      }}
    />
  )
}

function setup() {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ results: RESULTS })))
  vi.stubGlobal('fetch', fetchMock)
  const onChange = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <Harness onChange={onChange} />
    </QueryClientProvider>,
  )
  const input = screen.getByRole('combobox', { name: 'Origin' })
  return { input, onChange, fetchMock }
}

describe('PlaceAutocomplete', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('does not search until 3 characters are typed', async () => {
    const { input, fetchMock } = setup()
    fireEvent.change(input, { target: { value: 'sp' } })
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows suggestions and selects one with the mouse', async () => {
    const { input, onChange, fetchMock } = setup()
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'springf' } })

    const option = await screen.findByRole('option', { name: /Springfield, IL/ })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/geocode/?q=springf')

    fireEvent.mouseDown(option)
    expect(onChange).toHaveBeenLastCalledWith(RESULTS[1])
    expect(input).toHaveValue('Springfield, IL')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('selects the highlighted suggestion with the keyboard', async () => {
    const { input, onChange } = setup()
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'springf' } })
    await screen.findAllByRole('option')

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(onChange).toHaveBeenLastCalledWith(RESULTS[1])
  })

  it('clears the selection when the text is edited', async () => {
    const { input, onChange } = setup()
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'springf' } })
    fireEvent.mouseDown(await screen.findByRole('option', { name: /Springfield, MO/ }))

    fireEvent.change(input, { target: { value: 'Springfield, M' } })

    expect(onChange).toHaveBeenLastCalledWith(null)
  })
})
