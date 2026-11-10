"""
Plugin 4 (Pilar Connect) — Idea Collision.
Forces collisions between disparate thought clusters to spark high-novelty breakthrough hypotheses.
Produces 'idea_collision' edges for the Knowledge Graph.
"""

from __future__ import annotations
import uuid
from typing import Any, Dict, List

__manifest__ = {
    "plugin_name": "idea_collision",
    "display_name": "Idea Collision",
    "category": "connect",
    "description": "Mempertemukan dua klaster pemikiran dari domain yang berbeda untuk memicu hipotesis terobosan baru.",
    "render_view_type": "cards",
    "requires": ["vector_embedder"],
    "min_notes_threshold": 5,
    "default_timeframe": "all_time",
    "prompt_version": "v1.0",
}


async def execute(context: Any) -> Dict[str, Any]:
    # Ensure vector embeddings exist
    try:
        await context.call_plugin("vector_embedder")
    except Exception:
        pass

    notes = context.get_notes(limit=30)
    if len(notes) < 2:
        return {
            "title": "Idea Collision - Data Tidak Cukup",
            "summary_markdown": "Dibutuhkan minimal 2 catatan berbeda untuk memicu tabrakan ide.",
            "payload": {"cards": []},
            "source_note_ids": [],
            "confidence": 0.0,
        }

    source_ids = [n["id"] for n in notes]
    notes_block = "\n".join(
        [f"[Item {i+1}] ID: {n['id']}\n{n['content']}" for i, n in enumerate(notes[:20])]
    )

    system_prompt = context.build_time_aware_system_prompt(
        "Anda adalah provokator inovasi dan katalis 'Idea Collision'. "
        "Ambil konsep-konsep dari domain atau topik yang sangat berbeda dalam catatan pengguna, "
        "lalu tabrakkan keduanya untuk melahirkan sintesis radikal atau hipotesis 'Bagaimana Jika?' (What-If)."
    )

    user_prompt = f"""Kumpulan catatan pengguna:
{notes_block}

Tugas:
Pilih 2 atau 3 pasang konsep yang saling kontras atau dari domain berbeda, lalu buatkan 'tabrakan ide' yang memicu inovasi.
Kembalikan dalam JSON:
{{
  "intro": "Pengantar singkat tentang potensi persilangan pemikiran ini",
  "collisions": [
    {{
      "title": "Nama Hipotesis Terobosan",
      "concept_a": {{ "id": "note_id_A", "snippet": "Kutipan ide A" }},
      "concept_b": {{ "id": "note_id_B", "snippet": "Kutipan ide B" }},
      "collision_synthesis": "Bagaimana jika Konsep A diterapkan pada Konsep B?",
      "actionable_experiment": "Langkah konkret atau eksperimen cepat untuk membuktikan ide ini"
    }}
  ]
}}"""

    result_json = await context.ollama.generate_json_completion(
        prompt=user_prompt, system_prompt=system_prompt
    )

    collisions = result_json.get("collisions", [])
    if not isinstance(collisions, list) or not collisions:
        collisions = [
            {
                "title": "Tabrakan Domain Silang",
                "concept_a": {"id": source_ids[0], "snippet": notes[0]["content"][:60]},
                "concept_b": {"id": source_ids[-1], "snippet": notes[-1]["content"][:60]},
                "collision_synthesis": "Penerapan prinsip dari catatan awal ke domain catatan terbaru.",
                "actionable_experiment": "Lakukan eksplorasi konsep dalam bentuk prototipe kecil.",
            }
        ]

    # Format Markdown
    md_lines = ["# Idea Collision: Eksperimen Persilangan Gagasan\n"]
    md_lines.append(result_json.get("intro", "Berikut adalah hasil tabrakan ide lintas domain:"))
    md_lines.append("\n---\n")

    relations: List[Dict[str, Any]] = []
    used_ids: List[str] = []

    for item in collisions:
        title = item.get("title", "Hipotesis Kolisi")
        cA = item.get("concept_a", {})
        cB = item.get("concept_b", {})
        synth = item.get("collision_synthesis", "")
        exp = item.get("actionable_experiment", "")

        idA = cA.get("id")
        idB = cB.get("id")

        md_lines.append(f"### {title}")
        md_lines.append(f"- **Konsep A:** {cA.get('snippet', '')} `[ID: {idA}]`")
        md_lines.append(f"- **Konsep B:** {cB.get('snippet', '')} `[ID: {idB}]`")
        md_lines.append(f"**Tabrakan Ide:** {synth}")
        md_lines.append(f"**Eksperimen yang Dapat Dicoba:** {exp}\n")

        if idA and idB:
            used_ids.extend([idA, idB])
            relations.append(
                {
                    "id": f"rel-{uuid.uuid4().hex[:10]}",
                    "source_id": idA,
                    "target_id": idB,
                    "relationship_type": "idea_collision",
                    "weight": 0.9,
                    "reason": title,
                    "generated_by": "idea_collision",
                }
            )

    return {
        "title": "Idea Collision: Tabrakan Konsep Lintas Domain",
        "summary_markdown": "\n".join(md_lines),
        "payload": {"cards": collisions},
        "source_note_ids": list(set(used_ids)) if used_ids else source_ids[:10],
        "relations": relations,
        "confidence": 0.86,
    }
