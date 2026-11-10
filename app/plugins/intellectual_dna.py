"""
Plugin 1 (Pilar Understand) — Intellectual DNA.
Analyzes core cognitive patterns, dominant topic clusters, recurring inquiries,
and behavioral rhythms from micro_notes and silent keystroke/vocal metadata.
"""

from __future__ import annotations
import json
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "intellectual_dna",
    "display_name": "Intellectual DNA",
    "category": "understand",
    "description": "Menganalisis klaster minat utama, pertanyaan berulang, dan ritme kognitif pengguna.",
    "render_view_type": "document",
    "requires": [],
    "min_notes_threshold": 5,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    notes = context.get_notes(limit=80)
    if not notes:
        return {
            "title": "Intellectual DNA - Belum Ada Data",
            "summary_markdown": "Belum ada catatan yang ditemukan pada periode waktu ini.",
            "payload": {},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    source_ids = [n["id"] for n in notes]

    # Calculate cognitive rhythm metrics from silent metadata
    hour_counts = Counter()
    wpm_list = []
    vocal_list = []

    for n in notes:
        try:
            dt = datetime.fromisoformat(n["created_at"].replace("Z", "+00:00"))
            hour_counts[dt.hour] += 1
        except Exception:
            pass

        meta = n.get("metadata", {}) or {}
        if meta.get("typing_wpm"):
            wpm_list.append(meta["typing_wpm"])
        if meta.get("vocal_wpm"):
            vocal_list.append(meta["vocal_wpm"])

    avg_typing_wpm = round(sum(wpm_list) / len(wpm_list), 1) if wpm_list else None
    avg_vocal_wpm = round(sum(vocal_list) / len(vocal_list), 1) if vocal_list else None
    peak_hour = hour_counts.most_common(1)[0][0] if hour_counts else 9

    # Prepare prompt for LLM
    notes_sample = []
    for i, n in enumerate(notes[:40], 1):
        notes_sample.append(f"[{i}] (ID: {n['id']} | {n['created_at']}): {n['content']}")
    notes_text = "\n".join(notes_sample)

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah analis kognitif dan epistemologi berkelas dunia. "
        "Tugas Anda adalah memetakan 'Intellectual DNA' pengguna berdasarkan sekumpulan catatan mikro mentah. "
        "Temukan pola pemikiran sejati, topik yang terus-menerus menarik perhatiannya, dan rasa ingin tahu yang mendasari."
    )

    user_prompt = f"""Berikut adalah sampel catatan mikro pengguna:
{notes_text}

Statistik Ritme Kognitif:
- Jam pencatatan paling aktif: pukul {peak_hour:02d}:00
- Kecepatan ketik rata-rata: {avg_typing_wpm or 'N/A'} WPM
- Kecepatan vokal rata-rata: {avg_vocal_wpm or 'N/A'} WPM

Analisis dan berikan respons dalam format Markdown terstruktur yang memuat:
# Intellectual DNA: Pemetaan Pola Pikir & Arketipe Kognitif
## 1. Klaster Minat & Tema Dominan (dengan persentase estimasi fokus)
## 2. Pola Pertanyaan yang Terus Berulang (Pertanyaan Filosofis & Teknis Inti)
## 3. Ritme & Gaya Kognitif (berdasarkan jam aktif dan dinamika input)
## 4. Sintesis Intuitif (Siapakah pengguna ini dalam cara ia berpikir?)

Sebutkan minimal 3 ID catatan asli (contoh: `[ID: ...]`) sebagai bukti rujukan dalam analisis Anda."""

    summary_md = await context.ollama.generate_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    payload = {
        "total_analyzed_notes": len(notes),
        "peak_hour": peak_hour,
        "avg_typing_wpm": avg_typing_wpm,
        "avg_vocal_wpm": avg_vocal_wpm,
        "sample_size": min(len(notes), 40),
    }

    return {
        "title": "Profil Intellectual DNA & Pola Kognitif",
        "summary_markdown": summary_md,
        "payload": payload,
        "source_note_ids": source_ids[:40],
        "confidence": 0.88,
    }
