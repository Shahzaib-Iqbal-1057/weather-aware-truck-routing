import { useEffect, useState } from 'react'

/** The current time, refreshed periodically so time-based limits and hints stay current. */
export function useNow(refreshMs = 60_000): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), refreshMs)
    return () => clearInterval(timer)
  }, [refreshMs])

  return now
}
