# ChainSleuth Backend Service

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI%20Async-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Graph_Database-Neo4j%205.x-008CC1.svg?logo=neo4j&logoColor=white)](https://neo4j.com)
[![Redis](https://img.shields.io/badge/Cache_&_Limiter-Upstash%20Redis-DC382D.svg?logo=redis&logoColor=white)](https://upstash.com)
[![Supabase](https://img.shields.io/badge/Storage-Supabase%20PostgreSQL-3ECF8E.svg?logo=supabase&logoColor=white)](https://supabase.com)
[![Security Standards](https://img.shields.io/badge/Security-OWASP%20Hardened-green.svg)](https://owasp.org)

The ChainSleuth Backend is an asynchronous, high-throughput analytics engine built on FastAPI. It handles on-chain transaction ingestion, graph database persistence, multi-model machine learning inference, and statutory legal document synthesis for blockchain forensic investigations.

---

## Technical Architecture

```
                                 Client Application (HTTPS / REST)
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │   Security Middleware (OWASP Top 10)         │
                         │   - Strict CORS Whitelisting                 │
                         │   - Security Headers (nosniff, DENY, HSTS)   │
                         │   - Unhandled Exception Sanitization         │
                         └──────────────────────┬───────────────────────┘
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │   Identity & Access Control (RBAC)           │
                         │   - Supabase Bearer Token Authentication     │
                         │   - Local Dev Officer Profile Bypass         │
                         └──────────────────────┬───────────────────────┘
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │   Distributed Rate Limiter                   │
                         │   - Redis Sliding-Window Algorithm           │
                         │   - In-Memory Fallback Bucket                │
                         └──────────────────────┬───────────────────────┘
                                                │
                                                ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   API Routing Layer                                         │
 │  /trace  •  /cases  •  /fir  •  /notices  •  /ncrp  •  /vasp  •  /audit  •  /report         │
 └──────┬──────────────────────┬────────────────────────┬──────────────────────┬───────────────┘
        │                      │                        │                      │
        ▼                      ▼                        ▼                      ▼
┌───────────────┐      ┌───────────────┐        ┌───────────────┐      ┌───────────────┐
│ Ledger Engine │      │  Graph Engine │        │ ML Ensemble   │      │ Legal Engine  │
│ - Bitcoin     │      │ - Neo4j Bolt  │        │ - GraphSAGE   │      │ - WeasyPrint  │
│ - EVM / Base  │      │ - Schema Init │        │ - XGBoost     │      │ - ReportLab   │
│ - TRON        │      │ - BFS Paths   │        │ - IsoForest   │      │ - Jinja2      │
│ - Solana      │      │ - VASP Steps  │        │ - Gemini LLM  │      │ - SHA-256     │
└───────────────┘      └───────────────┘        └───────────────┘      └───────────────┘
```

---

## Key Modules & Responsibilities

### 1. Multi-Chain Ingestion (`app/engine/`)
- **`chain_router.py`**: Validates address syntaxes (Base58, Bech32, Hex) and dynamically routes requests to the appropriate network parser.
- **`btc_tracer.py`**: Resolves Bitcoin UTXO inputs and outputs using Blockstream and Blockchain.info APIs with multi-provider failover.
- **`evm_tracer.py`**: Extracts native ETH and ERC-20 transfers across Ethereum and Base via BaseScan and Blockscout endpoints.
- **`tron_tracer.py`**: Traverses TRON TRC-20 USDT interactions via TronGrid with cursor-based pagination and gas-funder extraction.
- **`solana_tracer.py`**: Parses SPL token transfers and account metadata via Solana JSON-RPC.

### 2. Forensic Graph Engine (`app/core/database.py`)
- Maintains an asynchronous connection pool to **Neo4j 5.x** via Bolt protocol.
- Enforces uniqueness constraints on `:Wallet(address, chain)` and `:VASP(name)`, with composite risk indexes for fast lookups.
- Implements parallel batch Cypher queries (`batch_merge_wallet_nodes`, `batch_create_transfer_edges`) to eliminate lock contention during deep graph ingestion.
- Manages graph path discovery for virtual asset service providers (`find_shortest_path_to_vasp`).

### 3. Machine Learning Ensemble (`app/engine/`)
- **`ml_risk_scorer.py`**: Executes an ONNX Runtime session (`graphsage_risk.onnx`) evaluating multi-hop node embeddings.
- **`ml_typology_classifier.py`**: Employs an XGBoost classifier suite identifying peeling chains, fan-out smurfing, and mixer interactions.
- **`ml_anomaly_detector.py`**: Uses an Isolation Forest estimator to identify statistical behavioral outliers in velocity and pass-through ratios.
- **`ml_ensemble_scorer.py`**: Combines topological, rule-based, and anomaly outputs into a calibrated 0–100 risk score.
- **`ml_report_generator.py`**: Synthesizes formal investigative summaries using the Google Gemini API with fallback text templates.

### 4. Statutory Legal Document Engine (`app/legal/`)
- **`pdf_generator.py`**: Compiles Section 94 BNSS legal notices and police FIR dockets into PDF format via WeasyPrint, with a pure-Python ReportLab fallback.
- **Tamper-Evident SHA-256 Stamping**: Serializes graph representations deterministically to generate court-admissible electronic evidence seals adhering to Section 63 BSA 2023.

---

## Security Implementation (OWASP Top 10 Hardened)

| Security Domain | Defensive Implementation |
| :--- | :--- |
| **Authentication & RBAC** | Enforces `get_current_user` across all sensitive API routers. Supports Supabase JWT token validation in production with automated dev-officer fallbacks in local testing. |
| **Strict CORS** | Explicit domain whitelist (`localhost:3000`, `localhost:5173`, `chainsleuth.in`, `chain-sleuth-six.vercel.app`). Wildcard regex matching is strictly disabled. |
| **Defensive Headers** | Injected via middleware: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Strict-Transport-Security` (HSTS). |
| **Rate Limiting** | Distributed sliding-window limiter (`RateLimiter`) backed by Upstash Redis. Limits `/trace` to 20 req/min and `/fir/parse` to 15 req/min. |
| **Path Traversal Defense** | Document retrieval endpoints sanitize parameters using strict alphanumeric regex (`^[A-Za-z0-9_-]+$`) and path boundary verification (`.is_relative_to()`). |
| **Protected File Delivery** | Unauthenticated `/static` directory mounts are eliminated; documents are streamed exclusively through authenticated API endpoints. |
| **Error Sanitization** | Low-level RPC, database, and infrastructure exceptions are logged internally and sanitized in HTTP responses to prevent information leakage. |
| **Injection Mitigation** | All Neo4j queries use parameterized Cypher. Supabase PostgREST filters sanitize search queries. LLM prompts apply defensive XML tag boundaries against prompt injection. |

---

## Environment Configuration

Configure the following parameters in `backend/.env`:

```env
# ── Blockchain Explorers ──────────────────────────────────────────────────────
TRONGRID_KEY=your_trongrid_api_key
BASESCAN_API_KEY=your_basescan_api_key
BASE_RPC_URL=https://mainnet.base.org

# ── Large Language Model (Google Gemini) ──────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash

# ── Graph Database (Neo4j AuraDB / Self-Hosted) ──────────────────────────────
NEO4J_URI=neo4j+s://<instance_id>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=

# ── Cache & Rate Limiting (Upstash / Redis) ──────────────────────────────────
REDIS_URL=rediss://default:<token>@<host>.upstash.io:6379
UPSTASH_REDIS_REST_URL=https://<host>.upstash.io
UPSTASH_REDIS_REST_TOKEN=your_upstash_token

# ── Relational Storage (Supabase Cloud PostgreSQL) ───────────────────────────
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
AUTH_ENABLED=false

# ── Application Runtime ───────────────────────────────────────────────────────
DEBUG=false
ENABLE_DOCS=true
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://chain-sleuth-six.vercel.app,https://chain-sleuth-backend.onrender.com
```

---

## Local Setup & Development

### 1. Environment Preparation
```bash
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 2. Dependency Installation
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Service Execution
```bash
# Development mode with hot reload:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode with multiple worker processes:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## API Reference Overview

The API is mounted with prefix `/api/v1`.

### Trace & Graph Operations
- `POST /api/v1/trace/`: Executes a multi-hop BFS traversal for a suspect wallet and returns topological risk metrics.
- `GET /api/v1/cases/`: Lists previously stored investigation cases with pagination.
- `GET /api/v1/cases/{caseId}`: Returns complete stored graph details (nodes, edges, risk scores).
- `GET /api/v1/cases/{caseId}/export-bundle`: Generates a digital evidence ZIP package containing the canonical evidence graph, Section 63 BSA certificate, and Section 94 notice.

### Judicial & Legal Document Endpoints
- `POST /api/v1/notices/generate`: Compiles a Section 94 BNSS legal freeze order PDF.
- `GET /api/v1/notices/{noticeId}/download`: Securely streams the generated notice PDF.
- `POST /api/v1/fir/`: Creates a structured police FIR record and generates an associated PDF.
- `GET /api/v1/fir/{firId}/download`: Securely streams the generated FIR PDF document.
- `POST /api/v1/fir/parse`: Uses natural language processing to extract structured investigative entities from raw complaint text.

### Intelligence & Supervisory Controls
- `POST /api/v1/ncrp/ingest`: Ingests bulk complaints from the National Cyber Crime Reporting Portal.
- `GET /api/v1/ncrp/correlations`: Correlates shared fee funders and deposit targets across multiple cases.
- `GET /api/v1/vasp/labels`: Lists verified VASP attribution tags.
- `POST /api/v1/vasp/custom-labels`: Registers or updates custom wallet attribution intelligence.
- `GET /api/v1/audit/logs`: Provides tamper-evident supervisory action logs for judicial oversight.

---

## Verification & Automated Testing

Execute the comprehensive test suite:
```bash
python scratch/test_evidence_cert.py
python scratch/verify_owasp_hardening.py
```

---

## License

Proprietary and confidential. Authorized for government, law enforcement, and regulated financial intelligence operations only.
