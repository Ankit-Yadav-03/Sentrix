# SIH26165 — SIF Precursor Detection System
### v0 Internal Round Prototype

AI-powered near-miss report analysis for oil & gas sites. Detects Serious Injury & Fatality (SIF) precursor patterns from near-miss reports using a locally-hosted LLM (Ollama) + distilBERT classifier + weighted graph cluster engine.

---

## Architecture Overview

```
Report Submission (text / PDF / Flutter)
        │
        ▼
  Gate 1: Structural Validation (site registry, length, source, language, duplicate)
        │
        ▼
  Gate 2: Domain Keyword Check (80+ safety terms)
        │
        ▼
  LLM Extraction (Ollama qwen3:8B)
        │  → subtype_id, contributing_factors, equipment_classes,
        │    activity_contexts, evidence_span, severity, mapping_confidence
        ▼
  Gate 3: Vocabulary Lock (ontology registry enforcement)
        │
        ▼
  distilBERT Classifier (fine-tuned / rule-based fallback)
        │  → sif_category, severity, classifier_score
        ▼
  Pattern Score Engine (5 components × weights)
        │  Density (0.25) + Edge Strength (0.20) + Velocity (0.20)
        │  + Severity (0.20) + Concentration (0.15)
        ▼
  Risk State Machine: NOMINAL → WATCH → ELEVATED → CRITICAL
        │
        ▼
  Next.js Dashboard + REST API
```

**SIF Categories (6):** FALL_FROM_HEIGHT · CAUGHT_IN_STRUCK_BY · EXPLOSION_FIRE · CHEMICAL_EXPOSURE · ELECTRICAL · VEHICLE_TRANSPORT  
**Subtypes:** 24 total (4 per category)  
**Standards:** ILO OSH-MS 2001 · OISD-STD-155 · OSHA 29 CFR

---

## Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.11+ | |
| Node.js | 18+ | For Next.js frontend |
| PostgreSQL | 14+ | Local or Docker |
| Ollama | Latest | https://ollama.com |

---

## Quick Start

### 1. Clone & Configure

```bash
cd sih26165
cp .env.example .env
# Edit .env — set DATABASE_URL, OLLAMA_BASE_URL, OLLAMA_MODEL
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

> **Note on PyTorch:** `torch` and `transformers` are only needed if you train or run the distilBERT classifier. For v0 demo with rule-based fallback, you can skip them:
> ```bash
> pip install fastapi uvicorn sqlalchemy psycopg2-binary httpx pypdf langdetect python-multipart python-dotenv pydantic
> ```

### 3. Set Up PostgreSQL

**Option A — Docker (quickest):**
```bash
docker run -d --name sif-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=sif_db \
  -p 5432:5432 postgres:16
```

**Option B — Existing PostgreSQL:**
```bash
psql -U postgres -c "CREATE DATABASE sif_db;"
```

Apply schema:
```bash
psql -U postgres -d sif_db -f scripts/schema.sql
```

### 4. Start Ollama

```bash
ollama serve                    # starts Ollama daemon
ollama pull qwen3:8B         # ~4.7GB download (one time)
```

> **CPU-only / low-RAM:** Use `ollama pull phi3.5:3.8b` instead, and set `OLLAMA_MODEL=phi3.5:3.8b` in `.env`

### 5. Start the Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API available at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

### 6. Seed Demo Data

```bash
python scripts/seed_demo_data.py
```

This runs the full pipeline on all 10 demo reports and creates:
- **OIL_SITE_04**: CE.01 cluster with 2–3 reports → ELEVATED state
- **OIL_SITE_07**: FFH.01 + VT.01 reports → WATCH/NOMINAL
- **OIL_SITE_02**: EF.01 + EF.04 reports → WATCH state
- **OIL_SITE_11**, **OIL_SITE_15**: 1–2 reports each → NOMINAL

### 7. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at: http://localhost:3000

---

## Demo Walkthrough (Internal Round)

### Scenario: Site 4 Pattern Escalation

After seeding, Site 4 will be at WATCH or ELEVATED (3 CE.01 + CE.02 reports). Submit the live report to demonstrate cluster join and state escalation:

1. Open http://localhost:3000/submit  
2. Select **OIL_SITE_04**  
3. Paste the contents of `demo_data/reports/report_CE01_b.txt` (remove the `#` header lines)  
4. Click **Submit Report**  
5. Observe the result:
   - `CHEMICAL_EXPOSURE` / `CE.01` classification
   - Pattern Score breakdown showing all 5 components
   - Risk state update (should reach ELEVATED)
6. Navigate to http://localhost:3000/sites/OIL_SITE_04 to see the full cluster

### API Demo

```bash
# Health check
curl http://localhost:8000/health

# All site risk states
curl http://localhost:8000/sites | python3 -m json.tool

# Active clusters
curl http://localhost:8000/clusters | python3 -m json.tool

# Dashboard stats
curl http://localhost:8000/stats | python3 -m json.tool

# Submit report via API
curl -X POST http://localhost:8000/submit/text \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "OIL_SITE_04",
    "raw_text": "Maintenance technician performing valve inspection without chemical resistant gloves. Acid injection line had minor drip, contacted forearm. PPE available but not worn. Supervisor not notified prior to starting work.",
    "source": "manual_text",
    "submitted_by": "demo"
  }' | python3 -m json.tool
```

---

## Run Tests

```bash
pytest tests/ -v
```

Expected: **76 passed** in < 1 second (no DB, no Ollama required).

Tests cover:
- Gate 1 structural validation (7 tests)
- Gate 2 domain keyword check (10 tests)
- Vocabulary lock for all 24 subtypes (11 tests)
- Pattern Score Engine — all 5 components (7 tests)
- Edge weight computation (6 tests)
- State machine transitions (6 tests)
- Classifier interface (5 tests)
- Ontology registry integrity (6 tests)
- PDF parser (2 tests)
- LLM prompt builder + JSON extraction + fallback (12 tests)
- Temporal decay (4 tests)

---

## Train the Classifier (Optional)

The v0 prototype uses a rule-based fallback classifier. To train the distilBERT model:

```bash
# Place OSHA IMIS petroleum sector JSONL data in:
# classifier_training/data/train.jsonl

# Each line format:
# {"subtype_id":"CE.01","contributing_factors":["PPE_FAILURE"],"equipment_classes":["CHEMICAL_DRUM"],"activity_contexts":["CHEMICAL_HANDLING"],"evidence_span":"...","sif_category":"CHEMICAL_EXPOSURE","severity":"HIGH"}

cd sih26165
python classifier_training/train.py \
  --data_dir ./classifier_training/data \
  --output_dir ./backend/models/distilbert-sif-v1.0 \
  --epochs 5

# Set path in .env:
# CLASSIFIER_MODEL_PATH=./backend/models/distilbert-sif-v1.0
```

Target: ≥ 82% weighted F1, maximize CRITICAL severity recall.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check, model status |
| POST | `/submit/text` | Submit report as JSON text |
| POST | `/submit/pdf` | Upload PDF report |
| GET | `/reports` | List reports (paginated, filter by site) |
| GET | `/reports/{id}` | Full report detail with mappings |
| GET | `/sites` | All sites with risk states |
| GET | `/sites/{site_id}` | Site detail with clusters |
| GET | `/clusters` | All active clusters |
| GET | `/clusters/{id}` | Cluster with Pattern Score breakdown |
| GET | `/alerts` | Undelivered state-change alerts |
| GET | `/validation-failures` | Gate failure log |
| GET | `/stats` | Aggregate dashboard stats |

---

## Project Structure

```
sih26165/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── api/
│   │   ├── reports.py           # /submit/text, /submit/pdf, /reports
│   │   ├── sites.py             # /sites, /sites/{site_id}, /sites/{site_id}/state
│   │   ├── clusters.py          # /clusters, /clusters/{cluster_id}
│   │   ├── dashboard.py         # /health, /stats, /alerts, /validation-failures
│   │   └── dependencies.py      # Shared helpers & pipeline logic
│   ├── models/db.py             # SQLAlchemy ORM models
│   ├── ontology/registry.json   # 6 categories, 24 subtypes, standards refs
│   ├── pipeline/
│   │   ├── validator.py         # Gate 1, Gate 2, vocabulary lock
│   │   ├── pdf_parser.py        # PDF text extraction
│   │   ├── llm_extraction.py    # Ollama integration + prompt builder
│   │   └── classifier.py        # distilBERT + rule-based fallback
│   └── graph/
│       └── pattern_score.py     # 5-component pattern score engine
├── classifier_training/
│   └── train.py                 # distilBERT fine-tuning script
├── frontend/
│   └── pages/                   # Next.js dashboard
│       ├── index.js             # Main dashboard
│       ├── submit.js            # Report submission
│       ├── reports/             # Report list + detail
│       ├── sites/               # Site list + detail
│       └── clusters/            # Cluster list + detail (Pattern Score breakdown)
├── scripts/
│   ├── schema.sql               # Full PostgreSQL schema
│   └── seed_demo_data.py        # Demo data seeder
├── demo_data/reports/           # 10 realistic OSHA near-miss reports
├── tests/test_all.py            # 76 unit tests (no DB/Ollama required)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Known Limitations (v0)

- Pipeline runs synchronously (no async queue). Large reports may block for Ollama inference time (~5–30s on CPU).
- NetworkX graph not wired — Pattern Score computed from DB queries directly.
- Flutter mobile app defined in architecture but not in v0 scope.
- Classifier is rule-based fallback until OSHA corpus training data is provided.
- No authentication on API endpoints (v0 demo only).