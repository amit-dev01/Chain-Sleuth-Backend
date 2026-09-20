# ⛓️ ChainSleuth — Backend

> **Blockchain forensics and investigation platform for law enforcement.**  
> Trace crypto transactions, detect money-laundering typologies, attribute addresses to exchanges (VASPs), and generate court-ready legal documents — all through a single async FastAPI service.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Core Algorithms](#core-algorithms)
- [Legal Modules](#legal-modules)
- [Data Flow](#data-flow)
- [Development](#development)

---

## Overview

ChainSleuth Backend is a **Python 3.12 async FastAPI** service that provides the investigative engine for the ChainSleuth platform. It enables law enforcement officers to:

- **Trace** a suspect crypto wallet across multiple hops using a value-weighted BFS graph traversal
- **Detect** crime typologies such as peeling chains, first-funder matches, and fan-out mixing
- **Attribute** wallet addresses to known VASPs (exchanges) via a hot-wallet step-back algorithm
- **Parse** raw FIR/complaint text into structured trace parameters using Google Gemini AI
- **Generate** legally-formatted PDFs — Section 94 BNSS notices with Section 63 BSA SHA-256 evidence hash stamps

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ChainSleuth Backend                        │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐  │
│  │ FastAPI  │   │  Engine  │   │   VASP   │   │   Legal    │  │
│  │  Routes  │──▶│  (BFS +  │──▶│Attribution│──▶│  Module   │  │
│  │          │   │Typology) │   │ Step-Back│   │(PDF+Hash)  │  │
│  └──────────┘   └──────────┘   └──────────┘   └────────────┘  │
│       │               │                                         │
│       ▼               ▼                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Gemini  │    │ TronGrid │    │  Neo4j   │    │  Redis   │  │
│  │   AI    │    │REST API  │    │  Graph   │    │  Cache   │  │
│  └─────────┘    └──────────┘    └──────────┘    └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
backend/
├── .env.example                  # Environment variable template
├── requirements.txt              # Pinned Python dependencies
├── static/
│   └── notices/                  # Generated legal notice PDFs (served via /static)
└── app/
    ├── main.py                   # FastAPI app, lifespan, CORS, middleware, routing
    ├── core/
    │   ├── config.py             # Pydantic BaseSettings (env var management)
    │   └── database.py           # Neo4j driver pool + Redis client + Cypher helpers
    ├── models/
    │   └── schemas.py            # All Pydantic v2 DTOs (request/response models)
    ├── api/
    │   ├── routes_trace.py       # POST /trace — full pipeline endpoint
    │   ├── routes_cases.py       # GET /cases, GET /cases/{id} — graph retrieval
    │   ├── routes_fir.py         # POST /fir/parse — Gemini AI complaint parser
    │   └── routes_notice.py      # POST /notices/generate — legal notice PDF
    ├── engine/
    │   ├── chain_router.py       # Regex-based address → chain detector
    │   ├── tron_tracer.py        # TronGrid REST client (paginated, Redis-cached)
    │   ├── traversal.py          # Value-weighted BFS graph traversal engine
    │   └── typology.py           # Crime pattern detectors (peeling chain, first funder)
    ├── vasp/
    │   ├── registry.py           # VASP hot-wallet catalogue (8 exchanges, O(1) index)
    │   └── attribution.py        # Hot-wallet step-back attribution algorithm
    └── legal/
        ├── evidence_cert.py      # Section 63 BSA SHA-256 evidence hash builder
        └── pdf_generator.py      # Section 94 BNSS WeasyPrint PDF renderer
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) 0.115 + [Uvicorn](https://www.uvicorn.org/) |
| **Language** | Python 3.12 (fully async) |
| **Validation** | [Pydantic v2](https://docs.pydantic.dev/) + pydantic-settings |
| **Graph DB** | [Neo4j Community 5.x](https://neo4j.com/) (async driver, connection pool) |
| **Cache** | [Redis](https://redis.io/) (async via redis-py) |
| **Blockchain** | [TronGrid REST API](https://developers.tron.network/reference/background) + TronPy |
| **AI** | [Google Gemini](https://ai.google.dev/) via `google-genai` SDK |
| **PDF** | [WeasyPrint](https://weasyprint.org/) + Jinja2 |
| **HTTP Client** | [httpx](https://www.python-httpx.org/) (shared async connection pool) |
| **Logging** | Python `logging` (structured, configurable via `DEBUG` env var) |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Neo4j Community Edition 5.x (running locally or via Docker)
- Redis 7.x (running locally or via Docker)
- A [TronGrid API key](https://www.trongrid.io/)
- A [Google Gemini API key](https://aistudio.google.com/)

### Quick Start with Docker (recommended for dependencies)

```bash
# Start Neo4j
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/yourpassword \
  neo4j:5-community

# Start Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Installation

```bash
# 1. Clone and navigate to the backend
git clone https://github.com/amit-dev01/Chain-Sleuth-Backend.git
cd Chain-Sleuth-Backend

# 2. Create and activate virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your actual API keys and DB credentials

# 5. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verify it's running

```bash
curl http://localhost:8000/health
# → {"status":"ok","app":"ChainSleuth","version":"0.1.0"}

curl http://localhost:8000/ready
# → {"status":"ready","dependencies":{"neo4j":"ok","redis":"ok"}}
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Default | Description |
|---|---|---|---|
| `TRONGRID_KEY` | ✅ | — | TronGrid API key for TRON blockchain RPC |
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key |
| `GEMINI_MODEL` | ❌ | `gemini-2.0-flash` | Gemini model to use |
| `NEO4J_URI` | ✅ | `bolt://localhost:7687` | Neo4j Bolt connection URI |
| `NEO4J_USER` | ✅ | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | ✅ | `password` | Neo4j password |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` | Redis connection URL |
| `DEBUG` | ❌ | `false` | Enable debug logging |

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

### 🔍 Trace

#### `POST /trace/`
Execute a full blockchain trace pipeline.

**Request body:**
```json
{
  "suspect_address": "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9",
  "chain": "tron",
  "max_hops": 5,
  "value_threshold_pct": 2.0,
  "complaint_id": "FIR-2024-001"
}
```

**Response:** `TraceResult` with nodes, edges, typology flags, VASP attribution, and overall risk score.

**Pipeline stages:**
1. Address format validation (regex chain detector)
2. Value-weighted BFS traversal via TronGrid API
3. Neo4j graph write (Wallet nodes + TRANSFER edges)
4. Peeling chain + first funder typology detection
5. VASP hot-wallet step-back attribution
6. Case node persistence

---

### 📁 Cases

#### `GET /cases/{case_id}`
Retrieve the full trace graph for a stored case.

**Response:** `TraceResult` with all Wallet nodes and TransferEdge objects reconstructed from Neo4j. Results are Redis-cached for 2 minutes.

#### `GET /cases/?skip=0&limit=20`
List all cases for the dashboard.

**Response:** `List[CaseSummary]` ordered by creation date descending.

---

### 🤖 AI Parser

#### `POST /fir/parse`
Parse a raw complaint narrative into structured trace parameters using Gemini AI.

**Request body:**
```json
{
  "complaintText": "The victim transferred 50,000 USDT to address TN3W4H6... on the TRON network after being defrauded by an online investment scheme. Total loss: ₹42,00,000."
}
```

**Response:**
```json
{
  "suspect_wallet_address": "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9",
  "blockchain_type": "tron",
  "max_trace_hops": 5,
  "estimated_loss_inr": 4200000.0,
  "summary": "Victim defrauded of 50,000 USDT via TRON investment scam.",
  "confidence": "high"
}
```

---

### 📄 Legal Notices

#### `POST /notices/generate`
Generate a Section 94 BNSS legal notice PDF.

**Request body:** `LegalNoticePayload` with case number, VASP attribution, loss amount, and SHA-256 evidence hash.

**Response:**
```json
{
  "notice_ref": "NOTICE-AB12CD34",
  "pdf_url": "/static/notices/NOTICE-AB12CD34.pdf",
  "sha256_evidence_hash": "a3f5c8...",
  "vasp_name": "Binance",
  "case_number": "FIR-2024-001",
  "is_fiu_registered": false
}
```

#### `GET /notices/{notice_id}/download`
Stream the generated PDF as a file download.

---

### 🩺 Health

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe |
| `GET /ready` | Readiness probe (pings Neo4j + Redis) |
| `GET /docs` | Swagger UI |
| `GET /redoc` | ReDoc |

---

## Core Algorithms

### Value-Weighted BFS (`engine/traversal.py`)

The traversal starts at the suspect address and expands outward:

```
1. Fetch all outbound USDT transfers for current address (TronGrid, Redis-cached)
2. total_volume = Σ(transfer.value)
3. cutoff = total_volume × (value_threshold_pct / 100)   ← noise filter
4. Sort surviving transfers by value DESC                 ← high-value first
5. For each recipient: merge Wallet node → write TRANSFER edge → enqueue
6. Repeat up to max_hops depth
```

- **Safety cap:** Max 500 nodes per trace
- **Concurrency:** `asyncio.gather()` for batch Neo4j writes per BFS level
- **Caching:** TronGrid responses cached in Redis for 5 minutes per address

### Peeling Chain Detector (`engine/typology.py`)

```
For each wallet node:
  forward_ratio = outbound / inbound

  IF forward_ratio ≥ 0.85 AND retain_ratio < 0.15 → candidate

Walk consecutive linear chains among candidates:
  A → B → C → D (single outbound to another candidate each hop)
  IF chain_length ≥ 3 → flag ALL nodes as 'peeling_chain'
```

### VASP Attribution Step-Back (`vasp/attribution.py`)

```
BFS through trace graph edges:
  When to_address ∈ known hot wallets (O(1) registry lookup):
    → Step back 1 hop via inbound edge index
    → Predecessor ranked by value DESC = KYC deposit address

Confidence:
  depth ≤ 2 → 0.95 (direct hit)
  depth > 2 → 0.75 (indirect hit)
```

---

## Legal Modules

### Section 63 BSA Evidence Hash (`legal/evidence_cert.py`)

Produces a **deterministic SHA-256 digest** over the trace data:

```python
canonical = {
    "tx_hashes": sorted([h.lower() for h in tx_hashes]),
    "nodes":     sorted([{address, chain, riskScore} for n in nodes],
                        key=lambda n: n["address"])
}
digest = sha256(json.dumps(canonical, separators=(',',':'), sort_keys=True))
```

The same trace always produces the same hash — making it admissible under:
- **Section 63 BSA 2023** (formerly S.65B Indian Evidence Act)
- **Section 79A IT Act 2000**

### Section 94 BNSS Legal Notice PDF (`legal/pdf_generator.py`)

WeasyPrint renders a full legally-structured notice containing:
- Government header + issuing authority
- VASP attribution detail table (deposit address, hot wallet, FIU status)
- 7-day data production deadline clause (Section 94 BNSS)
- SHA-256 evidence hash stamp (tamper-evident seal)
- Legal basis table (BNSS / BSA / PMLA / IT Act)
- Officer signature block

---

## Data Flow

```
Officer submits suspect address
        │
        ▼
POST /api/v1/trace
        │
        ├─ 1. chain_router.detect_chain()     ← regex validation
        │
        ├─ 2. traversal.run_bfs_trace()
        │       ├─ tron_tracer.fetch_usdt_transfers()   ← TronGrid + Redis cache
        │       ├─ Value filter (threshold_pct)
        │       └─ database.merge_wallet_node()
        │           database.create_transfer_edge()     ← Neo4j writes
        │
        ├─ 3. typology.peeling_chain_detector()         ← flags nodes in-place
        │     typology.first_funder_trace()             ← TronGrid TRX + FEE_FUNDED_BY
        │
        ├─ 4. attribution.attribute_vasp()              ← BFS → hot wallet → step-back
        │       └─ database.merge_vasp_node()
        │           database.create_owned_by_vasp_edge()
        │
        └─ 5. database.save_trace_result()              ← :Case node in Neo4j
                │
                ▼
           TraceResult JSON response

Officer generates legal notice
        │
        ▼
POST /api/v1/notices/generate
        ├─ evidence_cert.compute_evidence_hash()        ← SHA-256 canonical hash
        └─ pdf_generator.generate_legal_notice_pdf()    ← WeasyPrint PDF
                │
                ▼
        /static/notices/NOTICE-XXXXXXXX.pdf
```

---

## Development

### Run with hot reload
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run directly
```bash
python -m app.main
```

### Lint & format
```bash
pip install ruff black
ruff check app/
black app/
```

### Neo4j Browser
Navigate to **http://localhost:7474** to explore the graph visually.

Useful Cypher queries:
```cypher
// View all traced wallets
MATCH (w:Wallet) RETURN w LIMIT 50

// View all cases
MATCH (c:Case) RETURN c ORDER BY c.created_at DESC

// View the shortest path between two wallets
MATCH path = (a:Wallet {address: "TXXX"})-[:TRANSFER*1..5]->(b:Wallet)
RETURN path LIMIT 1

// View VASP attributions
MATCH (w:Wallet)-[:OWNED_BY_VASP]->(v:VASP) RETURN w, v
```

---

<div align="center">
  <sub>Built for the ChainSleuth platform — Blockchain forensics for Indian law enforcement</sub>
</div>
