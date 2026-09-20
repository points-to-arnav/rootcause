# RootCause: The Conversational AI Data Analyst

> A production-grade, hallucination-free conversational data analysis platform built on **DuckDB**, **FastAPI**, **React**, and **Tailwind CSS**.

---

## Key Highlights

- ⚡ **Zero Hallucination Guarantee**: DuckDB and deterministic Python code execute 100% of calculations. The LLM only plans queries and narratesthe pre-computed totals.
- 🛡️ **Regex Number Verifier**: Every number stated in the narrative is verified against actual DuckDB result cells before presentation.
- 🔍 **Root-Cause "Why" Engine**: Decomposes period-over-period metric declines ($\Delta = M(T) - M(B)$) across all candidate dimensions and identifies top contributing drivers.
- 🔄 **Dual-Provider LLM Fallback**: Seamless automatic failover between **OpenRouter** (free models) and **NVIDIA NIM** (`meta/llama-3.2-11b-vision-instruct`).
- 📊 **Glass-Box Transparency**: Inspect the exact compiled DuckDB SQL, JSON execution plan, resolved calendar windows, and data quality warnings for every turn.
- 🗂️ **Automated Data Quality & Ingestion**: Drag and drop multi-sheet `.xlsx` or `.csv` files. Automatically infers schemas, detects relationships, and highlights data quality bugs.

---

## Architecture Diagram

```
User Question / Upload
         │
         ▼
┌──────────────────┐      ┌─────────────────────────────┐
│ Fast Ingestion   │ ───► │ DuckDB Database & Profiler  │
│ Excel / CSV      │      │ (Nulls, Types, DQ Checks)   │
└──────────────────┘      └─────────────────────────────┘
         │                               │
         ▼                               ▼
┌──────────────────┐      ┌─────────────────────────────┐
│ Semantic Layer   │ ───► │ Join Graph & Anchor Date    │
│ (Roles, Metrics) │      │ RapidFuzz Value Index       │
└──────────────────┘      └─────────────────────────────┘
         │                               │
         ▼                               ▼
┌──────────────────┐      ┌─────────────────────────────┐
│ LLM Planner      │ ───► │ SQL Compiler & Why Engine   │
│ (Structured JSON)│      │ (Single-scan DuckDB query)  │
└──────────────────┘      └─────────────────────────────┘
         │                               │
         ▼                               ▼
┌──────────────────┐      ┌─────────────────────────────┐
│ Result Aggregates│ ───► │ Narrator & Number Verifier  │
│                  │      │ (Regex match vs DuckDB cells│
└──────────────────┘      └─────────────────────────────┘
         │                               │
         ▼                               ▼
┌───────────────────────────────────────────────────────┐
│ Modern React + ECharts UI                             │
│ (KPI Cards, Line, Bar, Contribution, Glass-Box SQL)   │
└───────────────────────────────────────────────────────┘
```

---

## Quick Start Guide

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/points-to-arnav/rootcause.git
cd rootcause

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run automated tests
PYTHONPATH=backend pytest backend/tests/ -v

# Start FastAPI backend server (port 8000)
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server (port 5173)
npm run dev
```

Open your browser at `http://localhost:5173`.

---

## Demo Walkthrough with Retail Demo Data

Click **"Load Retail Demo Dataset"** on the upload page to instantly load `sample_data/retail_demo.xlsx` (16,641 sales, 800 customers, 110 products, 8,800 inventory rows).

Try asking these questions in sequence:
1. *"What is our total revenue?"* $\to$ Renders KPI card of ~$3.9M with data quality notice.
2. *"Show me monthly revenue for 2026"* $\to$ Renders monthly revenue trend line chart (Jan–Aug 2026).
3. *"Revenue by region"* $\to$ Renders categorical breakdown bar chart.
4. *"Why did revenue fall last month?"* $\to$ Renders signed contribution diverging waterfall chart identifying the August 2026 drop ($\Delta = -\$70.8\text{k}$) driven by Electronics in the West region.
5. *"Show me the five products responsible for the largest decline"* $\to$ Renders horizontal ranking bar chart of the top 5 products with largest negative delta.

Or switch to the **Dashboard** tab to view the executive summary, KPI sparklines, and automated anomaly alerts!

---

## Documentation & Guides

- 📘 **[Setup & Deployment Guide](docs/SETUP_GUIDE.md)**: Prerequisites, automated one-command setup, and production builds.
- 🏛️ **[System Architecture & Engine Guide](docs/SYSTEM_GUIDE.md)**: Deep-dive into every module, file map, data flow, and the Why engine.
- 📡 **[REST API Reference](docs/API_REFERENCE.md)**: Complete endpoint documentation with request/response schemas.
- 🛠️ **[Troubleshooting & FAQ](docs/TROUBLESHOOTING.md)**: Common questions, rate limit failovers, and DuckDB concurrency.

---

## License

This project is licensed under the [MIT License](LICENSE).

