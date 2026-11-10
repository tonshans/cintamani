"""
Plugin 6 (Pilar Create) — Project Seed Generator.
Aggregates interconnected thoughts into an actionable Project Blueprint.
Converts loose ideas into a defined problem statement, architecture, and 48-hour launch plan.
"""

from __future__ import annotations
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "project_seed_generator",
    "display_name": "Project Seed Generator",
    "category": "create",
    "description": "Menyusun draf proposal proyek utuh (Project Blueprint) dari sekumpulan catatan yang saling mendukung.",
    "render_view_type": "document",
    "requires": [],
    "min_notes_threshold": 5,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    notes = context.get_notes(limit=40)
    if not notes:
        return {
            "title": "Project Seed - Belum Ada Data",
            "summary_markdown": "Belum ada catatan yang ditemukan pada periode waktu ini.",
            "payload": {},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    source_ids = [n["id"] for n in notes]
    notes_block = "\n".join(
        [f"[ID: {n['id']}] {n['content']}" for n in notes[:25]]
    )

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah Arsitek Proyek dan Product Strategist tingkat tinggi. "
        "Tugas Anda adalah membaca potongan-potongan pemikiran pengguna dan merajutnya menjadi "
        "sebuah 'Project Seed Blueprint' yang terstruktur, bernilai nyata, dan dapat segera diwujudkan."
    )

    user_prompt = f"""Kumpulan catatan mentah pengguna:
{notes_block}

Identifikasi sebuah benih proyek yang paling potensial dan susunlah dalam format Markdown lengkap:
# Project Blueprint: [Nama Proyek yang Kuat & Menarik]
## 1. Masalah Utama (The Core Problem)
Apa friksi atau tantangan yang ingin diselesaikan berdasarkan catatan pengguna?
## 2. Solusi & Konsep Inti (The Solution Architecture)
Bagaimana proyek ini memecahkan masalah tersebut dengan elegan?
## 3. Tantangan Teknis & Risiko Utama (Technical Challenges & Risk)
Apa hambatan teknis atau operasional yang perlu diantisipasi sejak awal?
## 4. Langkah Awal 48 Jam (Immediate 48-Hour Action Plan)
Daftar 3-5 langkah konkret pertama yang bisa diselesaikan dalam 2 hari ke depan.

Sebutkan ID catatan rujukan asli (`[ID: ...]`) pada bagian yang relevan."""

    summary_md = await context.ollama.generate_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    payload = {
        "analyzed_notes_count": len(notes),
        "generator": "project_seed_generator",
    }

    return {
        "title": "Project Blueprint: Rencana Inkubasi Proyek",
        "summary_markdown": summary_md,
        "payload": payload,
        "source_note_ids": source_ids[:20],
        "confidence": 0.91,
    }
