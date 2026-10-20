import type { ReactNode } from 'react'
import './MapMessage.css'

interface MapMessageProps {
  title?: string
  /** Shows a spinner; the message is read out as a status update. */
  busy?: boolean
  /** A first-use hint: on phones only the title is shown, so the small map stays visible. */
  hint?: boolean
  children: ReactNode
}

/** A small card over the map: what to do first, progress, or what went wrong. */
export function MapMessage({ title, busy = false, hint = false, children }: MapMessageProps) {
  const className = ['map-message', busy && 'map-message--busy', hint && 'map-message--hint']
    .filter(Boolean)
    .join(' ')
  return (
    <div className={className} role="status">
      {busy && <span className="map-message__spinner" aria-hidden="true" />}
      <div>
        {title && <p className="map-message__title">{title}</p>}
        <p className="map-message__text">{children}</p>
      </div>
    </div>
  )
}
