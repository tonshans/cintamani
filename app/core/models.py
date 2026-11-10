"""
Cintamani Pydantic Models & Data Contracts.
Strictly conforms to Section 2.3 of the System Architecture Document.
100% compatible with cintamani-android SyncClient.kt.
"""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class NoteMetadataPayload(BaseModel):
    typing_wpm: Optional[float] = None
    backspace_count: Optional[int] = None
    compose_duration_ms: Optional[int] = None
    vocal_wpm: Optional[float] = None
    rms_db_avg: Optional[float] = None
    rms_db_peak: Optional[float] = None
    coarse_lat: Optional[float] = None
    coarse_lon: Optional[float] = None
    plugin_flags: Dict[str, str] = Field(default_factory=dict)


class SyncNoteItem(BaseModel):
    id: str
    content: str
    created_at: str
    source: str = "cintamani-android"
    input_mode: Literal["text", "voice", "mixed"] = "text"
    metadata: NoteMetadataPayload = Field(default_factory=NoteMetadataPayload)


class SyncBatchRequest(BaseModel):
    device_id: str
    notes: List[SyncNoteItem]


class SyncBatchResponse(BaseModel):
    status: str = "success"
    synced_ids: List[str]
    server_time: str


class WebNoteCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    plugin_flags: Dict[str, str] = Field(default_factory=dict)


class TimeFilterPayload(BaseModel):
    mode: Literal[
        "all_time",
        "last_7_days",
        "last_30_days",
        "this_year",
        "custom_range",
    ] = "all_time"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ExploreRequest(BaseModel):
    plugin_name: str
    time_filter: TimeFilterPayload = Field(default_factory=TimeFilterPayload)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class InsightFeedbackRequest(BaseModel):
    feedback_status: Optional[Literal["unreviewed", "accepted", "rejected"]] = None
    is_pinned: Optional[bool] = None


class PingResponse(BaseModel):
    status: str = "alive"
    server_time: str
    ollama_reachable: bool = True
    llm_model: str
    llm_provider: str = "ollama"


class JobStatusResponse(BaseModel):
    job_id: str
    plugin_name: str
    status: Literal["queued", "running", "completed", "failed"]
    result_insight_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class PluginManifestItem(BaseModel):
    plugin_name: str
    display_name: str
    category: Literal["utility", "understand", "connect", "challenge", "create"]
    description: str
    render_view_type: Literal["utility", "document", "cards", "tasks", "graph"]
    min_notes_threshold: int
    is_ready: bool
    missing_notes_count: int
    requires: List[str] = Field(default_factory=list)
    dependencies_met: bool = True
    default_timeframe: str = "all_time"
    prompt_version: str = "v1.0"


class ActivePluginsResponse(BaseModel):
    total_notes_in_period: int
    plugins: List[PluginManifestItem]
