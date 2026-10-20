import { useEffect, useState } from 'react'
import { formatClock } from '../../lib/format'
import './HeatmapControl.css'

const HOUR_MS = 3_600_000
const PLAY_STEP_MS = 500

interface HeatmapControlProps {
  enabled: boolean
  onEnable: () => void
  /** Hour index from the departure hour (0 … hours − 1). */
  hour: number
  onHourChange: (hour: number) => void
  hours: number
  /** The departure hour, as UTC ISO. */
  startUtc: string
  timeZone: string
  status: 'loading' | 'ready' | 'busy' | 'error'
  /** False when no cell is Moderate or worse at this hour. */
  hasWeather: boolean
}

/** Turns the weather map on, and picks the hour it shows: drag, step with the arrow keys, or play. */
export function HeatmapControl({
  enabled,
  onEnable,
  hour,
  onHourChange,
  hours,
  startUtc,
  timeZone,
  status,
  hasWeather,
}: HeatmapControlProps) {
  const [playRequested, setPlayRequested] = useState(false)
  const lastHour = hours - 1
  // Playback stops by itself at the last hour.
  const playing = playRequested && hour < lastHour

  // Playing advances one hour every half second.
  useEffect(() => {
    if (!playing) return
    const timer = setTimeout(() => onHourChange(hour + 1), PLAY_STEP_MS)
    return () => clearTimeout(timer)
  }, [playing, hour, onHourChange])

  if (!enabled) {
    return (
      <div className="heatmap-control heatmap-control--off">
        <button type="button" className="heatmap-control__enable" onClick={onEnable}>
          Show weather map (next 48 h)
        </button>
      </div>
    )
  }

  const shownAt = new Date(Date.parse(startUtc) + hour * HOUR_MS).toISOString()
  const ready = status === 'ready'
  return (
    <section className="heatmap-control" aria-label="Weather map time">
      <div className="heatmap-control__row">
        <button
          type="button"
          className="heatmap-control__play"
          onClick={() => {
            if (playing) {
              setPlayRequested(false)
              return
            }
            if (hour >= lastHour) onHourChange(0) // replay from the start
            setPlayRequested(true)
          }}
          disabled={!ready}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          className="heatmap-control__slider"
          min={0}
          max={lastHour}
          step={1}
          value={hour}
          disabled={!ready}
          aria-label="Hours after departure"
          aria-valuetext={`${formatClock(shownAt, timeZone)}, ${hour} hours after departure`}
          onChange={(event) => {
            setPlayRequested(false)
            onHourChange(Number(event.target.value))
          }}
        />
      </div>
      <p className="heatmap-control__status" aria-live={playing ? 'off' : 'polite'}>
        {status === 'loading' && 'Loading weather map…'}
        {status === 'busy' && 'The weather map is busy. Retrying shortly…'}
        {status === 'error' && 'The weather map is unavailable right now.'}
        {ready && (
          <>
            <strong>Weather at {formatClock(shownAt, timeZone)}</strong> · +{hour} h
            {!hasWeather && ' · no significant weather in the corridor'}
          </>
        )}
      </p>
    </section>
  )
}
