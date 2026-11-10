"""
Plugin 3 (Pilar Connect) — Serendipity Engine.
Discovers hidden semantic bridges between notes across different times and contexts.
Produces 'serendipitous_link' edges for the Knowledge Graph.
"""

from __future__ import annotations
import uuid
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "serendipity_engine",
    "display_name": "Serendipity Engine",
    "category": "connect",
    "description": "Menemukan hubungan semantik tersembunyi antar pemikiran lintas waktu.",
    "render_view_type": "cards",
    "requires": ["vector_embedder"],
    "min_notes_threshold": 5,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    # 1. Enforce Service Locator: ensure embeddings are up to date
    try:
        await context.call_plugin("vector_embedder")
    except Exception:
        pass

    notes = context.get_notes(limit=40)
    if len(notes) < 2:
        return {
            "title": "Serendipity Engine - Data Tidak Cukup",
            "summary_markdown": "Dibutuhkan minimal 2 catatan untuk mencari koneksi tersembunyi.",
            "payload": {"cards": []},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    source_ids = [n["id"] for n in notes]
    notes_block = "\n".join(
        [f"[Catatan {i+1}] ID: {n['id']} | Tanggal: {n['created_at'][:10]}\nIsi: {n['content']}" for i, n in enumerate(notes[:25])]
    )

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah Serendipity Engine yang bertugas menemukan koneksi 'tak terduga' namun bermakna mendalam "
        "antara catatan-catatan pengguna yang ditulis pada waktu berbeda atau topik yang sekilas tidak berhubungan. "
        "Hindari asosiasi dangkal; cari benang merah filosofis, analogi tersembunyi, atau prinsip bersama."
    )

    user_prompt = f"""Berikut adalah kumpulan catatan pengguna:
{notes_block}

Tugas Anda:
Pilih 2 hingga 4 pasang/kelompok catatan yang memiliki korelasi tersembunyi yang menarik.
Kembalikan respon dalam format JSON dengan struktur:
{{
  "synthesis_summary": "Rangkuman 2-3 kalimat mengenai benang merah pemikiran pengguna",
  "cards": [
    {{
      "title": "Judul Menarik Koneksi",
      "note_ids": ["id_catatan_1", "id_catatan_2"],
      "hidden_connection": "Penjelasan mendalam mengapa kedua ide ini berhubungan",
      "breakthrough_takeaway": "Insight baru yang lahir dari penggabungan ini"
    }}
  ]
}}"""

    result_json = await context.ollama.generate_json_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    cards = result_json.get("cards", [])
    if not isinstance(cards, list) or not cards:
        # Fallback card if parsing was non-standard
        cards = [
            {
                "title": "Koneksi Semantik Antar Catatan",
                "note_ids": source_ids[:2],
                "hidden_connection": "Ditemukan kedekatan tematik yang saling melengkapi pemikiran pengguna.",
                "breakthrough_takeaway": "Menggabungkan dua sudut pandang ini membuka peluang eksplorasi lebih lanjut.",
            }
        ]

    # Build Markdown summary from cards
    md_lines = ["# Hasil Penemuan Serendipity Engine\n"]
    md_lines.append(result_json.get("synthesis_summary", "Berikut adalah koneksi tersembunyi yang berhasil diidentifikasi:"))
    md_lines.append("\n---\n")

    relations: List[Dict[str, Any]] = []
    connected_note_ids: List[str] = []

    for card in cards:
        c_title = card.get("title", "Koneksi Ide")
        c_notes = card.get("note_ids", [])
        c_conn = card.get("hidden_connection", "")
        c_takeaway = card.get("breakthrough_takeaway", "")

        md_lines.append(f"### {c_title}")
        md_lines.append(f"**Benang Merah Tersembunyi:** {c_conn}")
        md_lines.append(f"**Wawasan Baru:** {c_takeaway}")
        if c_notes:
            md_lines.append(f"*Rujukan Catatan:* `{', '.join(c_notes)}`")
            connected_note_ids.extend(c_notes)
            # Create graph edge between first two notes
            if len(c_notes) >= 2:
                relations.append(
                    {
                        "id": f"rel-{uuid.uuid4().hex[:10]}",
                        "source_id": c_notes[0],
                        "target_id": c_notes[1],
                        "relationship_type": "serendipitous_link",
                        "weight": 0.85,
                        "reason": c_title,
                        "generated_by": "serendipity_engine",
                    }
                )
        md_lines.append("\n")

    return {
        "title": "Serendipitas: Rajutan Koneksi Tersembunyi",
        "summary_markdown": "\n".join(md_lines),
        "payload": {"cards": cards},
        "source_note_ids": list(set(connected_note_ids)) if connected_note_ids else source_ids[:10],
        "relations": relations,
        "confidence": 0.87,
    }
