"""
Cintamani REST API Routes (/api/v1/*).
Implements the locked I/O API contracts from Section 3 of System Architecture.
Guarded by verify_api_token dependency.
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.core.config import get_config
from app.core.database import get_db
from app.core.job_runner import get_job_runner
from app.core.models import (
    ActivePluginsResponse,
    ExploreRequest,
    InsightFeedbackRequest,
    JobStatusResponse,
    PingResponse,
    SyncBatchRequest,
    SyncBatchResponse,
    WebNoteCreateRequest,
)
from app.core.ollama_client import get_ollama_client
from app.core.plugin_registry import get_plugin_registry
from app.core.security import verify_api_token

router = APIRouter(prefix="/api/v1", tags=["Cintamani API"])
TIME_MODE_PATTERN = "^(all_time|last_7_days|last_30_days|this_year|custom_range)$"
VALID_LLM_PROVIDERS = {"ollama", "openai", "openai_compatible", "gemini", "claude"}
VALID_EMBEDDING_PROVIDERS = {"ollama", "openai", "openai_compatible", "gemini"}
SECRET_CONFIG_KEYS = {"llm_api_key", "gemini_api_key", "openai_api_key", "anthropic_api_key"}


# -----------------------------------------------------------------
# 3.1. Health Check & Connection Test
# -----------------------------------------------------------------
@router.get("/ping", response_model=PingResponse)
async def ping(token: str = Depends(verify_api_token)):
    """
    Health check endpoint for Android SyncClient and Web UI connection status.
    """
    ollama = get_ollama_client()
    reachable, _ = await ollama.check_health()
    now_iso = datetime.now(timezone.utc).isoformat()

    return PingResponse(
        status="alive",
        server_time=now_iso,
        ollama_reachable=reachable,
        llm_model=ollama.model_name,
        llm_provider=ollama.provider,
    )


# -----------------------------------------------------------------
# 3.2. Batch Ingestion from Android Node
# -----------------------------------------------------------------
@router.post("/sync", response_model=SyncBatchResponse)
async def sync_notes(
    payload: SyncBatchRequest, token: str = Depends(verify_api_token)
):
    """
    Append-only idempotent ingestion of micro_notes from cintamani-android.
    """
    db = get_db()
    notes_dicts = [n.model_dump() for n in payload.notes]
    synced_ids = db.insert_notes_batch(payload.device_id, notes_dicts)
    now_iso = datetime.now(timezone.utc).isoformat()

    return SyncBatchResponse(
        status="success",
        synced_ids=synced_ids,
        server_time=now_iso,
    )


# -----------------------------------------------------------------
# 3.3. Alternative Web Note Capture & Listing
# -----------------------------------------------------------------
@router.post("/notes")
async def create_web_note(
    payload: WebNoteCreateRequest, token: str = Depends(verify_api_token)
):
    """
    Creates a new note directly from the Web Dashboard.
    """
    db = get_db()
    note_id = str(uuid.uuid4())
    created = db.create_web_note(
        note_id=note_id,
        content=payload.content,
        plugin_flags=payload.plugin_flags,
    )
    return {"status": "success", "note": created}


@router.get("/notes")
async def get_notes(
    mode: str = Query("all_time", pattern=TIME_MODE_PATTERN),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    token: str = Depends(verify_api_token),
):
    """
    Retrieves stored micro_notes with optional temporal pre-filtering.
    """
    db = get_db()
    notes, total = db.get_notes(
        mode=mode,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "notes": notes}


# -----------------------------------------------------------------
# 3.4. Hybrid Search Engine (Exact Keyword + Semantic Vector)
# -----------------------------------------------------------------
@router.get("/search")
async def search_notes(
    q: str = Query(..., min_length=1),
    search_type: str = Query("hybrid", pattern="^(keyword|semantic|hybrid)$"),
    mode: str = Query("all_time", pattern=TIME_MODE_PATTERN),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(verify_api_token),
):
    """
    Executes Keyword FTS, Semantic Vector, or Hybrid Search with SQL time pre-filtering.
    """
    db = get_db()
    ollama = get_ollama_client()

    try:
        if search_type == "keyword":
            results = db.search_keyword(
                q, mode=mode, start_date=start_date, end_date=end_date, limit=limit
            )
        elif search_type == "semantic":
            query_vector = await ollama.generate_embedding(q)
            results = db.search_semantic(
                query_vector,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
        else:  # hybrid
            query_vector = await ollama.generate_embedding(q)
            results = db.search_hybrid(
                query_text=q,
                query_vector=query_vector,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )

        return {"query": q, "search_type": search_type, "count": len(results), "results": results}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# -----------------------------------------------------------------
# 3.5. Active Plugins & Data Threshold Status
# -----------------------------------------------------------------
@router.get("/active-plugins")
async def get_active_plugins(
    mode: str = Query("all_time", pattern=TIME_MODE_PATTERN),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    token: str = Depends(verify_api_token),
):
    """
    Returns active plugins for the Web UI Sidebar with readiness threshold checks.
    """
    db = get_db()
    registry = get_plugin_registry()
    time_filter = {"mode": mode, "start_date": start_date, "end_date": end_date}

    total_notes = db.count_notes_in_period(mode, start_date, end_date)
    plugins_info = registry.list_plugins_info(time_filter)

    return {
        "total_notes_in_period": total_notes,
        "plugins": plugins_info,
    }


# -----------------------------------------------------------------
# 3.6. Trigger On-Demand AI Exploration
# -----------------------------------------------------------------
@router.post("/explore", status_code=status.HTTP_202_ACCEPTED)
async def trigger_exploration(
    payload: ExploreRequest, token: str = Depends(verify_api_token)
):
    """
    Triggers an asynchronous AI exploration job and immediately returns job_id in < 50ms.
    """
    registry = get_plugin_registry()
    plugin = registry.get_plugin(payload.plugin_name)

    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plugin '{payload.plugin_name}' tidak terdaftar.",
        )

    if not plugin.get("dependencies_met", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dependensi plugin '{payload.plugin_name}' belum terpenuhi.",
        )

    # Check note threshold
    db = get_db()
    tf = payload.time_filter.model_dump()
    mode = tf.get("mode", "all_time")
    s_dt = tf.get("start_date")
    e_dt = tf.get("end_date")

    total_notes = db.count_notes_in_period(mode, s_dt, e_dt)
    threshold = plugin["manifest"].get("min_notes_threshold", 0)

    if total_notes < threshold:
        missing = threshold - total_notes
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Catatan tidak cukup untuk {plugin['manifest'].get('display_name')}. Kurang {missing} catatan.",
        )

    runner = get_job_runner()
    job_id = runner.submit_job(
        plugin_name=payload.plugin_name,
        time_filter=tf,
        parameters=payload.parameters,
    )

    return {
        "job_id": job_id,
        "plugin_name": payload.plugin_name,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# -----------------------------------------------------------------
# 3.7. Poll AI Job Status
# -----------------------------------------------------------------
@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, token: str = Depends(verify_api_token)):
    """
    Polls execution status of an asynchronous exploration job.
    """
    db = get_db()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' tidak ditemukan.",
        )

    return JobStatusResponse(**job)


# -----------------------------------------------------------------
# 3.8. Insights, Provenance & Feedback Loop
# -----------------------------------------------------------------
@router.get("/insights")
async def list_insights(
    plugin_name: Optional[str] = Query(None),
    feedback_status: Optional[str] = Query(None),
    pinned_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    token: str = Depends(verify_api_token),
):
    """
    Returns insights enriched with full source_notes text for the Provenance Audit Drawer.
    """
    db = get_db()
    insights = db.list_insights(
        plugin_name=plugin_name,
        feedback_status=feedback_status,
        pinned_only=pinned_only,
        limit=limit,
    )
    return {"count": len(insights), "insights": insights}


@router.post("/insights/{insight_id}/feedback")
async def update_insight_feedback(
    insight_id: str,
    payload: InsightFeedbackRequest,
    token: str = Depends(verify_api_token),
):
    """
    Updates feedback status (accepted / rejected / unreviewed) or pinned state.
    """
    db = get_db()
    success = db.update_insight_feedback(
        insight_id=insight_id,
        feedback_status=payload.feedback_status,
        is_pinned=payload.is_pinned,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Insight '{insight_id}' tidak ditemukan.",
        )
    return {"status": "success", "insight_id": insight_id}


# -----------------------------------------------------------------
# 3.9. Thought Constellation Knowledge Graph Data
# -----------------------------------------------------------------
@router.get("/graph")
async def get_graph(
    mode: str = Query("all_time", pattern=TIME_MODE_PATTERN),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    token: str = Depends(verify_api_token),
):
    """
    Returns nodes and edges formatted for Vis-Network graph visualization.
    """
    db = get_db()
    graph_data = db.get_graph_data(mode=mode, start_date=start_date, end_date=end_date)
    return graph_data


# -----------------------------------------------------------------
# 3.10. 1-Click Backup Export
# -----------------------------------------------------------------
@router.get("/export")
async def export_brain(token: str = Depends(verify_api_token)):
    """
    1-Click Backup: Dumps micro_notes, insights, and thought_relations as JSON.
    """
    db = get_db()
    export_payload = db.export_all_data()
    content_str = json.dumps(export_payload, indent=2, ensure_ascii=False)

    return Response(
        content=content_str,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="cintamani_brain_export.json"'
        },
    )


# -----------------------------------------------------------------
# Server Configuration Endpoint (for Web Settings Modal)
# -----------------------------------------------------------------
@router.get("/config")
async def get_server_config(token: str = Depends(verify_api_token)):
    """Returns safe server configuration for the Web UI."""
    cfg = get_config().get_all()
    # Mask secrets
    return {
        "server_name": cfg.get("server_name"),
        "host": cfg.get("host"),
        "port": cfg.get("port"),
        "llm_provider": cfg.get("llm_provider"),
        "llm_base_url": cfg.get("llm_base_url"),
        "ollama_base_url": cfg.get("ollama_base_url"),
        "llm_model": cfg.get("llm_model"),
        "embedding_provider": cfg.get("embedding_provider"),
        "embedding_model": cfg.get("embedding_model"),
        "embedding_dim": cfg.get("embedding_dim"),
        "has_llm_key": bool(cfg.get("llm_api_key")),
        "has_gemini_key": bool(cfg.get("gemini_api_key")),
        "has_openai_key": bool(cfg.get("openai_api_key")),
        "has_claude_key": bool(cfg.get("anthropic_api_key")),
    }


@router.post("/config")
async def update_server_config(
    payload: Dict[str, Any], token: str = Depends(verify_api_token)
):
    """Updates server configuration options."""
    cfg = get_config()
    allowed_keys = [
        "server_name",
        "llm_provider",
        "llm_base_url",
        "llm_api_key",
        "ollama_base_url",
        "llm_model",
        "embedding_provider",
        "embedding_model",
        "embedding_dim",
        "gemini_api_key",
        "openai_api_key",
        "anthropic_api_key",
    ]
    updates = {k: v for k, v in payload.items() if k in allowed_keys}
    # Never wipe a stored secret with an empty form field.
    updates = {
        k: v
        for k, v in updates.items()
        if not (k in SECRET_CONFIG_KEYS and not str(v).strip())
    }

    if "llm_provider" in updates and updates["llm_provider"] not in VALID_LLM_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"llm_provider tidak valid. Pilihan: {sorted(VALID_LLM_PROVIDERS)}",
        )
    if (
        "embedding_provider" in updates
        and updates["embedding_provider"] not in VALID_EMBEDDING_PROVIDERS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"embedding_provider tidak valid. Pilihan: {sorted(VALID_EMBEDDING_PROVIDERS)}",
        )

    merged = {**cfg.get_all(), **updates}
    if merged.get("llm_provider") == "openai_compatible" and not (
        merged.get("llm_base_url") or ""
    ).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="llm_base_url wajib diisi untuk provider openai_compatible.",
        )

    if updates:
        cfg.update(updates)
    return {"status": "success", "updated": {k: "***" if k in SECRET_CONFIG_KEYS else v for k, v in updates.items()}}
