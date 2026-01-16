import type { IndicatorConfig, Strategy, MarketData } from "../interfaces/types"

export const STRATEGY: Strategy = {
  PHI_SIGMA_THRESHOLD: 4.0,
  DIRECTIONAL_THRESHOLD: 0.5,
}

// Trading signal thresholds (matches Python signal_generator.py)
export const TRADING_RULES = {
  STOP_LOSS_PCT: 0.0010,   // 0.10% Stop-Loss
  TAKE_PROFIT_PCT: 0.0005, // 0.05% Take-Profit
}

export const AVAILABLE_INDICATORS: IndicatorConfig[] = [
  {
    id: "directional_indicator",
    label: "DIRECTIONAL",
    friendlyName: "Market Direction",
    getValue: (row: MarketData) => row.directional_indicator ?? null,
    min: -1.0,
    max: 1.0,
    greenMin: 0.5,
    greenMax: 1.0,
    redMin: -1.0,
    redMax: -0.5,
    type: "line",
  },
  {
    id: "phi_sigma",
    label: "Φσ",
    friendlyName: "Phi Sigma (Volatility Z-Score)",
    getValue: (row: MarketData) => row.phi_sigma ?? null,
    min: -5,
    max: 5,
    greenMin: 4.0,
    greenMax: 5.0,
    redMin: -5.0,
    redMax: -4.0,
    type: "line",
  },
  {
    id: "svc_delta_pct",
    label: "SVC Δ",
    friendlyName: "SVC Delta (Percentile)",
    getValue: (row: MarketData) => row.svc_delta_pct ?? null,
    min: 0,
    max: 1.0,
    greenMin: 0.95,
    greenMax: 1.0,
    redMin: 0,
    redMax: 0.05,
    type: "line",
  },
  {
    id: "tf_crit",
    label: "TF CRIT",
    friendlyName: "Timeframe Critical",
    getValue: (row: MarketData) => row.tf_crit ?? null,
    type: "number",
  },
  {
    id: "cvd_pct",
    label: "CVD %",
    friendlyName: "CVD Percentile Rank",
    getValue: (row: MarketData) => row.cvd_pct ?? null,
    min: 0,
    max: 1.0,
    greenMin: 0.7,
    greenMax: 1.0,
    redMin: 0,
    redMax: 0.3,
    type: "line",
  },
  {
    id: "tvi_reversal_flag",
    label: "TVI REV",
    friendlyName: "TVI Reversal Flag",
    getValue: (row: MarketData) => row.tvi_reversal_flag ?? null,
    type: "number",
  },
]
