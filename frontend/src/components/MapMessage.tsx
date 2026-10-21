import type { ReactNode } from 'react'
import './MapMessage.css'

interface MapMessageProps {
  title?: string
  /** Shows a spinner; the message is read out as a status update. */
  busy?: boolean
  children: ReactNode
}

/** A small card over the map: progress, or what went wrong. */
export function MapMessage({ title, busy = false, children }: MapMessageProps) {
  return (
    <div className={`map-message${busy ? ' map-message--busy' : ''}`} role="status">
      {busy && <span className="map-message__spinner" aria-hidden="true" />}
      <div>
        {title && <p className="map-message__title">{title}</p>}
        <p className="map-message__text">{children}</p>
      </div>
    </div>
  )
}
