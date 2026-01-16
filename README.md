# Gestalt Signal Engine

Real-time market data pipeline with technical indicator computation and live dashboard visualization.

## Overview

The Signal Engine fetches market data from trading APIs, computes proprietary technical indicators, and streams results to a React dashboard via WebSocket.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Provider  │────▶│  Signal Engine   │────▶│ React Dashboard │
│  (TopstepX)     │     │  (Python)        │     │ (WebSocket)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌───────────────┐
                        │  Indicators   │
                        │  - Phi Sigma  │
                        │  - TVI        │
                        │  - TF Mod     │
                        │  - Directional│
                        └───────────────┘
```

## Quick Start

### 1. Setup Environment

```bash
# Clone and enter directory
cd signal-engine

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your API credentials
```

### 2. Start the Backend

```bash
python3 main.py --contract_id CON.F.US.GCE.Z25 --mode realtime --provider topstepx
```

### 3. Start the Dashboard

```bash
cd client
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Project Structure

```
signal-engine/
├── api/                          # Data provider abstraction layer
│   ├── base.py                   # Abstract DataProvider class
│   ├── topstep.py                # TopstepX API (REST polling)
│   ├── massive.py                # Massive.io API
│   ├── file.py                   # File-based provider
│   ├── factory.py                # Provider factory
│   └── websocket_server.py       # WebSocket broadcaster
│
├── features/                     # Technical indicator modules
│   ├── features_phi.py           # Phi Sigma (volatility regime)
│   ├── features_tf.py            # Time-Flow modulation
│   ├── features_tvi.py           # Time-Value Index
│   ├── features_svc.py           # Signed Volume Change
│   ├── features_directional.py   # Directional indicator
│   └── score_da_tem_e.py         # DA-TEM-E score
│
├── tribernachi/                  # Compression & encoding
│   ├── constants.py              # Mathematical constants
│   ├── tgc_encoder.py            # Tribernachi Geometric Compression
│   ├── tvc_versioning.py         # T-Hex cache versioning
│   └── tensor_recurrence.py      # Tensor recurrence engine
│
├── cache/                        # Caching layer
│   └── feature_cache_wrapper.py  # TGC-enhanced caching
│
├── orchestration/                # Pipeline coordination
│   └── pipeline_orchestrator.py  # Main pipeline logic
│
├── client/                       # React dashboard
│   └── src/
│       ├── App.tsx               # Main dashboard component
│       ├── hooks/useWebSocket.ts # WebSocket connection hook
│       ├── config/indicators.ts  # Indicator configuration
│       └── interfaces/types.ts   # TypeScript definitions
│
├── main.py                       # CLI entry point
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment template
```

## Usage

### Command Line Options

```bash
python3 main.py [OPTIONS]

Options:
  --contract_id   Contract ID (e.g., CON.F.US.GCE.Z25)
  --ticker        Ticker symbol (e.g., XAUUSD) - alternative to contract_id
  --mode          Operating mode: batch | realtime (default: batch)
  --provider      Data provider: topstepx | massive | file (default: topstepx)
  --hours         Hours of historical data (default: 24)
  --no-websocket  Disable WebSocket server in realtime mode
```

### Examples

```bash
# Real-time Gold futures with dashboard
python3 main.py --contract_id CON.F.US.GCE.Z25 --mode realtime --provider topstepx

# Batch processing (no streaming)
python3 main.py --contract_id CON.F.US.GCE.Z25 --mode batch --hours 8

# Different contract (E-mini S&P 500)
python3 main.py --contract_id CON.F.US.ESE.Z25 --mode realtime --provider topstepx
```

## Configuration

### Environment Variables (.env)

```bash
# TopstepX API (primary provider)
TOPSTEP_APIKEY=your_api_key
TOPSTEP_USERNAME=your_username
TOPSTEP_PASSWORD=your_password
TOPSTEP_CURRENT_TOKEN=          # Cached JWT token (auto-updated)

# Massive.io API (alternative provider)
MASSIVE_API_KEY=your_api_key

# File provider
DATA_DIR=./data

# Cache settings
CACHE_DIR=./cache_data
ENABLE_COMPRESSION=true
```

### TopstepX Contract IDs

| Symbol | Contract ID | Description |
|--------|-------------|-------------|
| GC | `CON.F.US.GCE.Z25` | Gold Futures Dec 2025 |
| ES | `CON.F.US.ESE.Z25` | E-mini S&P 500 Dec 2025 |
| NQ | `CON.F.US.NQE.Z25` | E-mini Nasdaq Dec 2025 |
| CL | `CON.F.US.CLE.Z25` | Crude Oil Dec 2025 |

## Technical Indicators

| Indicator | Range | Description |
|-----------|-------|-------------|
| **Phi Sigma** | 0-10 | Volatility regime score using golden ratio |
| **Directional** | -1 to 1 | Market direction with momentum fade |
| **TVI** | -1 to 1 | Time-Value Index (price-volume momentum) |
| **TF Mod** | 0-5 | Time-Flow compression score |
| **SVC Delta** | -1 to 1 | Signed Volume Change |
| **CVD %** | -100 to 100 | Cumulative Volume Delta percentage |

### Buy Signal Detection

The dashboard triggers a buy signal when:
- `phi_sigma >= 4.0` (high volatility regime)
- `directional_indicator >= 0.5` (strong bullish conviction)

## Architecture

### Data Flow

1. **Data Provider** polls market data (3-second intervals)
2. **Pipeline Orchestrator** computes all technical indicators
3. **WebSocket Server** broadcasts to connected clients
4. **React Dashboard** displays real-time updates

### Error Handling

The TopstepX provider includes robust error handling:
- Automatic retry with exponential backoff (up to 5 retries)
- SSL error recovery with session reset
- Token refresh on authentication failures
- Adaptive polling interval during errors

### Caching

Features are cached using Tribernachi Geometric Compression (TGC):
- 20-30% compression over standard methods
- Version-aware cache invalidation via T-Hex codes
- Dual-layer caching (memory + file)

## Development

### Running Tests

```bash
python3 -m pytest tests/
```

### Adding New Indicators

1. Create module in `features/features_*.py`
2. Export from `features/__init__.py`
3. Add to `pipeline_orchestrator.py` computation
4. Update `client/src/config/indicators.ts` for dashboard display
5. Add TypeScript type in `client/src/interfaces/types.ts`

## Troubleshooting

### "Connection timeout - is the server running?"
- Ensure TopstepX credentials are correct in `.env`
- Check if markets are open (futures have trading hours)
- Verify network connectivity

### Dashboard shows "CONNECTING"
- Confirm Python backend is running in realtime mode
- Check that port 8765 is not blocked
- Look for "WebSocket server started" in backend logs

- graph TD
    A[TopstepX API / Massive.io] -->|Market Data| B(Pipeline Orchestrator)
    B --> C{Indicator Engine}
    C -->|Phi Sigma| D[Feature Cache]
    C -->|TVI / SVC| D
    D --> E[TGC Encoder]
    E --> F[WebSocket Server]
    F --> G[React Dashboard]
    E --> H[PyQt Desktop GUI]
Conversation with Gemini
make mee a completer read me file for this repo, include schematic, feature and functionality

Here is a comprehensive README for your Signal Engine GUI repository. I have structured it to be professional, scannable, and informative, incorporating the technical details found in your codebase.

Gestalt Signal Engine (GUI Version)
The Gestalt Signal Engine is a high-performance, real-time market data pipeline designed for professional traders. It integrates directly with the TopstepX API to fetch live market data, compute proprietary technical indicators using mathematical constants like the Golden Ratio, and visualize results through a modern PyQt-based Desktop GUI or a React Dashboard.

🏗 System Architecture
The engine follows a modular orchestration pattern to ensure low-latency data processing and high reliability.

Code snippet
graph TD
    A[TopstepX API / Massive.io] -->|Market Data| B(Pipeline Orchestrator)
    B --> C{Indicator Engine}
    C -->|Phi Sigma| D[Feature Cache]
    C -->|TVI / SVC| D
    D --> E[TGC Encoder]
    E --> F[WebSocket Server]
    F --> G[React Dashboard]
    E --> H[PyQt Desktop GUI]
✨ Key Features
Real-Time Data Streaming: Seamless integration with TopstepX for live futures data (Gold, S&P 500, Nasdaq, Crude Oil).

Proprietary Indicators: Specialized signal modules including Phi Sigma (volatility regime) and Tribernachi-based momentum indicators.

TGC Compression: Uses Tribernachi Geometric Compression to reduce data overhead by 20-30% for faster transmission.

Dual Interface: Choose between a lightweight React web dashboard or a robust PyQt desktop application.

Robust Error Handling: Features exponential backoff, session recovery, and automated token refreshing for 24/7 stability.

📊 Proprietary Indicators & Logic
The engine calculates several advanced metrics to identify high-conviction trading opportunities:

Indicator	Range	Description
Phi Sigma	0 to 10	Volatility regime score based on the golden ratio (ϕ).
Directional	-1 to 1	Market direction filtered with momentum fade logic.
TVI	-1 to 1	Time-Value Index: measures price-volume momentum.
SVC Delta	-1 to 1	Signed Volume Change: tracks aggressive buying/selling.
Buy Signal Detection Logic
A Buy Signal is triggered on the dashboard when:

Phi Sigma ≥4.0 (Indicates a high-volatility regime).

Directional Indicator ≥0.5 (Indicates strong bullish conviction).

🚀 Quick Start
1. Environment Setup
Bash
# Clone the repository
git clone https://github.com/rickpeters112233/signal-engine-gui.git
cd signal-engine-gui

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
2. Configuration
Rename .env.example to .env and add your Topstep credentials:

Code snippet
TOPSTEP_USERNAME=your_username
TOPSTEP_PASSWORD=your_password
TOPSTEP_APIKEY=your_api_key
3. Launching the GUI
To start the desktop interface:

Bash
python3 main_gui.py
To run the backend with the React dashboard:

Bash
python3 main.py --mode realtime --provider topstepx
🛠 Project Structure
api/: Data provider abstractions (Topstep, Massive, Websocket).

features/: The mathematical core (Phi Sigma, TVI, SVC, Directional logic).

tribernachi/: Compression and tensor recurrence engines.

orchestration/: Coordinates the flow from data ingestion to signal output.

client/: Source code for the React-based frontend.


