import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'
import type { GeocodeResponse } from './types'

export const MIN_QUERY_LENGTH = 3

export function usePlaceSearch(query: string, enabled: boolean) {
  return useQuery({
    queryKey: ['geocode', query.toLowerCase()],
    queryFn: () => apiGet<GeocodeResponse>('/geocode/', { q: query }).then((data) => data.results),
    enabled: enabled && query.length >= MIN_QUERY_LENGTH,
    staleTime: Infinity,
    retry: false,
  })
}
