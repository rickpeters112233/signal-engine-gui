/**
 * Type definitions for Gestalt Signal Engine Dashboard
 */

export interface MarketData {
  timestamp: string
  symbol?: string
  close: number
  volume: number
  atr_14?: number
  tvi?: number
  phi_sigma?: number
  tf_mod?: number
  tf_crit?: number
  directional_indicator?: number

  // SVC Delta fields (enhanced with directional calculation)
  svc_delta?: number           // Raw directional delta value
  svc_delta_pct?: number       // Percentile rank (0-1)
  svc_extreme?: number         // Flag: 99th percentile (extreme buying)
  svc_overbought?: number      // Flag: 95th-99th percentile
  svc_oversold?: number        // Flag: 1st-5th percentile (climactic selling)
  svc_extreme_sell?: number    // Flag: below 1st percentile (extreme selling)

  // CVD (Cumulative Volume Delta) fields
  cvd?: number                 // Cumulative volume delta value
  cvd_pct?: number             // Percentile rank (0-1)
  cvd_status?: 'BULLISH' | 'BEARISH' | 'NEUTRAL'  // Current CVD direction
  cvd_momentum?: 'RISING' | 'FALLING' | 'FLAT'    // CVD momentum

  // TVI reversal flag
  tvi_reversal_flag?: number   // 0 or 1 (gated reversal signal)

  // Major Event Warning (precursor to tf_crit based on 99th percentile SVC)
  major_event_warning?: boolean
  warning_countdown?: number   // Minutes until predicted major event (default: 10)

  // Trading signal data
  trading_signal?: 'BUY' | 'SELL_PROFIT' | 'SELL_STOP' | 'HOLD'
  entry_price?: number
  position_open?: boolean
  pnl_pct?: number
  stop_loss_price?: number
  take_profit_price?: number
  [key: string]: any
}

export interface UpdatedItem {
  col: string
  change?: "up" | "down"
}

export interface BuySignal {
  timestamp: string
  phiSigma: number
  directional: number
}

export interface SignalHistoryItem {
  recorded_at: string
  signal: 'BUY' | 'SELL_PROFIT' | 'SELL_STOP'
  timestamp: string
  symbol: string
  price: number
  directional_indicator: number
  phi_sigma: number
  svc_delta_pct: number
  tf_crit: number
}

export interface IndicatorConfig {
  id: string
  label: string
  friendlyName: string
  getValue: (row: MarketData) => number | string | null
  min?: number
  max?: number
  targetMin?: number
  targetMax?: number
  redMin?: number
  redMax?: number
  greenMin?: number
  greenMax?: number
  type: "line" | "number"
}

export interface Strategy {
  PHI_SIGMA_THRESHOLD: number
  DIRECTIONAL_THRESHOLD: number
}

export interface WebSocketMessage {
  type: string
  timestamp: string
  data?: MarketData
  status?: string
  message?: string
  signal_history?: SignalHistoryItem[]
}

export interface TimeProgress {
  min1: number
  min5: number
  min15: number
}
