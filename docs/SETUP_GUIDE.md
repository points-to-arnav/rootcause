# RootCause / AskData: Comprehensive Setup & Deployment Guide

This guide walks through setting up, configuring, and running **RootCause** from a fresh clone, ensuring zero missing dependencies or runtime problems.

---

## 1. Prerequisites

Ensure the following tools are installed on your machine:
- **Python**: `3.11` or newer (Tested on Python 3.11, 3.12, 3.14)
- **Node.js**: `18.0.0` or newer (Tested on Node v20 & v26)
- **npm**: `9.0.0` or newer
- **Git**: Installed and configured

---

## 2. Quick Automated Setup (One Command)

If you are on Linux or macOS, you can run the provided automated setup script:
```bash
chmod +x setup.sh
./setup.sh
```
This script will automatically:
1. Create a Python virtual environment (`.venv`)
2. Install all Python dependencies from `backend/requirements.txt`
3. Install all frontend dependencies in `frontend/`
4. Copy `.env.example` to `backend/.env` (if not already present)
5. Generate the sample dataset workbooks (`retail_demo.xlsx`, `sample_orders.xlsx`, `sample_sales.csv`)
6. Execute the full backend test suite to verify everything is working

---

## 3. Step-by-Step Manual Setup

### Step 3.1: Clone the Repository
```bash
git clone https://github.com/points-to-arnav/rootcause.git
cd rootcause
```

---

### Step 3.2: Python Virtual Environment & Backend Dependencies

1. **Create and activate the virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   *(On Windows: `.venv\Scripts\activate`)*

2. **Upgrade pip and install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

   **Key dependencies installed:**
   - `fastapi` & `uvicorn`: High-performance asynchronous REST API
   - `duckdb`: Embedded analytical query engine
   - `pandas` & `openpyxl`: Excel & CSV parser and tabular manipulation
   - `pydantic` & `pydantic-settings`: Schema validation and settings management
   - `httpx`: Resilient asynchronous HTTP client for LLM API calls
   - `rapidfuzz`: Fast fuzzy search string metric matching for dimensional value resolution
   - `pytest`: Automated test framework

---

### Step 3.3: Configure Environment Variables & LLM Keys

1. Copy the example configuration file:
   ```bash
   cp .env.example backend/.env
   ```

2. Open `backend/.env` in your editor and provide your LLM API keys:
   ```env
   # Active LLM Provider: "openrouter" or "nvidia_nim"
   LLM_PROVIDER=openrouter

   # OpenRouter API Key (Obtain free key at: https://openrouter.ai/keys)
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   OPENROUTER_MODEL=nex-agi/nex-n2.5-mini:free

   # NVIDIA NIM API Key (Obtain at: https://build.nvidia.com/)
   NVIDIA_NIM_API_KEY=nvapi-your-key-here
   NVIDIA_NIM_MODEL=meta/llama-3.2-11b-vision-instruct
   ```

   > [!TIP]
   > **Dual-Provider Architecture**: You can provide either or both keys. If both are provided, RootCause automatically routes to NVIDIA NIM if OpenRouter encounters a rate limit or timeout.

---

### Step 3.4: Generate Sample Datasets

Run the data generator to create the official demo workbooks:
```bash
# Generate the multi-sheet retail demo with planted root-cause storyline
.venv/bin/python sample_data/generate_retail.py

# Generate additional E-commerce orders and CSV sample files
.venv/bin/python sample_data/create_sample_files.py
```
This produces:
- `sample_data/retail_demo.xlsx` (16,641 sales, 800 customers, 110 products, 8,800 inventory rows)
- `sample_orders.xlsx` (5,980 orders with Customers and Products sheets)
- `sample_sales.csv` (3,369 transactions across 6 cities)

---

### Step 3.5: Run Backend Tests

Verify that all analytical components, compilers, why engines, and API endpoints are working properly:
```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v
```
Expected output:
```
backend/tests/test_api_endpoints.py::test_health PASSED
backend/tests/test_api_endpoints.py::test_settings_get PASSED
backend/tests/test_api_endpoints.py::test_sample_dataset_and_semantic PASSED
backend/tests/test_compiler.py::test_sql_compiler_kpi_and_breakdown PASSED
backend/tests/test_narrator_verify.py::test_number_verification PASSED
backend/tests/test_pipeline_core.py::test_ingestion_and_semantic_pipeline PASSED
backend/tests/test_why_engine.py::test_why_engine_august_drop PASSED
========================= 7 passed in ~4.9s =========================
```

---

### Step 3.6: Frontend Installation & Build

1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   npm install
   ```

2. Validate that the production bundle builds cleanly:
   ```bash
   npm run build
   ```
   This compiles TypeScript, bundles React with Vite, and builds all Tailwind CSS styles into `frontend/dist/`.

---

## 4. Running the Development Servers

### Terminal 1: Backend API Server
```bash
cd backend
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The FastAPI documentation is accessible at `http://localhost:8000/docs`.

### Terminal 2: Frontend UI
```bash
cd frontend
npm run dev
```
Open your browser at **`http://localhost:5173`**.

---

## 5. Pre-Push Git Checklist

Before pushing commits to GitHub, verify the following:
1. **No API Keys in Git**:
   Run `git status` and verify that `backend/.env` is **NOT** listed in staged files. (It is excluded via `.gitignore`).
2. **Virtual Environment Ignored**:
   Ensure `.venv/` is excluded.
3. **DuckDB Database Artifacts Ignored**:
   Ensure `backend/data/` is excluded.
4. **Node Modules Ignored**:
   Ensure `frontend/node_modules/` and `frontend/dist/` are excluded.
5. **Verify Tests**:
   Ensure `PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v` passes 100%.
6. **Verify Frontend Build**:
   Ensure `npm run build` in `frontend/` succeeds without errors.
