#!/usr/bin/env python3
"""
Re-embeds notes whose vector_index row was built with a different embedding
model or dimension (e.g. after switching embedding provider).

Usage:
    python reembed.py
"""

import asyncio
import logging

from app.core.config import get_config
from app.core.database import get_db
from app.core.ollama_client import SUPPORTED_EMBEDDING_PROVIDERS, get_ollama_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    cfg = get_config()
    db = get_db()
    client = get_ollama_client()

    provider = client.embedding_provider
    if provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        raise SystemExit(
            f"[!] Provider embedding '{provider}' tidak didukung. "
            f"Pakai: {', '.join(sorted(SUPPORTED_EMBEDDING_PROVIDERS))}"
        )

    model = client.embedding_model
    dim = client.embedding_dim
    print(f"[*] Re-embedding provider={provider} model={model} dim={dim}")

    total = 0
    while True:
        notes = db.get_stale_embedding_notes(model, dim, limit=100)
        if not notes:
            break

        embedded_in_batch = 0
        for note in notes:
            vector = await client.generate_embedding(note["content"])
            if not vector:
                print(f"[!] Embedding kosong untuk {note['id']}, dilewati.")
                continue
            if len(vector) != dim:
                print(f"[*] Dimensi aktual {len(vector)} != config {dim}. Sinkron config.")
                cfg.set("embedding_dim", len(vector))
                dim = len(vector)
            db.save_embedding(note["id"], vector, model)
            embedded_in_batch += 1
            total += 1
            print(f"[+] {note['id']} ({total})")

        if embedded_in_batch == 0:
            # Nothing progressed: stop instead of looping on the same notes forever.
            print("[!] Tidak ada catatan yang berhasil di-embed pada batch ini. Berhenti.")
            break

    print(f"[*] Selesai. {total} catatan di-embed ulang.")


if __name__ == "__main__":
    asyncio.run(main())
