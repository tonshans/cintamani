"""
Plugin 2 (Pilar Understand) — Thought Evolution.
Traces chronological evolution of concepts from raw initial thoughts to mature formulations.
Produces 'evolves_into' relationship edges for the Knowledge Graph (thought_relations).
"""

from __future__ import annotations
import uuid
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "thought_evolution",
    "display_name": "Thought Evolution",
    "category": "understand",
    "description": "Melacak bagaimana suatu ide berkembang secara kronologis dari pemikiran awal hingga matang.",
    "render_view_type": "document",
    "requires": [],
    "min_notes_threshold": 5,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    notes = context.get_notes(limit=60)
    if not notes:
        return {
            "title": "Thought Evolution - Belum Ada Data",
            "summary_markdown": "Belum ada catatan yang ditemukan pada periode waktu ini.",
            "payload": {},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    # Sort strictly chronologically from oldest to newest
    sorted_notes = sorted(notes, key=lambda x: x["created_at"])
    source_ids = [n["id"] for n in sorted_notes]

    formatted_notes = []
    for i, n in enumerate(sorted_notes[:35], 1):
        formatted_notes.append(
            f"[{i}] Timestamp: {n['created_at']} | ID: {n['id']}\nContent: {n['content']}\n"
        )
    notes_block = "\n".join(formatted_notes)

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah genealogis ide dan sejarawan pemikiran pribadi. "
        "Tugas Anda adalah menelusuri bagaimana pemikiran pengguna berevolusi dari waktu ke waktu. "
        "Identifikasi titik awal (Genesis), pergeseran perspektif (Shift), dan konvergensi pematangan (Maturation)."
    )

    user_prompt = f"""Berikut adalah kronologi catatan mikro pengguna (dari yang paling lama ke yang paling baru):
{notes_block}

Tuliskan analisis evolusi pemikiran dalam Markdown yang mencakup:
# Genealogi Pemikiran: Evolusi Ide Lintas Waktu
## 1. Benih Gagasan Awal (Genesis Phase)
Uraikan pemikiran awal yang paling mendasar atau belum terstruktur.
## 2. Percabangan & Pergeseran Sudut Pandang (Exploration & Pivot Phase)
Jelaskan bagaimana ide tersebut diuji, dimodifikasi, atau menemukan konteks baru.
## 3. Pematangan & Konvergensi Saat Ini (Maturation Phase)
Uraikan bentuk ide yang sekarang tampak mengerucut atau matang.

Sertakan ID catatan asli (`[ID: ...]`) pada setiap tahap sebagai rujukan jejak audit."""

    summary_md = await context.ollama.generate_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    # Generate thought_relations edges connecting sequential evolutionary notes
    relations: List[Dict[str, Any]] = []
    for i in range(len(sorted_notes) - 1):
        # Link adjacent notes that share chronological proximity
        relations.append(
            {
                "id": f"rel-{uuid.uuid4().hex[:10]}",
                "source_id": sorted_notes[i]["id"],
                "target_id": sorted_notes[i + 1]["id"],
                "relationship_type": "evolves_into",
                "weight": 0.7,
                "reason": f"Kronologi pemikiran dari {sorted_notes[i]['created_at'][:10]} ke {sorted_notes[i+1]['created_at'][:10]}",
                "generated_by": "thought_evolution",
            }
        )

    return {
        "title": "Genealogi & Evolusi Pemikiran Kronologis",
        "summary_markdown": summary_md,
        "payload": {
            "chronological_note_count": len(sorted_notes),
            "start_time": sorted_notes[0]["created_at"],
            "end_time": sorted_notes[-1]["created_at"],
        },
        "source_note_ids": source_ids[:35],
        "relations": relations[:15],
        "confidence": 0.85,
    }
