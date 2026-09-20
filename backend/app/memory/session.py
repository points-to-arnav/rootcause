import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.config import settings
from app.planner.plan_schema import Plan

class Turn(BaseModel):
    turn: int
    question: str
    plan: Optional[Dict[str, Any]] = None
    summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class SessionState(BaseModel):
    session_id: str
    dataset_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_plan: Optional[Dict[str, Any]] = None
    last_result_head: Optional[Dict[str, Any]] = None
    history: List[Turn] = []

def get_session_path(dataset_id: str, session_id: str) -> str:
    s_dir = os.path.join(settings.DATA_DIR, dataset_id, "sessions")
    os.makedirs(s_dir, exist_ok=True)
    return os.path.join(s_dir, f"{session_id}.json")

def create_session(dataset_id: str) -> SessionState:
    sid = f"s_{uuid.uuid4().hex[:8]}"
    state = SessionState(session_id=sid, dataset_id=dataset_id)
    save_session(state)
    return state

def save_session(state: SessionState):
    path = get_session_path(state.dataset_id, state.session_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))

def load_session(dataset_id: str, session_id: str) -> Optional[SessionState]:
    path = get_session_path(dataset_id, session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return SessionState.model_validate(json.load(f))
