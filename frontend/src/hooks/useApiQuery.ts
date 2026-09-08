import { useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'

interface QueryState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useApiQuery<T>(path: string | null, deps: unknown[] = []): QueryState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(!!path)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    if (!path) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .get<T>(path)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps])

  return { data, loading, error, refetch }
}
