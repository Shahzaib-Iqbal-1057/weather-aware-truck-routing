import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BackendStatus } from './BackendStatus'

function renderWithQueryClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <BackendStatus />
    </QueryClientProvider>,
  )
}

describe('BackendStatus', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows connected when the health check succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }))),
    )
    renderWithQueryClient()
    expect(await screen.findByText('API connected')).toBeInTheDocument()
  })

  it('shows an error when the health check fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })))
    renderWithQueryClient()
    expect(await screen.findByText('API unreachable')).toBeInTheDocument()
  })
})
