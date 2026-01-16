# Gestalt Signal Engine Dashboard

Real-time market intelligence dashboard for the Gestalt trading system.

## Architecture

### Directory Structure

```
client/
├── src/
│   ├── interfaces/        # TypeScript type definitions
│   │   └── types.ts
│   ├── hooks/            # Custom React hooks
│   │   └── useWebSocket.ts
│   ├── config/           # Configuration and constants
│   │   └── indicators.ts
│   ├── styles/           # CSS and animations
│   │   └── animations.css
│   ├── components/       # Reusable components (future)
│   └── App.tsx           # Main application component
├── package.json
└── README.md
```

### WebSocket Connection

The dashboard connects to the Python backend via WebSocket on `ws://localhost:8765`.

**Data Flow:**
1. Python backend computes market indicators in realtime
2. Data is broadcasted via WebSocket to all connected clients
3. React frontend receives and displays data with animations

### Key Features

- **Real-time Updates**: Live market data streaming via WebSocket
- **Indicator Visualization**: Configurable indicators with line charts and numeric displays
- **Buy Signal Detection**: Automatic detection based on Phi Sigma and Directional indicators
- **Drag & Drop**: Reorder indicators on the dashboard
- **Responsive Animations**: Visual feedback for data changes

## Running the Dashboard

### Prerequisites

- Node.js 16+ and npm/yarn
- Python backend running in realtime mode with WebSocket enabled

### Installation

```bash
cd client
npm install
```

### Development

```bash
npm run dev
```

The dashboard will connect to `ws://localhost:8765` for real-time data.

### Production Build

```bash
npm run build
```

## Configuration

### Indicators

Indicators are configured in `src/config/indicators.ts`. Each indicator has:

- `id`: Unique identifier matching backend data keys
- `label`: Display label
- `friendlyName`: Full name for tooltips
- `type`: "line" (with visualization) or "number" (numeric display)
- `min/max`: Range for line charts
- `targetMin/targetMax`: Target range highlighting
- `greenMin/greenMax`: Green zone highlighting
- `redMin/redMax`: Red zone highlighting

### Strategy

Trading strategy thresholds are defined in `src/config/indicators.ts`:

```typescript
export const STRATEGY = {
  PHI_SIGMA_THRESHOLD: 4.0,
  DIRECTIONAL_THRESHOLD: 0.5,
}
```

## WebSocket API

### Message Format

**Connection:**
```json
{
  "type": "connection",
  "status": "connected",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "message": "Connected to Gestalt Signal Engine"
}
```

**Market Data:**
```json
{
  "type": "market_data",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "data": {
    "timestamp": "2025-01-01T12:00:00",
    "close": 98765.4,
    "volume": 1234567,
    "cvd_pct": 0.65,
    "atr_14": 245.8,
    "tvi": 0.42,
    "svc_delta_pct": 0.48,
    "phi_sigma": 4.2,
    "tf_mod": 0.78,
    "tf_crit": 1,
    "directional_indicator": 0.6
  }
}
```

## Development

### Adding New Indicators

1. Update `src/interfaces/types.ts` to include the new field in `MarketData`
2. Add indicator configuration to `src/config/indicators.ts`
3. Ensure Python backend broadcasts the new indicator value

### Customizing Styles

Animations and visual effects are in `src/styles/animations.css`.

## Troubleshooting

**WebSocket connection fails:**
- Ensure Python backend is running in realtime mode
- Verify WebSocket server is listening on `localhost:8765`
- Check browser console for connection errors

**No data displayed:**
- Verify WebSocket connection is established (check console)
- Ensure Python backend is receiving market data
- Check that indicator IDs match between frontend and backend
