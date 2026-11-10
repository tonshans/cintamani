"""
Plugin 0 (Base Utility) — Vector Embedder.
Generates semantic embeddings for unembedded micro_notes and saves them to vector_index.
Can be invoked standalone or via context.call_plugin("vector_embedder") by other plugins.
"""

from __future__ import annotations
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "vector_embedder",
    "display_name": "Vector Embedder",
    "category": "utility",
    "description": "Menghasilkan representasi vektor semantik untuk catatan mikro dan menyimpannya ke indeks vektor.",
    "render_view_type": "utility",
    "requires": [],
    "min_notes_threshold": 0,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    """
    Scans for micro_notes lacking embeddings in the selected time frame,
    generates semantic vectors, and writes them to vector_index.
    """
    mode = context.time_filter.get("mode", "all_time")
    start_date = context.time_filter.get("start_date")
    end_date = context.time_filter.get("end_date")

    unembedded = context.db.get_unembedded_notes(
        mode=mode, start_date=start_date, end_date=end_date, limit=200
    )

    embedded_ids: List[str] = []
    model_name = context.ollama.embedding_model

    for note in unembedded:
        n_id = note["id"]
        content = note["content"]

        try:
            vector = await context.ollama.generate_embedding(content)
            if vector and len(vector) > 0:
                context.db.save_embedding(n_id, vector, model_name)
                embedded_ids.append(n_id)
        except Exception:
            continue

    return {
        "status": "success",
        "embedded_count": len(embedded_ids),
        "embedded_note_ids": embedded_ids,
        "model_name": model_name,
    }
