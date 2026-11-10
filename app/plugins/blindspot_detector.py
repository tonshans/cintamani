"""
Plugin 5 (Pilar Challenge) — Blind Spot & Assumption Detector.
Critiques user's thoughts to expose Hidden Assumptions, Critical Blind Spots,
Knowledge Gaps, and Recurring Unresolved Loops.
"""

from __future__ import annotations
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "blindspot_detector",
    "display_name": "Blindspot & Assumption Detector",
    "category": "challenge",
    "description": "Mendeteksi asumsi tak teruji, titik buta, kesenjangan pengetahuan, dan keluhan berulang tanpa tindakan.",
    "render_view_type": "cards",
    "requires": [],
    "min_notes_threshold": 5,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    notes = context.get_notes(limit=40)
    if not notes:
        return {
            "title": "Blindspot Detector - Belum Ada Data",
            "summary_markdown": "Belum ada catatan yang ditemukan pada periode waktu ini.",
            "payload": {"cards": []},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    source_ids = [n["id"] for n in notes]
    notes_block = "\n".join(
        [f"[ID: {n['id']}] {n['content']}" for n in notes[:25]]
    )

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah Mitra Kritis (Devil's Advocate) dan auditor pemikiran objektif. "
        "Tugas Anda BUKAN memuji pengguna, melainkan menantang asumsinya, menunjuk titik buta (blind spots) yang terlewat, "
        "dan mendeteksi pola keluhan atau masalah berulang yang tidak kunjung dieksekusi."
    )

    user_prompt = f"""Catatan mikro pengguna:
{notes_block}

Lakukan audit pemikiran yang tajam dan konstruktif.
Kembalikan JSON dengan format:
{{
  "critique_overview": "Ringkasan 2 kalimat mengenai kecenderungan titik buta pengguna",
  "cards": [
    {{
      "category": "Hidden Assumption",
      "title": "Judul Asumsi Tak Teruji",
      "target_note_id": "ID_catatan_terkait",
      "critique": "Penjelasan mengapa ini merupakan asumsi yang berisiko",
      "counter_question": "Pertanyaan reflektif untuk membongkar asumsi ini"
    }},
    {{
      "category": "Blind Spot",
      "title": "Judul Aspek yang Luput Dipikirkan",
      "target_note_id": "ID_catatan_terkait",
      "critique": "Aspek penting (misal: operasional, biaya, psikologis, hukum, skalabilitas) yang belum tersentuh",
      "counter_question": "Pertanyaan kunci untuk menutup titik buta ini"
    }},
    {{
      "category": "Recurring Loop",
      "title": "Judul Pola Berulang Tanpa Aksi",
      "target_note_id": "ID_catatan_terkait",
      "critique": "Masalah atau renungan yang berputar-putar tanpa langkah nyata",
      "counter_question": "Apa keputusan terkecil yang bisa diambil sekarang untuk memutus loop ini?"
    }}
  ]
}}"""

    result_json = await context.ollama.generate_json_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    cards = result_json.get("cards", [])
    if not isinstance(cards, list) or not cards:
        cards = [
            {
                "category": "Blind Spot",
                "title": "Validasi Asumsi Awal",
                "target_note_id": source_ids[0],
                "critique": "Gagasan yang tercatat perlu diuji dengan feedback eksternal nyata.",
                "counter_question": "Bagaimana cara membuktikan premis ini dalam 48 jam ke depan?",
            }
        ]

    # Build Markdown Summary
    md_lines = ["# Audit Pemikiran: Blind Spots & Hidden Assumptions\n"]
    md_lines.append(result_json.get("critique_overview", "Berikut adalah hasil audit kritis terhadap kumpulan catatan Anda:"))
    md_lines.append("\n---\n")

    referenced_ids = []
    for c in cards:
        cat = c.get("category", "Tantangan")
        title = c.get("title", "Kritik Pemikiran")
        t_id = c.get("target_note_id")
        crit = c.get("critique", "")
        cq = c.get("counter_question", "")

        md_lines.append(f"### [{cat}] {title}")
        if t_id:
            md_lines.append(f"*Rujukan Catatan:* `[ID: {t_id}]`")
            referenced_ids.append(t_id)
        md_lines.append(f"**Analisis Kritis:** {crit}")
        md_lines.append(f"**Pertanyaan Pembuka Pikiran:** *{cq}*\n")

    return {
        "title": "Audit Pemikiran: Blind Spots & Asumsi Tersembunyi",
        "summary_markdown": "\n".join(md_lines),
        "payload": {"cards": cards},
        "source_note_ids": list(set(referenced_ids)) if referenced_ids else source_ids[:10],
        "confidence": 0.89,
    }
