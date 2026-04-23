import { useState, useEffect, useRef } from 'react'

export function useAlertFeed() {
  const [alerts, setAlerts] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)
  const retryRef = useRef(null)
  const retryCountRef = useRef(0)
  const DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]

  useEffect(() => {
    function connect() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${window.location.host}/ws/alerts`)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        retryCountRef.current = 0
      }
      ws.onmessage = (e) => {
        try {
          const alert = JSON.parse(e.data)
          if (!alert.alert_id) return
          setAlerts(prev => {
            if (prev.some(a => a.alert_id === alert.alert_id)) return prev
            return [alert, ...prev].slice(0, 50)
          })
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

  return { alerts, isConnected }
}
