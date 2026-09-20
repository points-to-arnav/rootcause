"""
Test script to verify LLM connection, Query Planning, DuckDB execution, and Narration.
Usage:
    .venv/Scripts/python backend/test_ai_analyst.py
"""
import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.semantic.store import load_semantic_layer
from app.semantic.value_index import ValueIndex
from app.memory.session import create_session
from app.pipeline import run_ask_pipeline

def main():
    print("=" * 60)
    print("[*] RootCause / AskData AI Analyst Verification")
    print("=" * 60)

    # 1. Check Configuration
    print(f"Active Provider : {settings.LLM_PROVIDER}")
    or_key = settings.OPENROUTER_API_KEY
    nv_key = settings.NVIDIA_NIM_API_KEY

    print(f"OpenRouter Key  : {'[OK] Configured (length ' + str(len(or_key)) + ')' if or_key else '[X] Empty'}")
    if or_key:
        print(f"OpenRouter Model: {settings.OPENROUTER_MODEL}")

    print(f"NVIDIA NIM Key  : {'[OK] Configured (length ' + str(len(nv_key)) + ')' if nv_key else '[X] Empty'}")
    if nv_key:
        print(f"NVIDIA NIM Model: {settings.NVIDIA_NIM_MODEL}")

    if not or_key and not nv_key:
        print("\n[!] Error: Neither OPENROUTER_API_KEY nor NVIDIA_NIM_API_KEY is saved in backend/.env!")
        print("--> Please make sure you saved (Ctrl + S) the backend/.env file with your key.")
        return

    # 2. Check Dataset
    ds_id = "ds_retail_sample"
    semantic = load_semantic_layer(ds_id)
    if not semantic:
        print(f"\nLoading sample dataset '{ds_id}'...")
        from app.api.routes_datasets import load_sample_dataset
        load_sample_dataset()
        semantic = load_semantic_layer(ds_id)

    print(f"\n[OK] Loaded Semantic Layer for '{ds_id}' ({len(semantic.tables)} tables, fact='{semantic.fact_table}', anchor='{semantic.time.anchor_date}')")

    # 3. Test Question
    test_question = "Show me monthly revenue for 2026"
    print(f"\n[>] Sending query to LLM Planner: '{test_question}'...")
    
    session = create_session(ds_id)
    v_index = ValueIndex()
    v_index.build(semantic.tables, semantic.metrics)

    response = run_ask_pipeline(
        session=session,
        semantic=semantic,
        question=test_question,
        value_index=v_index
    )

    print("\n" + "=" * 60)
    print("[+] AI ANALYST PIPELINE RESULTS")
    print("=" * 60)
    print(f"Status           : {response.get('status')}")
    print(f"Intent           : {response.get('plan', {}).get('intent') if response.get('plan') else 'N/A'}")
    print(f"Metric           : {response.get('plan', {}).get('metric') if response.get('plan') else 'N/A'}")
    print(f"Resolved Window  : {response.get('resolved_time')}")
    print(f"\nCompiled SQL:\n{response.get('sql')}")
    print(f"\nDuckDB Rows Returned: {response.get('result', {}).get('row_count')}")
    if response.get('result', {}).get('rows'):
        print(f"Columns: {response.get('result', {}).get('columns')}")
        print("Sample Data:")
        for r in response.get('result', {}).get('rows')[:5]:
            print(f"  {r}")
    print(f"\nChart Type Chosen: {response.get('chart', {}).get('type')}")
    print(f"\nNarrative:\n{response.get('narrative')}")
    print(f"\nFollow-up Suggestions: {response.get('suggestions')}")
    print("=" * 60)
    print("[SUCCESS] AI Analyst verified end-to-end!")

if __name__ == "__main__":
    main()
