"""
Plugin 7 (Pilar Create) — Task & Action Extractor.
Scans micro-notes to extract transactional intentions, pending tasks,
and concrete action items, categorizing them by urgency for 'tasks' render_view_type.
"""

from __future__ import annotations
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "task_extractor",
    "display_name": "Task & Action Extractor",
    "category": "create",
    "description": "Mengekstrak niat tindakan dan hal yang harus dikerjakan dari catatan menjadi daftar Action Items.",
    "render_view_type": "tasks",
    "requires": [],
    "min_notes_threshold": 3,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    notes = context.get_notes(limit=50)
    if not notes:
        return {
            "title": "Action Items - Belum Ada Data",
            "summary_markdown": "Belum ada catatan yang ditemukan pada periode waktu ini.",
            "payload": {"tasks": []},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    source_ids = [n["id"] for n in notes]
    notes_block = "\n".join(
        [f"[ID: {n['id']}] {n['content']}" for n in notes[:30]]
    )

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah Ekstraktor Tindakan Eksekutif (Action Items Extractor). "
        "Tugas Anda memisahkan renungan konseptual dari niat tindakan nyata (misal: 'perlu menghubungi...', 'harus beli...', 'coba riset...', 'jadwalkan...'). "
        "Ekstrak setiap niat tindakan menjadi tugas konkret dengan tingkat urgensi yang jelas."
    )

    user_prompt = f"""Kumpulan catatan mikro:
{notes_block}

Ekstrak seluruh niat tindakan yang terpendam.
Kembalikan respon JSON:
{{
  "task_summary": "Ringkasan 1-2 kalimat mengenai fokus aksi pengguna saat ini",
  "tasks": [
    {{
      "task": "Deskripsi tugas konkret dengan kata kerja aktif",
      "urgency": "high",
      "source_note_id": "ID_catatan_asli",
      "suggested_deadline": "Hari ini / Minggu ini / Kapan saja",
      "completed": false
    }}
  ]
}}
Urgency hanya boleh bernilai: 'high', 'medium', atau 'low'."""

    result_json = await context.ollama.generate_json_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    tasks = result_json.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        # Fallback task extraction
        tasks = [
            {
                "task": f"Tindak lanjuti pemikiran: {notes[0]['content'][:50]}...",
                "urgency": "medium",
                "source_note_id": source_ids[0],
                "suggested_deadline": "Minggu ini",
                "completed": False,
            }
        ]

    # Build Markdown Checklist
    md_lines = ["# Daftar Aksi Nyata (Action Items Extracted)\n"]
    md_lines.append(result_json.get("task_summary", "Berikut adalah tugas-tugas yang diekstrak dari catatan Anda:"))
    md_lines.append("\n---\n")

    referenced_ids = []
    for t in tasks:
        urg = t.get("urgency", "medium").upper()
        task_text = t.get("task", "")
        nid = t.get("source_note_id")
        deadline = t.get("suggested_deadline", "")

        md_lines.append(f"- [ ] **[{urg}]** {task_text} *(Batas: {deadline})* `[ID: {nid}]`")
        if nid:
            referenced_ids.append(nid)

    return {
        "title": "Daftar Tindakan Terstruktur (Action Items)",
        "summary_markdown": "\n".join(md_lines),
        "payload": {"tasks": tasks},
        "source_note_ids": list(set(referenced_ids)) if referenced_ids else source_ids[:10],
        "confidence": 0.92,
    }
