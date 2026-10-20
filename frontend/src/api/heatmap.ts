import { useQuery } from '@tanstack/react-query'
import { ApiError, apiPost } from './client'
import type { HeatmapResponse, TripPlanRequest } from './types'

const RETRY_AFTER_MS = 60_000

/** The weather map for a planned trip. Only fetched once the user turns it on. */
export function useHeatmap(request: TripPlanRequest | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['heatmap', request],
    queryFn: () => apiPost<HeatmapResponse>('/trips/heatmap/', request),
    enabled: enabled && request !== undefined,
    staleTime: 30 * 60_000,
    // The server answers 503 when the free weather allowance is busy: wait and try again. Not
    // when the hour's or day's allowance is used up: that won't clear within minutes.
    retry: (failures, error) =>
      error instanceof ApiError &&
      error.status === 503 &&
      !weatherAllowanceUsedUp(error) &&
      failures < 3,
    retryDelay: RETRY_AFTER_MS,
  })
}

/** True when the server refused because the hourly or daily weather allowance is used up. */
export function weatherAllowanceUsedUp(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    typeof error.body === 'object' &&
    error.body !== null &&
    'code' in error.body &&
    error.body.code === 'weather_allowance_used_up'
  )
}
