import { useEffect, useRef, useState, useCallback } from "react"
import type { MarketData, WebSocketMessage, SignalHistoryItem } from "../interfaces/types"

interface UseWebSocketReturn {
  data: MarketData | null
  isConnected: boolean
  error: string | null
  reconnect: () => void
  signalHistory: SignalHistoryItem[]
}

// Dynamically determine WebSocket URL based on current location
const getWebSocketURL = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  // In development, connect directly to localhost:8765
  // In production, connect through nginx proxy at /ws
  if (host.includes('localhost') || host.includes('127.0.0.1')) {
    return 'ws://localhost:8765'
  }
  return `${protocol}//${host}/ws`
}

const WEBSOCKET_URL = getWebSocketURL()
const RECONNECT_DELAY = 2000 // 2 seconds base delay
const MAX_RECONNECT_DELAY = 30000 // 30 seconds max
const CONNECTION_TIMEOUT = 10000 // 10 seconds
const PING_INTERVAL = 25000 // 25 seconds (keep under server's 30s timeout)

export function useWebSocket(): UseWebSocketReturn {
  const [data, setData] = useState<MarketData | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [signalHistory, setSignalHistory] = useState<SignalHistoryItem[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectAttemptsRef = useRef(0)

  // Use a ref to track if the component is truly mounted (handles React StrictMode)
  const isMountedRef = useRef(false)
  const isCleaningUpRef = useRef(false)

  // Track connection state to avoid race conditions
  const connectionStateRef = useRef<'disconnected' | 'connecting' | 'connected'>('disconnected')

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (connectionTimeoutRef.current) {
      clearTimeout(connectionTimeoutRef.current)
      connectionTimeoutRef.current = null
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
  }, [])

  const cleanup = useCallback((closeSocket = true) => {
    isCleaningUpRef.current = true
    clearTimers()

    if (wsRef.current && closeSocket) {
      // Remove handlers to prevent callbacks during cleanup
      wsRef.current.onopen = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null

      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000, "Client cleanup")
      } else if (wsRef.current.readyState === WebSocket.CONNECTING) {
        // For connections still in progress, close them
        wsRef.current.close()
      }
      wsRef.current = null
    }

    connectionStateRef.current = 'disconnected'
    isCleaningUpRef.current = false
  }, [clearTimers])

  const startPingInterval = useCallback(() => {
    // Clear any existing ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
    }

    // Send ping every PING_INTERVAL to keep connection alive
    pingIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ type: "ping" }))
        } catch (e) {
          console.warn("Failed to send ping:", e)
        }
      }
    }, PING_INTERVAL)
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (!isMountedRef.current || isCleaningUpRef.current) {
      return
    }

    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }

    reconnectAttemptsRef.current++
    // Exponential backoff with jitter
    const baseDelay = Math.min(RECONNECT_DELAY * Math.pow(1.5, reconnectAttemptsRef.current - 1), MAX_RECONNECT_DELAY)
    const jitter = Math.random() * 1000 // Add up to 1 second of jitter
    const delay = Math.floor(baseDelay + jitter)

    console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current})`)
    setError(`Reconnecting in ${Math.round(delay / 1000)}s...`)

    reconnectTimeoutRef.current = setTimeout(() => {
      if (isMountedRef.current && !isCleaningUpRef.current) {
        connect()
      }
    }, delay)
  }, [])

  const connect = useCallback(() => {
    // Don't connect if not mounted or cleaning up
    if (!isMountedRef.current || isCleaningUpRef.current) {
      return
    }

    // Don't create a new connection if one already exists and is open/connecting
    if (wsRef.current) {
      const state = wsRef.current.readyState
      if (state === WebSocket.OPEN) {
        console.log("WebSocket already connected")
        return
      }
      if (state === WebSocket.CONNECTING) {
        console.log("WebSocket already connecting")
        return
      }
    }

    // Clean up any existing dead connection without triggering reconnect
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.onmessage = null
      wsRef.current = null
    }

    clearTimers()
    connectionStateRef.current = 'connecting'

    try {
      console.log("Connecting to WebSocket:", WEBSOCKET_URL)
      setError("Connecting...")
      const ws = new WebSocket(WEBSOCKET_URL)
      wsRef.current = ws

      // Set connection timeout
      connectionTimeoutRef.current = setTimeout(() => {
        if (ws === wsRef.current && ws.readyState !== WebSocket.OPEN) {
          console.warn("Connection timeout - server may not be running")
          ws.close()
          connectionStateRef.current = 'disconnected'
          setError("Connection timeout - is the server running?")
          setIsConnected(false)

          if (isMountedRef.current) {
            scheduleReconnect()
          }
        }
      }, CONNECTION_TIMEOUT)

      ws.onopen = () => {
        // Verify this is still our current socket
        if (ws !== wsRef.current) {
          ws.close()
          return
        }

        console.log("WebSocket connected successfully")
        connectionStateRef.current = 'connected'
        setIsConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0

        // Clear connection timeout
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current)
          connectionTimeoutRef.current = null
        }

        // Start ping interval to keep connection alive
        startPingInterval()
      }

      ws.onmessage = (event) => {
        // Verify this is still our current socket
        if (ws !== wsRef.current) return

        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          if (message.type === "market_data" && message.data) {
            setData(message.data)
            setError(null)
            // Update signal history if included in the message
            if (message.signal_history) {
              setSignalHistory(message.signal_history)
            }
          } else if (message.type === "signal_history" && message.data) {
            // Handle dedicated signal history message (sent on connection)
            setSignalHistory(message.data as unknown as SignalHistoryItem[])
          } else if (message.type === "connection") {
            console.log("Server:", message.message)
          } else if (message.type === "pong") {
            // Server acknowledged our ping - connection is healthy
          }
        } catch (err) {
          console.error("Error parsing message:", err)
        }
      }

      ws.onerror = () => {
        // Verify this is still our current socket
        if (ws !== wsRef.current) return

        console.warn("WebSocket error - server may be unavailable")
        // Don't set error here - onclose will be called with more info
      }

      ws.onclose = (event) => {
        // Verify this is still our current socket
        if (ws !== wsRef.current) {
          return
        }

        console.log(`WebSocket closed: code=${event.code}, reason="${event.reason || 'No reason'}", wasClean=${event.wasClean}`)

        connectionStateRef.current = 'disconnected'
        setIsConnected(false)
        clearTimers()

        // Don't reconnect if we're cleaning up
        if (isCleaningUpRef.current || !isMountedRef.current) {
          return
        }

        // Only skip reconnect for intentional closures
        // 1000 = normal closure (we closed it), 1001 = going away
        if (event.code === 1000 && event.reason === "Client cleanup") {
          console.log("Connection closed intentionally by client")
          return
        }

        // For all other closures, try to reconnect
        // This handles: server restart, network issues, server crashes, etc.
        console.log("Connection lost - will attempt to reconnect")
        setError("Connection lost - reconnecting...")
        scheduleReconnect()
      }
    } catch (err) {
      console.error("Error creating WebSocket:", err)
      connectionStateRef.current = 'disconnected'
      setError("Failed to create connection")
      setIsConnected(false)

      if (isMountedRef.current) {
        scheduleReconnect()
      }
    }
  }, [clearTimers, scheduleReconnect, startPingInterval])

  const reconnect = useCallback(() => {
    console.log("Manual reconnect triggered")
    reconnectAttemptsRef.current = 0
    cleanup(true)
    // Small delay to ensure cleanup completes
    setTimeout(() => {
      if (isMountedRef.current) {
        connect()
      }
    }, 100)
  }, [cleanup, connect])

  // Handle page visibility changes (tab focus/unfocus)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isMountedRef.current) {
        // Tab became visible - check if we need to reconnect
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          console.log("Tab visible - checking connection...")
          reconnectAttemptsRef.current = 0 // Reset attempts on tab focus
          connect()
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [connect])

  // Handle online/offline events
  useEffect(() => {
    const handleOnline = () => {
      if (isMountedRef.current) {
        console.log("Network online - reconnecting...")
        reconnectAttemptsRef.current = 0
        connect()
      }
    }

    const handleOffline = () => {
      console.log("Network offline")
      setError("Network offline")
      setIsConnected(false)
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [connect])

  // Main effect for connection lifecycle
  useEffect(() => {
    // Mark as mounted
    isMountedRef.current = true

    // Small delay to handle React StrictMode double-mount
    // In StrictMode, React unmounts and remounts immediately
    // This delay ensures we don't start connecting during the unmount phase
    const connectTimeout = setTimeout(() => {
      if (isMountedRef.current) {
        connect()
      }
    }, 50)

    return () => {
      console.log("WebSocket hook unmounting")
      clearTimeout(connectTimeout)
      isMountedRef.current = false
      cleanup(true)
    }
  }, [connect, cleanup])

  return {
    data,
    isConnected,
    error,
    reconnect,
    signalHistory,
  }
}
