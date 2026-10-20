import type { RouteResult } from '../../api/types'

/** "0 Severe mi · 10 High mi · avg risk 0.12", plus miles without a forecast. */
export function riskSummary(route: RouteResult): string {
  const { totals } = route
  if (totals.average_risk === null) return 'Weather risk unknown'
  const parts = [
    `${Math.round(totals.severe_mi)} Severe mi`,
    `${Math.round(totals.high_mi)} High mi`,
    `avg risk ${totals.average_risk.toFixed(2)}`,
  ]
  if (totals.unknown_mi >= 1) parts.push(`${Math.round(totals.unknown_mi)} mi without forecast`)
  return parts.join(' · ')
}
