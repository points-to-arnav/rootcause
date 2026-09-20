import os
import shutil
import uuid
from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile
import duckdb
from app.config import settings
from app.ingestion.loader import ingest_to_duckdb
from app.profiling.types import infer_column_type, cast_and_recreate_table
from app.profiling.profiler import profile_table
from app.profiling.quality import run_quality_checks
from app.semantic.tagger import tag_column
from app.semantic.relationships import detect_relationships
from app.semantic.join_graph import JoinGraph
from app.semantic.metrics import register_metrics
from app.semantic.model import TableMeta, SemanticLayer
from app.semantic.store import save_semantic_layer, load_semantic_layer

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

def process_and_save_dataset(dataset_id: str, file_paths: List[str]) -> SemanticLayer:
    """Executes ingestion, profiling, DQ, and semantic layer generation."""
    db_path, schema_meta, notices = ingest_to_duckdb(dataset_id, file_paths)

    con = duckdb.connect(db_path, read_only=False)
    tables = {}
    table_profs = {}
    all_issues = []

    for tbl, smeta in schema_meta.items():
        cols = [r[0] for r in con.execute(f'DESCRIBE "{tbl}"').fetchall()]
        col_types = {}
        for c in cols:
            sample_vals = [r[0] for r in con.execute(f'SELECT "{c}" FROM "{tbl}" LIMIT 500').fetchall()]
            dtype, _ = infer_column_type(sample_vals, c)
            col_types[c] = dtype

        cast_and_recreate_table(con, tbl, col_types)
        prof = profile_table(con, tbl, col_types)
        table_profs[tbl] = prof

        tagged_cols = {
            c: tag_column(c, smeta["columns"][c]["display_name"], prof["columns"][c], prof["row_count"])
            for c in cols
        }
        tables[tbl] = TableMeta(
            name=tbl,
            display_name=smeta["display_name"],
            row_count=prof["row_count"],
            columns=tagged_cols
        )

        table_issues = run_quality_checks(con, tbl, prof)
        all_issues.extend(table_issues)

    tables_dict = {t: {"columns": table_profs[t]["columns"], "row_count": tmeta.row_count} for t, tmeta in tables.items()}
    relationships, orphan_issues = detect_relationships(con, tables_dict)
    all_issues.extend(orphan_issues)

    jg = JoinGraph(tables, relationships)
    fact_table = jg.pick_fact_table()
    tables[fact_table].role = "fact"
    time_info = jg.get_time_info(con, fact_table)
    metrics = register_metrics(tables, fact_table)

    semantic = SemanticLayer(
        dataset_id=dataset_id,
        tables=tables,
        relationships=relationships,
        metrics=metrics,
        time=time_info,
        quality_issues=all_issues
    )
    save_semantic_layer(semantic)
    con.close()
    return semantic

@router.post("")
async def upload_datasets(files: List[UploadFile] = File(...)):
    """Uploads Excel or CSV files, ingests them into DuckDB, and builds the semantic layer."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    raw_dir = os.path.join(settings.DATA_DIR, dataset_id, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    saved_paths = []
    for f in files:
        target_path = os.path.join(raw_dir, f.filename)
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        saved_paths.append(target_path)

    try:
        semantic = process_and_save_dataset(dataset_id, saved_paths)
        return {
            "status": "ok",
            "dataset_id": dataset_id,
            "tables": [
                {
                    "name": t.name,
                    "display_name": t.display_name,
                    "role": t.role,
                    "row_count": t.row_count,
                    "columns": [
                        {
                            "name": c.name,
                            "display_name": c.display_name,
                            "dtype": c.dtype,
                            "role": c.role,
                            "null_pct": c.null_pct
                        }
                        for c in t.columns.values()
                    ]
                }
                for t in semantic.tables.values()
            ],
            "relationships": [
                {"from": r.from_col, "to": r.to_col, "type": r.type, "confidence": r.confidence}
                for r in semantic.relationships
            ],
            "time": semantic.time.model_dump(),
            "quality_summary": {
                "high": sum(1 for i in semantic.quality_issues if i.get("severity") == "high"),
                "medium": sum(1 for i in semantic.quality_issues if i.get("severity") == "medium"),
                "low": sum(1 for i in semantic.quality_issues if i.get("severity") == "low"),
                "total": len(semantic.quality_issues)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process dataset: {str(e)}")

@router.post("/sample")
def load_sample_dataset():
    """Loads bundled retail_demo.xlsx for instant demo loading."""
    sample_path = "sample_data/retail_demo.xlsx"
    if not os.path.exists(sample_path):
        from sample_data.generate_retail import generate_retail_data
        generate_retail_data()

    dataset_id = "ds_retail_sample"
    semantic = process_and_save_dataset(dataset_id, [sample_path])
    return {
        "status": "ok",
        "dataset_id": dataset_id,
        "tables": [
            {
                "name": t.name,
                "display_name": t.display_name,
                "role": t.role,
                "row_count": t.row_count,
                "columns": [
                    {
                        "name": c.name,
                        "display_name": c.display_name,
                        "dtype": c.dtype,
                        "role": c.role,
                        "null_pct": c.null_pct
                    }
                    for c in t.columns.values()
                ]
            }
            for t in semantic.tables.values()
        ],
        "relationships": [
            {"from": r.from_col, "to": r.to_col, "type": r.type, "confidence": r.confidence}
            for r in semantic.relationships
        ],
        "time": semantic.time.model_dump(),
        "quality_summary": {
            "high": sum(1 for i in semantic.quality_issues if i.get("severity") == "high"),
            "medium": sum(1 for i in semantic.quality_issues if i.get("severity") == "medium"),
            "low": sum(1 for i in semantic.quality_issues if i.get("severity") == "low"),
            "total": len(semantic.quality_issues)
        }
    }

@router.get("/{id}/semantic")
def get_semantic(id: str):
    sem = load_semantic_layer(id)
    if not sem:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return sem.model_dump(by_alias=True)

@router.get("/{id}/quality")
def get_quality(id: str):
    sem = load_semantic_layer(id)
    if not sem:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {
        "issues": sem.quality_issues,
        "summary": {
            "high": sum(1 for i in sem.quality_issues if i.get("severity") == "high"),
            "medium": sum(1 for i in sem.quality_issues if i.get("severity") == "medium"),
            "low": sum(1 for i in sem.quality_issues if i.get("severity") == "low"),
            "total": len(sem.quality_issues)
        }
    }
