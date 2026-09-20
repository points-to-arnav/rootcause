import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.analysis.dashboard import generate_management_dashboard
from app.semantic.store import load_semantic_layer

router = APIRouter(prefix="/api/datasets", tags=["dashboard"])

class DashboardRequest(BaseModel):
    session_id: Optional[str] = None

@router.post("/{id}/dashboard")
def get_dashboard(id: str, req: Optional[DashboardRequest] = None):
    semantic = load_semantic_layer(id)
    if not semantic:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    db_path = os.path.join(settings.DATA_DIR, id, "data.duckdb")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Dataset DuckDB file not found.")

    try:
        dash = generate_management_dashboard(db_path, semantic)
        return dash
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard: {str(e)}")
