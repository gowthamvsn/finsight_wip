import { useState, useEffect, useRef } from 'react'

export function useLivePrices() {
  const [isConnected, setIsConnected] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)
  const wsRef = useRef(null)
  const retryRef = useRef(null)
  const retryCountRef = useRef(0)
  const DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]

  useEffect(() => {
    function connect() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${window.location.host}/ws/dashboard`)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        retryCountRef.current = 0
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'price_update') {
            setRefreshTick(t => t + 1)
          }
        } catch {}
      }
      ws.onclose = () => {
        setIsConnected(false)
        const delay = DELAYS[Math.min(retryCountRef.current, DELAYS.length - 1)]
        retryCountRef.current++
        retryRef.current = setTimeout(connect, delay)
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => {
      clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [])

  return { isConnected, refreshTick }
}
