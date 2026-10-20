import type { RiskLevelKey } from '../api/types'

export interface RiskLevelStyle {
  key: RiskLevelKey
  label: string
  color: string
}

// Ordered least to most severe, then Unknown. Status colours (good → critical, then a darker red
// for No Travel) are reserved for risk; routes use blue/gray. Colour never stands alone: the
// legend and every popup name the level.
export const RISK_LEVELS: readonly RiskLevelStyle[] = [
  { key: 'low', label: 'Low', color: '#0ca30c' },
  { key: 'moderate', label: 'Moderate', color: '#fab219' },
  { key: 'high', label: 'High', color: '#ec835a' },
  { key: 'severe', label: 'Severe', color: '#d03b3b' },
  { key: 'no_travel', label: 'No Travel', color: '#7a1023' },
  { key: 'unknown', label: 'Unknown', color: '#c3c2b7' },
]

const BY_KEY = Object.fromEntries(RISK_LEVELS.map((level) => [level.key, level])) as Record<
  RiskLevelKey,
  RiskLevelStyle
>

export function riskStyle(key: RiskLevelKey): RiskLevelStyle {
  return BY_KEY[key]
}
