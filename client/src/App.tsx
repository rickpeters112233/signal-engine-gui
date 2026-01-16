"use client"

import type React from "react"
import { useEffect, useState, useRef } from "react"

// Import from new modular structure
import type { MarketData, UpdatedItem } from "./interfaces/types"
import { useWebSocket } from "./hooks/useWebSocket"
import { STRATEGY, AVAILABLE_INDICATORS, TRADING_RULES } from "./config/indicators"
import { useAuth } from "./contexts/AuthContext"
import "./styles/animations.css"

// Trade history entry
interface TradeEntry {
  timestamp: string
  signal: string
  price: number
  pnl_pct?: number
}

function HorizontalLineIndicator({
  label,
  friendlyName,
  value,
  min,
  max,
  targetMin,
  targetMax,
  redMin,
  redMax,
  greenMin,
  greenMax,
  className,
  isHighlighted,
  onRemove,
}: {
  label: string
  friendlyName: string
  value: number
  min: number
  max: number
  targetMin?: number
  targetMax?: number
  redMin?: number
  redMax?: number
  greenMin?: number
  greenMax?: number
  className?: string
  isHighlighted?: boolean
  onRemove?: () => void
}) {
  const isInTarget = targetMin !== undefined && targetMax !== undefined && value >= targetMin && value <= targetMax
  const isInRed = redMin !== undefined && redMax !== undefined && value >= redMin && value <= redMax
  const isInGreen = greenMin !== undefined && greenMax !== undefined && value >= greenMin && value <= greenMax

  const dotColor = isInTarget || isInGreen ? "#00FF88" : isInRed ? "#FF4444" : "#FFFFFF"
  const textColor = isHighlighted ? "#00FF88" : isInTarget || isInGreen ? "#00FF88" : isInRed ? "#FF4444" : "#FFFFFF"

  const percentage = ((value - min) / (max - min)) * 100
  const clampedPercentage = Math.max(0, Math.min(100, percentage))

  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", label)}
      style={{
        position: "relative",
        border: isHighlighted ? "2px solid #00FF88" : "2px solid rgba(255, 255, 255, 0.2)",
        padding: "30px",
        backgroundColor: isHighlighted ? "rgba(0, 255, 136, 0.1)" : "rgba(0, 0, 0, 0.5)",
        textAlign: "center",
        cursor: "grab",
        boxShadow: isHighlighted ? "0 0 20px rgba(0, 255, 136, 0.3)" : "none",
        transition: "all 0.3s ease",
      }}
    >
      {onRemove && (
        <button
          onClick={onRemove}
          style={{
            position: "absolute",
            top: "8px",
            right: "8px",
            background: "rgba(255, 68, 68, 0.2)",
            border: "1px solid #FF4444",
            color: "#FF4444",
            width: "24px",
            height: "24px",
            borderRadius: "50%",
            cursor: "pointer",
            fontSize: "14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
          }}
        >
          ×
        </button>
      )}
      <div style={{ fontSize: "1.5em", marginBottom: "5px", opacity: 0.7, letterSpacing: "2px", color: textColor }}>
        {label}
      </div>
      <div style={{ fontSize: "0.8em", marginBottom: "15px", opacity: 0.5, color: textColor }}>{friendlyName}</div>

      <div style={{ padding: "20px 10px" }}>
        <div style={{ position: "relative", height: "40px", display: "flex", alignItems: "center" }}>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              height: "4px",
              backgroundColor: "rgba(255, 255, 255, 0.2)",
              borderRadius: "2px",
            }}
          />

          {targetMin !== undefined && targetMax !== undefined && (
            <div
              style={{
                position: "absolute",
                left: `${((targetMin - min) / (max - min)) * 100}%`,
                width: `${((targetMax - targetMin) / (max - min)) * 100}%`,
                height: "4px",
                backgroundColor: "rgba(0, 255, 136, 0.3)",
                borderRadius: "2px",
              }}
            />
          )}

          {redMin !== undefined && redMax !== undefined && (
            <div
              style={{
                position: "absolute",
                left: `${((redMin - min) / (max - min)) * 100}%`,
                width: `${((redMax - redMin) / (max - min)) * 100}%`,
                height: "4px",
                backgroundColor: "rgba(255, 68, 68, 0.3)",
                borderRadius: "2px",
              }}
            />
          )}

          {greenMin !== undefined && greenMax !== undefined && (
            <div
              style={{
                position: "absolute",
                left: `${((greenMin - min) / (max - min)) * 100}%`,
                width: `${((greenMax - greenMin) / (max - min)) * 100}%`,
                height: "4px",
                backgroundColor: "rgba(0, 255, 136, 0.3)",
                borderRadius: "2px",
              }}
            />
          )}

          <div
            style={{
              position: "absolute",
              left: `${clampedPercentage}%`,
              transform: "translateX(-50%)",
              width: "16px",
              height: "16px",
              borderRadius: "50%",
              backgroundColor: dotColor,
              border: "2px solid rgba(0, 0, 0, 0.8)",
              boxShadow: `0 0 10px ${dotColor}`,
              zIndex: 2,
            }}
            className={className}
          />
        </div>

        <div style={{ fontSize: "1.8em", fontWeight: "bold", color: textColor, marginTop: "15px" }}>
          {value.toFixed(2)}
        </div>
      </div>
    </div>
  )
}

function MetricBox({
  label,
  friendlyName,
  value,
  color,
  className,
  isHighlighted,
  onRemove,
}: {
  label: string
  friendlyName: string
  value: string
  color: string
  className: string
  isHighlighted?: boolean
  onRemove?: () => void
}) {
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", label)}
      style={{
        position: "relative",
        border: isHighlighted ? "2px solid #00FF88" : "2px solid rgba(255, 255, 255, 0.2)",
        padding: "30px",
        backgroundColor: isHighlighted ? "rgba(0, 255, 136, 0.1)" : "rgba(0, 0, 0, 0.5)",
        textAlign: "center",
        cursor: "grab",
        boxShadow: isHighlighted ? "0 0 20px rgba(0, 255, 136, 0.3)" : "none",
        transition: "all 0.3s ease",
      }}
    >
      {onRemove && (
        <button
          onClick={onRemove}
          style={{
            position: "absolute",
            top: "8px",
            right: "8px",
            background: "rgba(128, 128, 128, 0.2)",
            border: "1px solid #808080",
            color: "#808080",
            width: "24px",
            height: "24px",
            borderRadius: "50%",
            cursor: "pointer",
            fontSize: "14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
          }}
        >
          ×
        </button>
      )}
      <div
        style={{
          fontSize: "1.5em",
          marginBottom: "5px",
          opacity: 0.7,
          letterSpacing: "2px",
          color: isHighlighted ? "#00FF88" : "#FFFFFF",
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "0.8em", marginBottom: "15px", opacity: 0.5 }}>{friendlyName}</div>
      <div
        style={{ fontSize: "3.5em", fontWeight: "bold", color: isHighlighted ? "#00FF88" : color, lineHeight: "1.2" }}
        className={className}
      >
        {value}
      </div>
    </div>
  )
}

function AddIndicatorCard({ onClick }: { onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        position: "relative",
        border: "2px dashed rgba(255, 255, 255, 0.3)",
        padding: "30px",
        backgroundColor: "rgba(0, 0, 0, 0.3)",
        textAlign: "center",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "200px",
        transition: "all 0.3s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#00FF88"
        e.currentTarget.style.backgroundColor = "rgba(0, 255, 136, 0.05)"
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.3)"
        e.currentTarget.style.backgroundColor = "rgba(0, 0, 0, 0.3)"
      }}
    >
      <div>
        <div style={{ fontSize: "4em", color: "rgba(255, 255, 255, 0.5)", marginBottom: "10px" }}>+</div>
        <div style={{ fontSize: "1em", color: "rgba(255, 255, 255, 0.5)", letterSpacing: "2px" }}>ADD INDICATOR</div>
      </div>
    </div>
  )
}

const CornerBrackets = ({ style }: { style?: React.CSSProperties }) => (
  <>
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "12px",
        height: "12px",
        borderTop: "2px solid #666666",
        borderLeft: "2px solid #666666",
        ...style,
      }}
    />
    <div
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: "12px",
        height: "12px",
        borderTop: "2px solid #666666",
        borderRight: "2px solid #666666",
        ...style,
      }}
    />
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        width: "12px",
        height: "12px",
        borderBottom: "2px solid #666666",
        borderLeft: "2px solid #666666",
        ...style,
      }}
    />
    <div
      style={{
        position: "absolute",
        bottom: 0,
        right: 0,
        width: "12px",
        height: "12px",
        borderBottom: "2px solid #666666",
        borderRight: "2px solid #666666",
        ...style,
      }}
    />
  </>
)

export default function App() {
  // Authentication
  const { address, disconnect } = useAuth()

  // WebSocket connection
  const { data: latest, isConnected, error: wsError, signalHistory } = useWebSocket()

  const [error, setError] = useState<string>("")
  const [isSignalHistoryExpanded, setIsSignalHistoryExpanded] = useState(false)
  const prevLatestRef = useRef<MarketData | null>(null)
  const [updatedCols, setUpdatedCols] = useState<UpdatedItem[]>([])
  const [recentCloses, setRecentCloses] = useState<number[]>([])
  const [recentVolumes, setRecentVolumes] = useState<number[]>([])

  const [activeIndicators, setActiveIndicators] = useState<string[]>([
    "directional_indicator",
    "phi_sigma",
    "svc_delta_pct",
    "tf_crit",
  ])
  const [tradeHistory, setTradeHistory] = useState<TradeEntry[]>([])
  const [showAddModal, setShowAddModal] = useState(false)
  const [draggedFrom, setDraggedFrom] = useState<number | null>(null)

  // Update data when WebSocket receives new data
  useEffect(() => {
    if (latest) {
      const prev = prevLatestRef.current
      const updated: UpdatedItem[] = []

      if (prev) {
        const columns = [
          "timestamp",
          "close",
          "volume",
          "cvd_pct",
          "atr_14",
          "tvi",
          "svc_delta_pct",
          "phi_sigma",
          "tf_mod",
          "tf_crit",
          "directional_indicator",
        ]
        columns.forEach((col) => {
          const oldVal = prev[col]
          const newVal = latest[col]
          if (newVal !== oldVal) {
            const item: UpdatedItem = { col }
            if (typeof oldVal === "number" && typeof newVal === "number") {
              if (newVal > oldVal) item.change = "up"
              else if (newVal < oldVal) item.change = "down"
            }
            updated.push(item)
          }
        })
      }

      setUpdatedCols(updated)
      setTimeout(() => setUpdatedCols([]), 500)

      // Track trade signals from the server
      if (latest.trading_signal && latest.trading_signal !== 'HOLD') {
        const timestamp = new Date().toLocaleTimeString("en-US", { hour12: false })
        const newTrade: TradeEntry = {
          timestamp,
          signal: latest.trading_signal,
          price: latest.close,
          pnl_pct: latest.pnl_pct,
        }
        setTradeHistory((prev) => {
          // Avoid duplicate entries for same timestamp
          if (prev.length === 0 || prev[0].timestamp !== timestamp) {
            return [newTrade, ...prev].slice(0, 20)
          }
          return prev
        })
      }

      prevLatestRef.current = latest

      // Update recent history (simulated for now - in real app, maintain buffer)
      if (latest.close) {
        setRecentCloses((prev) => [...prev.slice(-49), latest.close as number])
      }
      if (latest.volume) {
        setRecentVolumes((prev) => [...prev.slice(-49), latest.volume as number])
      }

      // Clear error on successful data
      setError("")
    }
  }, [latest])

  // Update error state from WebSocket
  useEffect(() => {
    if (wsError) {
      setError(wsError)
    } else if (!isConnected) {
      setError("Connecting to server...")
    } else {
      setError("") // Clear error when connected
    }
  }, [wsError, isConnected])

  // Helper to get signal color
  const getSignalColor = (signal: string | undefined) => {
    switch (signal) {
      case 'BUY': return '#00FF88'        // Green
      case 'SELL_PROFIT': return '#FF4444' // Red
      case 'SELL_STOP': return '#FF4444'   // Red
      case 'HOLD': return '#FFAA00'        // Mustard yellow (warning)
      default: return '#FFAA00'            // Mustard yellow for waiting state too
    }
  }

  // Helper to get signal display text
  const getSignalDisplay = (signal: string | undefined) => {
    switch (signal) {
      case 'BUY': return 'BUY'
      case 'SELL_PROFIT': return 'SELL (PROFIT)'
      case 'SELL_STOP': return 'SELL (STOP)'
      case 'HOLD': return 'HOLD'
      default: return 'WAITING'
    }
  }

  const getCellClass = (col: string) => {
    const item = updatedCols.find((u) => u.col === col)
    if (!item) return ""
    let classes = "jitter"
    if (item.change === "up") classes += " up"
    if (item.change === "down") classes += " down"
    return classes
  }

  const getValueColor = (col: string, value: any) => {
    if (col === "tvi") {
      if (value < 0.2) return "#CCCCCC"
      if (value > 0.7) return "#FF4444"
      return "#CCCCCC"
    }
    if (col === "svc_delta_pct") {
      if (value < 0.1) return "#FFFFFF"
      if (value > 0.9) return "#FF4444"
      return "#CCCCCC"
    }
    if (col === "cvd_pct") {
      if (value < 0.1) return "#FF4444"
      if (value > 0.9) return "#FFFFFF"
      return "#CCCCCC"
    }
    if (col === "directional_indicator") {
      if (value === 1.0) return "#FFFFFF"
      if (value === -1.0) return "#FF4444"
      return "#CCCCCC"
    }
    if (col === "tf_crit") {
      if (value === 0) return "#CCCCCC"
      if (value === 1) return "#FFAA00"
      return "#CCCCCC"
    }
    if (col === "phi_sigma") {
      if (value >= 4.0) return "#00FF88"  // Green for BUY condition
      if (value <= -4.0) return "#FF4444" // Red for extreme low volatility
      return "#CCCCCC"
    }
    return "#CCCCCC"
  }

  const renderLineGraph = (data: number[], color: string) => {
    if (data.length < 2) return null
    const width = 200
    const height = 50
    const maxVal = Math.max(...data)
    const minVal = Math.min(...data)
    const range = maxVal - minVal || 1
    const points = data
      .map((val, i) => {
        const x = (i / (data.length - 1)) * width
        const y = height - ((val - minVal) / range) * height
        return `${x},${y}`
      })
      .join(" ")
    return (
      <svg
        style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", opacity: 0.4 }}
        viewBox={`0 0 ${width} ${height}`}
      >
        <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
      </svg>
    )
  }

  // Check if we have an active trade signal (not HOLD)
  const hasActiveSignal = latest?.trading_signal && latest.trading_signal !== 'HOLD'
  const isInPosition = latest?.position_open === true

  // Helper function for CVD status color
  const getCvdColor = (status?: string) => {
    switch (status) {
      case 'BULLISH': return '#00FF88'  // Green
      case 'BEARISH': return '#FF4444'  // Red
      default: return '#FFAA00'         // Yellow/Neutral
    }
  }

  // Helper function for CVD momentum icon
  const getCvdMomentumIcon = (momentum?: string) => {
    switch (momentum) {
      case 'RISING': return '↑'
      case 'FALLING': return '↓'
      default: return '→'
    }
  }

  const handleDragStart = (index: number) => {
    setDraggedFrom(index)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (index: number) => {
    if (draggedFrom === null) return

    const newIndicators = [...activeIndicators]
    const [removed] = newIndicators.splice(draggedFrom, 1)
    newIndicators.splice(index, 0, removed)

    setActiveIndicators(newIndicators)
    setDraggedFrom(null)
  }

  return (
    <div
      style={{
        padding: "20px",
        backgroundColor: "#0a0a0a",
        color: "#CCCCCC",
        minHeight: "100vh",
        backgroundImage:
          "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255, 255, 255, 0.02) 2px, rgba(255, 255, 255, 0.02) 4px)",
        position: "relative",
      }}
    >
      <div className="scanline" />

      {/* Header */}
      <div
        style={{
          position: "relative",
          border: "1px solid #666666",
          padding: "20px",
          marginBottom: "20px",
          backgroundColor: "rgba(0, 0, 0, 0.6)",
        }}
      >
        <CornerBrackets />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1
              style={{ margin: 0, fontSize: "2em", letterSpacing: "4px", textTransform: "uppercase", color: "#00FF88" }}
            >
              [ GESTALT ]
            </h1>
            <div style={{ color: "#999999", fontSize: "0.9em", marginTop: "5px", opacity: 0.7 }}>
              TACTICAL MARKET INTELLIGENCE SYSTEM
            </div>
          </div>

          <div style={{ textAlign: "right" }}>
            {hasActiveSignal && (
              <div
                style={{
                  fontSize: "1.2em",
                  color: getSignalColor(latest?.trading_signal),
                  marginBottom: "10px",
                  fontWeight: "bold",
                  animation: "pulse 1s ease-in-out infinite",
                }}
              >
                {getSignalDisplay(latest?.trading_signal)}
              </div>
            )}
            {isInPosition && (
              <div style={{ fontSize: "0.9em", color: "#FFAA00", marginBottom: "5px" }}>
                IN POSITION @ {latest?.entry_price?.toFixed(2)}
              </div>
            )}
            <div style={{ fontSize: "0.85em", color: "#FFFFFF", marginBottom: "5px" }}>
              STATUS:{" "}
              <span className="status-pulse" style={{ color: isConnected ? "#00FF88" : "#FFAA00" }}>
                {String.fromCharCode(9679)} {isConnected ? "CONNECTED" : "CONNECTING"}
              </span>
            </div>
            {address && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "10px", marginTop: "8px" }}>
                <span style={{ fontSize: "0.75em", color: "#666666", fontFamily: "monospace" }}>
                  {address.slice(0, 6)}...{address.slice(-4)}
                </span>
                <button
                  onClick={disconnect}
                  style={{
                    padding: "4px 10px",
                    backgroundColor: "rgba(255, 68, 68, 0.1)",
                    border: "1px solid #FF4444",
                    color: "#FF4444",
                    fontSize: "0.7em",
                    letterSpacing: "1px",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(255, 68, 68, 0.2)"
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(255, 68, 68, 0.1)"
                  }}
                >
                  DISCONNECT
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div
          style={{
            position: "relative",
            border: "1px solid #FFAA00",
            padding: "15px",
            marginBottom: "20px",
            backgroundColor: "rgba(255, 170, 0, 0.1)",
          }}
        >
          <CornerBrackets style={{ borderColor: "#FFAA00" }} />
          <div style={{ color: "#FFAA00", fontSize: "1em" }}>⚠ {error}</div>
        </div>
      )}

      {/* SVC Extreme Floating Indicator - Precursor to TF_CRIT */}
      {latest && (latest.svc_extreme === 1 || latest.svc_extreme_sell === 1) && (
        <div style={{
          position: "fixed",
          top: "20px",
          right: "20px",
          padding: "15px 25px",
          backgroundColor: latest.svc_extreme === 1 ? "#00FF88" : "#FF4444",
          color: "#000",
          fontWeight: "bold",
          borderRadius: "4px",
          animation: "pulse 0.5s ease-in-out infinite",
          zIndex: 1000,
          boxShadow: `0 0 20px ${latest.svc_extreme === 1 ? "#00FF88" : "#FF4444"}`,
        }}>
          {latest.svc_extreme === 1 ? "EXTREME BUY PRESSURE" : "EXTREME SELL PRESSURE"}
        </div>
      )}

      {/* Trading Signal Panel */}
      {latest && (
        <div
          style={{
            position: "relative",
            border: `2px solid ${getSignalColor(latest.trading_signal)}`,
            padding: "20px",
            marginBottom: "20px",
            backgroundColor: `${getSignalColor(latest.trading_signal)}10`,
          }}
        >
          <CornerBrackets style={{ borderColor: getSignalColor(latest.trading_signal) }} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "20px" }}>
            <div>
              <div style={{ fontSize: "0.85em", marginBottom: "10px", color: getSignalColor(latest.trading_signal), letterSpacing: "2px" }}>
                ▸ TRADING SIGNAL
              </div>
              <div style={{
                fontSize: "2.5em",
                fontWeight: "bold",
                color: getSignalColor(latest.trading_signal),
                letterSpacing: "2px"
              }}>
                {getSignalDisplay(latest.trading_signal)}
              </div>
            </div>

            {isInPosition && (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.85em", color: "#FFAA00", marginBottom: "5px" }}>ENTRY PRICE</div>
                <div style={{ fontSize: "1.8em", color: "#FFAA00" }}>{latest.entry_price?.toFixed(2)}</div>
                <div style={{
                  fontSize: "1.2em",
                  marginTop: "5px",
                  color: (latest.pnl_pct ?? 0) >= 0 ? "#00FF88" : "#FF4444"
                }}>
                  P&L: {(latest.pnl_pct ?? 0) >= 0 ? "+" : ""}{(latest.pnl_pct ?? 0).toFixed(4)}%
                </div>
              </div>
            )}

            {isInPosition && (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.75em", color: "#666", marginBottom: "3px" }}>
                  TAKE PROFIT: {latest.take_profit_price?.toFixed(2)} (+{(TRADING_RULES.TAKE_PROFIT_PCT * 100).toFixed(2)}%)
                </div>
                <div style={{ fontSize: "0.75em", color: "#666" }}>
                  STOP LOSS: {latest.stop_loss_price?.toFixed(2)} (-{(TRADING_RULES.STOP_LOSS_PCT * 100).toFixed(2)}%)
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Major Event Warning Panel - Flashing */}
      {latest?.major_event_warning && (
        <div
          style={{
            position: "relative",
            border: "2px solid #FF4444",
            padding: "20px",
            marginBottom: "20px",
            backgroundColor: "rgba(255, 68, 68, 0.2)",
            animation: "flash-warning 1s ease-in-out infinite",
          }}
        >
          <CornerBrackets style={{ borderColor: "#FF4444" }} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: "0.85em", color: "#FF4444", letterSpacing: "2px" }}>
                MAJOR EVENT WARNING
              </div>
              <div style={{ fontSize: "2em", fontWeight: "bold", color: "#FF4444" }}>
                {latest.warning_countdown ?? 10} MIN.
              </div>
            </div>
            <div style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
              border: "3px solid #FF4444",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              animation: "pulse 0.5s ease-in-out infinite",
            }}>
              <span style={{ color: "#FF4444", fontSize: "0.8em", fontWeight: "bold" }}>FLASH</span>
            </div>
          </div>
        </div>
      )}

      {/* CVD Status Panel with Predicted Direction and Minor Event Indicator */}
      {latest && (
        <div
          style={{
            position: "relative",
            border: `2px solid ${getCvdColor(latest.cvd_status)}`,
            padding: "20px",
            marginBottom: "20px",
            backgroundColor: `${getCvdColor(latest.cvd_status)}15`,
          }}
        >
          <CornerBrackets style={{ borderColor: getCvdColor(latest.cvd_status) }} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "20px" }}>
            {/* CVD Status */}
            <div>
              <div style={{ fontSize: "0.85em", marginBottom: "10px", color: getCvdColor(latest.cvd_status), letterSpacing: "2px" }}>
                ▸ CVD STATUS
              </div>
              <div style={{
                fontSize: "2em",
                fontWeight: "bold",
                color: getCvdColor(latest.cvd_status)
              }}>
                {latest.cvd_status ?? 'NEUTRAL'}
              </div>
            </div>

            {/* Predicted Market Direction Indicator - Candle-like */}
            <div style={{
              position: "relative",
              padding: "20px 30px",
              backgroundColor: "rgba(0, 0, 0, 0.5)",
              border: "1px solid #666666",
              minWidth: "200px",
            }}>
              <CornerBrackets />
              <div style={{
                fontSize: "0.85em",
                color: getCvdColor(latest.cvd_status),
                marginBottom: "15px",
                letterSpacing: "2px",
                textAlign: "center",
                textTransform: "uppercase",
              }}>
                ▸ PREDICTED DIRECTION
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "20px", justifyContent: "center" }}>
                {/* Arrow pointing to candle */}
                <svg width="50" height="50" viewBox="0 0 50 50" style={{
                  transform: latest.cvd_status === 'BULLISH' ? "rotate(-45deg)" : latest.cvd_status === 'BEARISH' ? "rotate(45deg)" : "rotate(0deg)",
                  transition: "transform 0.3s ease",
                }}>
                  {/* Full arrow: shaft connected to arrowhead */}
                  <path
                    d="M8 25 L34 25 L34 19 L46 25 L34 31 L34 25"
                    fill={latest.cvd_status === 'BULLISH' ? "#00FF88" : latest.cvd_status === 'BEARISH' ? "#FF4444" : "#FFAA00"}
                    stroke={latest.cvd_status === 'BULLISH' ? "#00FF88" : latest.cvd_status === 'BEARISH' ? "#FF4444" : "#FFAA00"}
                    strokeWidth="2"
                    strokeLinejoin="round"
                  />
                </svg>
                {/* Candle-like indicator with glow */}
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  width: "28px",
                  boxShadow: latest.cvd_status === 'BULLISH'
                    ? "0 -5px 15px rgba(0, 255, 136, 0.4)"
                    : latest.cvd_status === 'BEARISH'
                      ? "0 5px 15px rgba(255, 68, 68, 0.4)"
                      : "none",
                }}>
                  {/* Green (bullish) portion */}
                  <div style={{
                    height: latest.cvd_status === 'BULLISH' ? "45px" : latest.cvd_status === 'NEUTRAL' ? "25px" : "12px",
                    backgroundColor: latest.cvd_status === 'BULLISH' ? "#00FF88" : "rgba(0, 255, 136, 0.4)",
                    borderRadius: "3px 3px 0 0",
                    transition: "all 0.3s ease",
                    border: "1px solid rgba(0, 255, 136, 0.6)",
                    borderBottom: "none",
                  }} />
                  {/* Red (bearish) portion */}
                  <div style={{
                    height: latest.cvd_status === 'BEARISH' ? "45px" : latest.cvd_status === 'NEUTRAL' ? "25px" : "12px",
                    backgroundColor: latest.cvd_status === 'BEARISH' ? "#FF4444" : "rgba(255, 68, 68, 0.4)",
                    borderRadius: "0 0 3px 3px",
                    transition: "all 0.3s ease",
                    border: "1px solid rgba(255, 68, 68, 0.6)",
                    borderTop: "none",
                  }} />
                </div>
                {/* CVD Percentile Value */}
                <div style={{ textAlign: "center" }}>
                  <div style={{
                    fontSize: "1.8em",
                    fontWeight: "bold",
                    color: getCvdColor(latest.cvd_status),
                    fontFamily: "monospace",
                  }}>
                    {typeof latest.cvd_pct === 'number' ? (latest.cvd_pct - 0.5).toFixed(2) : '0.00'}
                  </div>
                  <div style={{ fontSize: "0.7em", color: "#666", marginTop: "2px" }}>DELTA</div>
                </div>
              </div>
            </div>

            {/* Minor Event Indicator - Consider Purchase/Sale */}
            <div style={{
              position: "relative",
              padding: "20px 30px",
              backgroundColor: "rgba(0, 0, 0, 0.5)",
              border: `1px solid ${(latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                ? "#00FF88"
                : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                  ? "#FF4444"
                  : "#666666"
                }`,
              textAlign: "center",
              minWidth: "180px",
              transition: "border-color 0.3s ease",
            }}>
              <CornerBrackets style={{
                borderColor: (latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                  ? "#00FF88"
                  : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                    ? "#FF4444"
                    : "#666666"
              }} />
              <div style={{
                fontSize: "0.85em",
                color: (latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                  ? "#00FF88"
                  : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                    ? "#FF4444"
                    : "#888",
                marginBottom: "8px",
                letterSpacing: "2px",
                textTransform: "uppercase",
              }}>
                ▸ MINOR EVENT
              </div>
              <div style={{
                fontSize: "0.75em",
                color: "#666",
                marginBottom: "15px",
                letterSpacing: "1px",
              }}>
                CONSIDER PURCHASE/SALE
              </div>
              {/* Indicator circle with ring effect */}
              <div style={{
                position: "relative",
                width: "60px",
                height: "60px",
                margin: "0 auto",
              }}>
                {/* Outer ring */}
                <div style={{
                  position: "absolute",
                  top: "0",
                  left: "0",
                  width: "60px",
                  height: "60px",
                  borderRadius: "50%",
                  border: `2px solid ${(latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                    ? "rgba(0, 255, 136, 0.5)"
                    : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                      ? "rgba(255, 68, 68, 0.5)"
                      : "rgba(102, 102, 102, 0.3)"
                    }`,
                  transition: "all 0.3s ease",
                }} />
                {/* Inner filled circle */}
                <div style={{
                  position: "absolute",
                  top: "52%",
                  left: "53%",
                  transform: "translate(-50%, -50%)",
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  backgroundColor:
                    (latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                      ? "#00AA55"
                      : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                        ? "#AA2222"
                        : "#333333",
                  boxShadow:
                    (latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                      ? "0 0 20px rgba(0, 255, 136, 0.6), inset 0 0 15px rgba(0, 255, 136, 0.3)"
                      : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                        ? "0 0 20px rgba(255, 68, 68, 0.6), inset 0 0 15px rgba(255, 68, 68, 0.3)"
                        : "inset 0 0 10px rgba(0, 0, 0, 0.5)",
                  transition: "all 0.3s ease",
                }} />
              </div>
              {/* Status text below circle */}
              <div style={{
                marginTop: "12px",
                fontSize: "0.8em",
                fontWeight: "bold",
                color: (latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                  ? "#00FF88"
                  : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                    ? "#FF4444"
                    : "#666",
                letterSpacing: "1px",
              }}>
                {(latest.svc_overbought === 1 || (latest.cvd_status === 'BULLISH' && latest.cvd_momentum === 'RISING'))
                  ? "BUY SIGNAL"
                  : (latest.svc_oversold === 1 || (latest.cvd_status === 'BEARISH' && latest.cvd_momentum === 'FALLING'))
                    ? "SELL SIGNAL"
                    : "INACTIVE"}
              </div>
            </div>

            {/* Momentum */}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "0.85em", color: "#888", marginBottom: "5px" }}>MOMENTUM</div>
              <div style={{
                fontSize: "1.5em",
                fontWeight: "bold",
                color: getCvdColor(latest.cvd_status)
              }}>
                {getCvdMomentumIcon(latest.cvd_momentum)} {latest.cvd_momentum ?? 'FLAT'}
              </div>
            </div>

            {/* CVD Value */}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "0.85em", color: "#888", marginBottom: "5px" }}>CVD VALUE</div>
              <div style={{ fontSize: "1.2em", color: "#CCCCCC" }}>
                {typeof latest.cvd === 'number' ? latest.cvd.toLocaleString() : 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Server-Side Signal History (Expandable) */}
      {signalHistory.length > 0 && (
        <div
          style={{
            position: "relative",
            border: "1px solid #666666",
            padding: "15px 20px",
            marginBottom: "20px",
            backgroundColor: "rgba(0, 0, 0, 0.6)",
          }}
        >
          <CornerBrackets />
          <div
            onClick={() => setIsSignalHistoryExpanded(!isSignalHistoryExpanded)}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <div style={{ fontSize: "0.85em", color: "#00FF88", letterSpacing: "2px" }}>
              {isSignalHistoryExpanded ? "▾" : "▸"} SIGNAL HISTORY ({signalHistory.length})
            </div>
            <div style={{ fontSize: "0.75em", color: "#666666" }}>
              Last 72 hours • Max 500 signals
            </div>
          </div>

          {isSignalHistoryExpanded && (
            <div style={{ marginTop: "15px" }}>
              {/* Header Row */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "100px 80px 90px 100px 80px 80px 80px 70px",
                  gap: "10px",
                  padding: "10px",
                  backgroundColor: "rgba(0, 255, 136, 0.1)",
                  borderBottom: "1px solid rgba(0, 255, 136, 0.3)",
                  fontSize: "0.75em",
                  fontWeight: "bold",
                  color: "#00FF88",
                  letterSpacing: "1px",
                }}
              >
                <div>TIMESTAMP</div>
                <div>SIGNAL</div>
                <div>CONTRACT</div>
                <div style={{ textAlign: "right" }}>PRICE</div>
                <div style={{ textAlign: "right" }}>DIR</div>
                <div style={{ textAlign: "right" }}>Φσ</div>
                <div style={{ textAlign: "right" }}>SVC Δ</div>
                <div style={{ textAlign: "right" }}>TF</div>
              </div>

              {/* Data Rows */}
              <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                {signalHistory.map((signal, index) => (
                  <div
                    key={`${signal.recorded_at}-${index}`}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "100px 80px 90px 100px 80px 80px 80px 70px",
                      gap: "10px",
                      padding: "8px 10px",
                      backgroundColor: index % 2 === 0 ? "rgba(0, 0, 0, 0.3)" : "rgba(0, 0, 0, 0.5)",
                      borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                      fontSize: "0.8em",
                    }}
                  >
                    <div style={{ color: "#888888" }}>
                      {signal.timestamp || new Date(signal.recorded_at).toLocaleTimeString("en-US", { hour12: false })}
                    </div>
                    <div
                      style={{
                        color: signal.signal === "BUY" ? "#00FF88" : "#FF4444",
                        fontWeight: "bold",
                      }}
                    >
                      {signal.signal === "BUY" ? "BUY" : signal.signal === "SELL_PROFIT" ? "SELL TP" : "SELL SL"}
                    </div>
                    <div style={{ color: "#00FF88" }}>{signal.symbol || "N/A"}</div>
                    <div style={{ textAlign: "right", color: "#CCCCCC" }}>
                      {typeof signal.price === "number" ? signal.price.toFixed(2) : "N/A"}
                    </div>
                    <div
                      style={{
                        textAlign: "right",
                        color:
                          signal.directional_indicator >= 0.5
                            ? "#00FF88"
                            : signal.directional_indicator <= -0.5
                              ? "#FF4444"
                              : "#CCCCCC",
                      }}
                    >
                      {typeof signal.directional_indicator === "number"
                        ? signal.directional_indicator.toFixed(2)
                        : "N/A"}
                    </div>
                    <div
                      style={{
                        textAlign: "right",
                        color: signal.phi_sigma >= 4.0 ? "#00FF88" : "#CCCCCC",
                      }}
                    >
                      {typeof signal.phi_sigma === "number" ? signal.phi_sigma.toFixed(2) : "N/A"}
                    </div>
                    <div style={{ textAlign: "right", color: "#CCCCCC" }}>
                      {typeof signal.svc_delta_pct === "number" ? signal.svc_delta_pct.toFixed(2) : "N/A"}
                    </div>
                    <div
                      style={{
                        textAlign: "right",
                        color: signal.tf_crit === 1 ? "#FFAA00" : "#CCCCCC",
                      }}
                    >
                      {typeof signal.tf_crit === "number" ? signal.tf_crit : "N/A"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Trade History */}
      {tradeHistory.length > 0 && (
        <div
          style={{
            position: "relative",
            border: "1px solid #666666",
            padding: "20px",
            marginBottom: "20px",
            backgroundColor: "rgba(0, 0, 0, 0.6)",
          }}
        >
          <CornerBrackets />
          <div style={{ fontSize: "0.85em", marginBottom: "15px", color: "#00FF88", letterSpacing: "2px" }}>
            ▸ TRADE HISTORY
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "150px", overflowY: "auto" }}>
            {tradeHistory.map((trade, index) => (
              <div
                key={index}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  backgroundColor: `${getSignalColor(trade.signal)}15`,
                  border: `1px solid ${getSignalColor(trade.signal)}50`,
                  fontSize: "0.9em",
                }}
              >
                <span style={{ color: getSignalColor(trade.signal) }}>{trade.timestamp}</span>
                <span style={{ color: getSignalColor(trade.signal), fontWeight: "bold" }}>
                  {trade.signal}
                </span>
                <span style={{ color: "#CCCCCC" }}>
                  @ {trade.price.toFixed(2)}
                  {trade.pnl_pct !== undefined && trade.pnl_pct !== 0 && (
                    <span style={{ color: trade.pnl_pct >= 0 ? "#00FF88" : "#FF4444", marginLeft: "10px" }}>
                      ({trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(4)}%)
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {latest && (
        <div style={{ maxWidth: "100%" }}>
          {/* Primary Metrics */}
          <div
            style={{
              position: "relative",
              border: "1px solid #666666",
              padding: "20px",
              marginBottom: "20px",
              backgroundColor: "rgba(0, 0, 0, 0.6)",
            }}
          >
            <CornerBrackets />
            <div style={{ fontSize: "0.85em", marginBottom: "15px", color: "#00FF88", letterSpacing: "2px" }}>
              ▸ PRIMARY METRICS
            </div>
            <div style={{ display: "flex", gap: "20px", justifyContent: "space-between" }}>
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  border: "1px solid rgba(0, 255, 136, 0.3)",
                  padding: "20px",
                  backgroundColor: "rgba(0, 255, 136, 0.05)",
                }}
              >
                <div style={{ fontSize: "1em", marginBottom: "10px", opacity: 0.7, color: "#00FF88" }}>CONTRACT</div>
                <div
                  style={{
                    fontSize: "1.8em",
                    fontWeight: "bold",
                    color: "#00FF88",
                    letterSpacing: "1px",
                  }}
                >
                  {latest.symbol || "N/A"}
                </div>
              </div>
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  padding: "20px",
                  backgroundColor: "rgba(0, 0, 0, 0.4)",
                }}
              >
                <div style={{ fontSize: "1em", marginBottom: "10px", opacity: 0.7 }}>TIMESTAMP</div>
                <div
                  style={{
                    fontSize: "2.5em",
                    fontWeight: "bold",
                    color: getValueColor("timestamp", latest.timestamp),
                  }}
                  className={getCellClass("timestamp")}
                >
                  {latest.timestamp || "N/A"}
                </div>
              </div>
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  padding: "20px",
                  backgroundColor: "rgba(0, 0, 0, 0.4)",
                }}
              >
                {renderLineGraph(recentCloses.length > 0 ? recentCloses : [98000, 98200, 98500], "#CCCCCC")}
                <div
                  style={{ fontSize: "1em", marginBottom: "10px", opacity: 0.7, position: "relative", zIndex: 1 }}
                >
                  PRICE
                </div>
                <div
                  style={{
                    fontSize: "2.5em",
                    fontWeight: "bold",
                    color: getValueColor("close", latest.close),
                    position: "relative",
                    zIndex: 1,
                  }}
                  className={getCellClass("close")}
                >
                  {typeof latest.close === "number" ? latest.close.toFixed(1) : "N/A"}
                </div>
              </div>
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  padding: "20px",
                  backgroundColor: "rgba(0, 0, 0, 0.4)",
                }}
              >
                {renderLineGraph(recentVolumes.length > 0 ? recentVolumes : [1200000, 1250000, 1230000], "#CCCCCC")}
                <div
                  style={{ fontSize: "1em", marginBottom: "10px", opacity: 0.7, position: "relative", zIndex: 1 }}
                >
                  VOLUME
                </div>
                <div
                  style={{
                    fontSize: "2.5em",
                    fontWeight: "bold",
                    color: getValueColor("volume", latest.volume),
                    position: "relative",
                    zIndex: 1,
                  }}
                  className={getCellClass("volume")}
                >
                  {latest.volume ?? "N/A"}
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              position: "relative",
              border: "1px solid #666666",
              padding: "15px 20px",
              marginBottom: "20px",
              backgroundColor: "rgba(0, 0, 0, 0.6)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ fontSize: "0.85em", color: "#FFAA00", letterSpacing: "2px" }}>
              ▸ STRATEGY: BUY (Φσ≥{STRATEGY.PHI_SIGMA_THRESHOLD} & DIR≥{STRATEGY.DIRECTIONAL_THRESHOLD}) |
              TAKE PROFIT +{(TRADING_RULES.TAKE_PROFIT_PCT * 100).toFixed(2)}% |
              STOP LOSS -{(TRADING_RULES.STOP_LOSS_PCT * 100).toFixed(2)}%
            </div>
          </div>

          <div
            style={{
              position: "relative",
              border: "1px solid #666666",
              padding: "40px",
              marginBottom: "20px",
              backgroundColor: "rgba(0, 0, 0, 0.6)",
            }}
          >
            <CornerBrackets />
            <div
              style={{
                fontSize: "0.85em",
                marginBottom: "25px",
                color: "#00FF88",
                letterSpacing: "2px",
              }}
            >
              ▸ ACTIVE INDICATORS
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "30px",
                maxWidth: "1400px",
                margin: "0 auto",
              }}
            >
              {activeIndicators.map((indicatorId, index) => {
                const config = AVAILABLE_INDICATORS.find((ind) => ind.id === indicatorId)
                if (!config) return null

                const value = config.getValue(latest)
                const shouldHighlight =
                  (config.id === "phi_sigma" &&
                    typeof value === "number" &&
                    value >= STRATEGY.PHI_SIGMA_THRESHOLD) ||
                  (config.id === "directional_indicator" &&
                    typeof value === "number" &&
                    value >= STRATEGY.DIRECTIONAL_THRESHOLD)

                return (
                  <div
                    key={indicatorId}
                    draggable
                    onDragStart={() => handleDragStart(index)}
                    onDragOver={handleDragOver}
                    onDrop={() => handleDrop(index)}
                  >
                    {config.type === "line" && typeof value === "number" ? (
                      <HorizontalLineIndicator
                        label={config.label}
                        friendlyName={config.friendlyName}
                        value={value}
                        min={config.min!}
                        max={config.max!}
                        targetMin={config.targetMin}
                        targetMax={config.targetMax}
                        redMin={config.redMin}
                        redMax={config.redMax}
                        greenMin={config.greenMin}
                        greenMax={config.greenMax}
                        className={getCellClass(config.id)}
                        isHighlighted={shouldHighlight}
                        onRemove={() => setActiveIndicators(activeIndicators.filter((id) => id !== indicatorId))}
                      />
                    ) : (
                      <MetricBox
                        label={config.label}
                        friendlyName={config.friendlyName}
                        value={typeof value === "number" ? value.toFixed(1) : "N/A"}
                        color={getValueColor(config.id, value)}
                        className={getCellClass(config.id)}
                        isHighlighted={shouldHighlight}
                        onRemove={() => setActiveIndicators(activeIndicators.filter((id) => id !== indicatorId))}
                      />
                    )}
                  </div>
                )
              })}

              <AddIndicatorCard onClick={() => setShowAddModal(true)} />
            </div>
          </div>
        </div>
      )}

      {showAddModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setShowAddModal(false)}
        >
          <div
            style={{
              position: "relative",
              border: "2px solid #00FF88",
              padding: "30px",
              backgroundColor: "#0a0a0a",
              maxWidth: "500px",
              width: "90%",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <CornerBrackets style={{ borderColor: "#00FF88" }} />
            <div style={{ fontSize: "1.5em", marginBottom: "20px", color: "#00FF88", letterSpacing: "2px" }}>
              SELECT INDICATOR
            </div>
            <div
              style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "400px", overflowY: "auto" }}
            >
              {AVAILABLE_INDICATORS.filter((ind) => !activeIndicators.includes(ind.id)).map((indicator) => (
                <button
                  key={indicator.id}
                  onClick={() => {
                    setActiveIndicators([...activeIndicators, indicator.id])
                    setShowAddModal(false)
                  }}
                  style={{
                    padding: "15px",
                    backgroundColor: "rgba(0, 255, 136, 0.1)",
                    border: "1px solid rgba(0, 255, 136, 0.3)",
                    color: "#00FF88",
                    cursor: "pointer",
                    fontSize: "1em",
                    textAlign: "left",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(0, 255, 136, 0.2)"
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(0, 255, 136, 0.1)"
                  }}
                >
                  <div style={{ fontWeight: "bold", marginBottom: "5px" }}>{indicator.label}</div>
                  <div style={{ fontSize: "0.85em", opacity: 0.7 }}>{indicator.friendlyName}</div>
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowAddModal(false)}
              style={{
                marginTop: "20px",
                padding: "10px 20px",
                backgroundColor: "rgba(255, 255, 255, 0.1)",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                color: "#FFFFFF",
                cursor: "pointer",
                width: "100%",
              }}
            >
              CANCEL
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
