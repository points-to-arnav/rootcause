#!/usr/bin/env bash
set -e

# ==============================================================================
# RootCause: One-Command Automated Setup Script
# ==============================================================================

echo "=========================================================="
echo "   Setting up RootCause / AskData AI Analyst Platform     "
echo "=========================================================="

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is required but not installed. Aborting."
    exit 1
fi

# 2. Check Node & npm
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo "[ERROR] node and npm are required but not installed. Aborting."
    exit 1
fi

echo "[✓] Python version: $(python3 --version)"
echo "[✓] Node version:   $(node --version)"
echo "[✓] npm version:    $(npm --version)"
echo ""

# 3. Virtual Environment Setup
if [ ! -d ".venv" ]; then
    echo "[1/6] Creating Python virtual environment in .venv..."
    python3 -m venv .venv
else
    echo "[1/6] Existing .venv detected."
fi

source .venv/bin/activate
echo "[2/6] Installing Python backend dependencies..."
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q

# 4. Environment File
if [ ! -f "backend/.env" ]; then
    echo "[3/6] Copying .env.example to backend/.env..."
    cp .env.example backend/.env
    echo "      [!] Remember to add your OPENROUTER_API_KEY or NVIDIA_NIM_API_KEY in backend/.env"
else
    echo "[3/6] backend/.env already exists."
fi

# 5. Generate Sample Workbooks
echo "[4/6] Generating sample Excel & CSV datasets..."
python sample_data/generate_retail.py
python sample_data/create_sample_files.py

# 6. Run Test Suite
echo "[5/6] Running backend pytest suite..."
PYTHONPATH=backend pytest backend/tests/ -v

# 7. Frontend Setup
echo "[6/6] Installing frontend dependencies & building production bundle..."
cd frontend
npm install --silent
npm run build
cd ..

echo ""
echo "=========================================================="
echo "   Setup Complete! Everything is configured and verified. "
echo "=========================================================="
echo ""
echo "To start the application:"
echo ""
echo "1. Start the Backend (Terminal 1):"
echo "   cd backend && ../.venv/bin/uvicorn app.main:app --port 8000 --reload"
echo ""
echo "2. Start the Frontend (Terminal 2):"
echo "   cd frontend && npm run dev"
echo ""
echo "Open your browser at: http://localhost:5173"
echo "=========================================================="
