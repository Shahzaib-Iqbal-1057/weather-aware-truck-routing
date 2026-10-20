import type { CheckpointWeather } from '../api/types'

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes} min`
  return minutes === 0 ? `${hours} h` : `${hours} h ${minutes} min`
}

/** A moment shown on the clock of `timeZone`, e.g. "Tue 6:50 AM CDT". */
export function formatClock(utc: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).formatToParts(new Date(utc))
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? ''
  return `${part('weekday')} ${part('hour')}:${part('minute')} ${part('dayPeriod')} ${part('timeZoneName')}`
}

/** One-line weather summary, e.g. "Light rain, 54°F · wind 18 mph (gusts 31) · rain 0.12 in/hr". */
export function formatWeather(weather: CheckpointWeather | null): string {
  if (!weather) return 'Weather unavailable'
  const parts = []
  const sky = [weather.conditions, weather.temperature_f !== null && `${weather.temperature_f}°F`]
    .filter(Boolean)
    .join(', ')
  if (sky) parts.push(sky)
  const gusts = weather.gust_mph !== null ? ` (gusts ${Math.round(weather.gust_mph)})` : ''
  parts.push(`wind ${Math.round(weather.wind_mph)} mph${gusts}`)
  if (weather.rain_in_per_hr > 0) parts.push(`rain ${weather.rain_in_per_hr.toFixed(2)} in/hr`)
  if (weather.snow_in_per_hr > 0) parts.push(`snow ${weather.snow_in_per_hr.toFixed(2)} in/hr`)
  return parts.join(' · ')
}

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString('en-US')} mi`
}
