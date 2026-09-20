from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.memory.session import create_session, load_session
from app.pipeline import run_ask_pipeline
from app.semantic.store import load_semantic_layer
from app.semantic.value_index import ValueIndex

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# In-memory ValueIndex cache per dataset
_VALUE_INDEX_CACHE: dict[str, ValueIndex] = {}

def get_value_index(dataset_id: str, semantic) -> ValueIndex:
    if dataset_id not in _VALUE_INDEX_CACHE:
        idx = ValueIndex()
        idx.build(semantic.tables, semantic.metrics)
        _VALUE_INDEX_CACHE[dataset_id] = idx
    return _VALUE_INDEX_CACHE[dataset_id]

class CreateSessionRequest(BaseModel):
    dataset_id: str

class AskRequest(BaseModel):
    question: str

@router.post("")
def create_new_session(req: CreateSessionRequest):
    semantic = load_semantic_layer(req.dataset_id)
    if not semantic:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    session = create_session(req.dataset_id)
    return {"session_id": session.session_id, "dataset_id": session.dataset_id}

@router.post("/{sid}/ask")
def ask_question(sid: str, req: AskRequest):
    # Load session across all datasets
    from app.config import settings
    import os

    found_session = None
    target_dataset = None

    for d in os.listdir(settings.DATA_DIR):
        sess_path = os.path.join(settings.DATA_DIR, d, "sessions", f"{sid}.json")
        if os.path.exists(sess_path):
            found_session = load_session(d, sid)
            target_dataset = d
            break

    if not found_session:
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found.")

    semantic = load_semantic_layer(target_dataset)
    if not semantic:
        raise HTTPException(status_code=404, detail="Associated dataset not found.")

    v_index = get_value_index(target_dataset, semantic)

    try:
        response = run_ask_pipeline(
            session=found_session,
            semantic=semantic,
            question=req.question,
            value_index=v_index
        )
        return response
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "plan": None,
            "assumptions": [],
            "resolved_time": None,
            "sql": None,
            "result": None,
            "chart": None,
            "narrative": f"Error running analysis: {str(e)}",
            "dq_warnings": [],
            "why": None,
            "suggestions": ["Show total revenue", "Revenue by region"],
            "mode": "plan"
        }

@router.get("/{sid}/history")
def get_session_history(sid: str):
    from app.config import settings
    import os

    for d in os.listdir(settings.DATA_DIR):
        sess_path = os.path.join(settings.DATA_DIR, d, "sessions", f"{sid}.json")
        if os.path.exists(sess_path):
            sess = load_session(d, sid)
            return {"turns": [t.model_dump() for t in sess.history]}

    raise HTTPException(status_code=404, detail=f"Session '{sid}' not found.")
