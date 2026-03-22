#!/bin/bash
# FinClose AI — Environment Setup
# Run once from project root: bash scripts/setup.sh

set -e

echo "=================================================="
echo "  FinClose AI — Environment Setup"
echo "=================================================="

# 1. Python deps
echo ""
echo "[1/4] Installing Python dependencies..."
pip install -r requirements.txt

# 2. Check Ollama
echo ""
echo "[2/4] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "  ⚠️  Ollama not found."
    echo "  Install from: https://ollama.com"
    echo "  Then run: ollama pull mistral"
else
    echo "  ✅ Ollama found: $(ollama --version)"
    echo "  Pulling mistral model (this may take a few minutes first time)..."
    ollama pull mistral
fi

# 3. Generate mock data
echo ""
echo "[3/4] Generating mock enterprise data..."
if [ -f "finclose_data_gen/finclose.db" ]; then
    echo "  ✅ finclose.db already exists — skipping generation"
    echo "  (Delete finclose_data_gen/finclose.db to regenerate)"
else
    python finclose_data_gen/generate_mock_data.py
fi

# 4. Validate
echo ""
echo "[4/4] Validating setup..."
python3 -c "
import sys; sys.path.insert(0, '.')
from core.state import AgentState
from core import db_tools
from agents.agents import planner_agent, retriever_agent, executor_agent, critic_agent
from pipeline import run_pipeline
result = db_tools.get_anomalous_entries('2024-12')
print(f'  ✅ DB OK — {result[\"anomaly_count\"]} anomalies found')
print('  ✅ All imports OK')
print('  ✅ Pipeline ready')
"

echo ""
echo "=================================================="
echo "  Setup complete!"
echo ""
echo "  To run:"
echo "    ollama serve                    (keep running)"
echo "    python pipeline.py             (CLI demo)"
echo "    streamlit run ui/app.py        (dashboard)"
echo "    uvicorn api.server:app --reload (API)"
echo "=================================================="
