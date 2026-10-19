import { useMutation } from '@tanstack/react-query'
import { apiPost } from './client'
import type { TripPlanRequest, TripPlanResponse } from './types'

export function usePlanTrip() {
  return useMutation({
    mutationFn: (request: TripPlanRequest) => apiPost<TripPlanResponse>('/trips/plan/', request),
  })
}
