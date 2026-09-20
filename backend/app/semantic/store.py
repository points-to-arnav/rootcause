import json
import os
from typing import Optional
from app.config import settings
from app.semantic.model import SemanticLayer

def save_semantic_layer(semantic: SemanticLayer):
    dataset_dir = os.path.join(settings.DATA_DIR, semantic.dataset_id)
    os.makedirs(dataset_dir, exist_ok=True)
    path = os.path.join(dataset_dir, "semantic.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(semantic.model_dump_json(by_alias=True, indent=2))

def load_semantic_layer(dataset_id: str) -> Optional[SemanticLayer]:
    path = os.path.join(settings.DATA_DIR, dataset_id, "semantic.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SemanticLayer.model_validate(data)
