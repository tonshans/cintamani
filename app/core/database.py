"""
Cintamani Thread-Safe DuckDB Manager.
Implements the 5 Core Tables, Idempotent Note Ingestion, SQL Pre-Filtering,
Cosine Similarity Vector Search, Hybrid Keyword Search, Graph Data Extraction,
and 1-Click Complete JSON Export.
"""

from __future__ import annotations
import json
import math
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb

from app.core.config import get_config


class DuckDBManager:
    """Thread-safe Singleton Manager for the DuckDB persistent storage."""

    _instance: Optional[DuckDBManager] = None
    _lock = threading.RLock()
    _conn: Optional[duckdb.DuckDBPyConnection] = None

    def __new__(cls) -> DuckDBManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_db()
            return cls._instance

    def _init_db(self) -> None:
        """Initializes connection and creates the 5 core tables."""
        db_path_str = get_config().get("duckdb_path", "data/cintamani_brain.duckdb")
        db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = duckdb.connect(str(db_path))
        self._create_tables()
        self._seed_sample_data()

    def _create_tables(self) -> None:
        """Creates the 5 core tables defined in the Architecture specification."""
        with self._lock:
            # 1. micro_notes (IMMUTABLE SOURCE OF TRUTH)
            self._conn.execute("""
            CREATE TABLE IF NOT EXISTS micro_notes (
                id VARCHAR PRIMARY KEY,
                device_id VARCHAR NOT NULL,
                content VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                source VARCHAR NOT NULL,
                input_mode VARCHAR NOT NULL,
                typing_wpm DOUBLE,
                backspace_count INTEGER,
                compose_duration_ms BIGINT,
                vocal_wpm DOUBLE,
                rms_db_avg DOUBLE,
                rms_db_peak DOUBLE,
                coarse_lat DOUBLE,
                coarse_lon DOUBLE,
                plugin_flags_json VARCHAR NOT NULL DEFAULT '{}',
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. vector_index
            self._conn.execute("""
            CREATE TABLE IF NOT EXISTS vector_index (
                note_id VARCHAR PRIMARY KEY,
                embedding FLOAT[],
                embedding_dim INTEGER NOT NULL,
                model_name VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. insights (THE BLACKBOARD)
            self._conn.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id VARCHAR PRIMARY KEY,
                plugin_name VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                summary_markdown VARCHAR NOT NULL,
                payload_json VARCHAR NOT NULL DEFAULT '{}',
                source_note_ids_json VARCHAR NOT NULL DEFAULT '[]',
                time_filter_json VARCHAR NOT NULL DEFAULT '{}',
                ai_metadata_json VARCHAR NOT NULL DEFAULT '{}',
                feedback_status VARCHAR NOT NULL DEFAULT 'unreviewed',
                is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 4. thought_relations (Knowledge Graph)
            self._conn.execute("""
            CREATE TABLE IF NOT EXISTS thought_relations (
                id VARCHAR PRIMARY KEY,
                source_id VARCHAR NOT NULL,
                target_id VARCHAR NOT NULL,
                relationship_type VARCHAR NOT NULL,
                weight DOUBLE NOT NULL DEFAULT 0.5,
                reason VARCHAR NOT NULL DEFAULT '',
                generated_by VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 5. analysis_jobs (Async Job Tracking)
            self._conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                job_id VARCHAR PRIMARY KEY,
                plugin_name VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                request_json VARCHAR NOT NULL DEFAULT '{}',
                result_insight_id VARCHAR,
                error_message VARCHAR,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMPTZ
            );
            """)

    def _seed_sample_data(self) -> None:
        """Seeds realistic sample micro-notes, graph relations, and initial insight if empty."""
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM micro_notes").fetchone()[0]
            if count > 0:
                return

            sample_notes = [
                {
                    "id": "note-esp32-lora",
                    "device_id": "cintamani-phone-01",
                    "content": "Eksperimen telemetri cuaca: gunakan modul ESP32 dengan transceiver LoRa SX1278 frekuensi 433MHz untuk transmisi data jarak jauh 2km tanpa koneksi internet seluler.",
                    "created_at": "2026-11-05T08:30:00+00:00",
                    "source": "cintamani-android",
                    "input_mode": "text",
                    "typing_wpm": 68.5,
                },
                {
                    "id": "note-duckdb-local",
                    "device_id": "web-dashboard",
                    "content": "DuckDB terbukti sangat efisien untuk OLAP analitik lokal dan komputasi kemiripan vektor. 1 file database tunggal tanpa konfigurasi server yang rumit.",
                    "created_at": "2026-11-06T14:15:00+00:00",
                    "source": "cintamani-web",
                    "input_mode": "text",
                    "typing_wpm": 72.0,
                },
                {
                    "id": "note-epistemology",
                    "device_id": "cintamani-phone-01",
                    "content": "Bagaimana mencegah 'Context Window Trap' pada LLM saat ribuan catatan menumpuk? Solusinya adalah ringkasan berjenjang (hierarchical summarization) dan time-decay retrieval.",
                    "created_at": "2026-11-07T21:40:00+00:00",
                    "source": "cintamani-android",
                    "input_mode": "text",
                    "typing_wpm": 65.0,
                },
                {
                    "id": "note-solar-power",
                    "device_id": "cintamani-phone-01",
                    "content": "Desain catu daya mandiri untuk node pemantauan di kebun: panel surya 10W, modul TP4056 dengan proteksi overdischarge, dan baterai LiFePO4 3.2V 6000mAh.",
                    "created_at": "2026-11-08T10:00:00+00:00",
                    "source": "cintamani-android",
                    "input_mode": "text",
                    "typing_wpm": 70.0,
                },
                {
                    "id": "note-action-motor",
                    "device_id": "cintamani-phone-01",
                    "content": "Action item: periksa sistem rem belakang motor dan ganti oli gardan akhir pekan ini sebelum perjalanan touring ke dataran tinggi.",
                    "created_at": "2026-11-09T09:20:00+00:00",
                    "source": "cintamani-android",
                    "input_mode": "text",
                    "typing_wpm": 55.0,
                },
                {
                    "id": "note-project-seed",
                    "device_id": "web-dashboard",
                    "content": "Ide Proyek Cintamani Brain: Personal knowledge graph lokal yang mentransformasikan kumpulan pemikiran mikro mentah menjadi wawasan bermakna secara on-demand.",
                    "created_at": "2026-11-10T07:00:00+00:00",
                    "source": "cintamani-web",
                    "input_mode": "text",
                    "typing_wpm": 75.0,
                },
            ]

            for n in sample_notes:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO micro_notes (
                        id, device_id, content, created_at, source, input_mode, typing_wpm, plugin_flags_json
                    ) VALUES (?, ?, ?, ?::TIMESTAMPTZ, ?, ?, ?, '{}')
                    """,
                    [n["id"], n["device_id"], n["content"], n["created_at"], n["source"], n["input_mode"], n["typing_wpm"]],
                )

            sample_relations = [
                ("rel-01", "note-esp32-lora", "note-solar-power", "evolves_into", 0.85, "Integrasi node telemetri radio dengan sistem catu daya surya mandiri", "seed"),
                ("rel-02", "note-duckdb-local", "note-epistemology", "serendipitous_link", 0.90, "Pemanfaatan database lokal untuk mengatasi batas konteks LLM", "seed"),
                ("rel-03", "note-esp32-lora", "note-duckdb-local", "idea_collision", 0.75, "Penerapan analitik data tepi pada jaringan sensor", "seed"),
                ("rel-04", "note-epistemology", "note-project-seed", "evolves_into", 0.95, "Konseptualisasi arsitektur sistem memori Cintamani", "seed"),
            ]
            for r in sample_relations:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO thought_relations (
                        id, source_id, target_id, relationship_type, weight, reason, generated_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    list(r),
                )

            sample_insight_md = """# Rajutan Sinergi: Perangkat Keras Tepi & Pengetahuan Lokal

Ditemukan benang merah kuat antara eksperimen radio LoRa dan arsitektur database lokal DuckDB. Keduanya mencerminkan filosofi desentralisasi dan kedaulatan data penuh tanpa ketergantungan pada cloud publik.

### Temuan Analisis:
- **Kemandirian Sistem:** Node sensor berdaya rendah dan sistem pencatatan satu-folder saling melengkapi konsep infrastruktur tangguh (*resilient local ecosystem*).
- **Wawasan Kunci:** Data dari lapangan dapat langsung diproses dan dihubungkan dengan memori pemikiran sebelumnya tanpa latency transmisi eksternal.
- **Rekomendasi:** Lakukan pengujian transmisi LoRa bersamaan dengan pencatatan status telemetri langsung ke tabel DuckDB."""

            self._conn.execute(
                """
                INSERT OR IGNORE INTO insights (
                    id, plugin_name, title, summary_markdown, payload_json,
                    source_note_ids_json, time_filter_json, ai_metadata_json,
                    feedback_status, is_pinned, created_at
                ) VALUES (
                    'ins-seed-001', 'serendipity_engine', 'Serendipitas: Sinergi Sistem Terdistribusi & Memori Lokal',
                    ?, '{"synthesis_summary": "Sinergi antara node LoRa mandiri dan arsitektur DuckDB lokal"}',
                    '["note-esp32-lora", "note-duckdb-local", "note-solar-power"]',
                    '{"mode": "all_time"}',
                    '{"model_name": "qwen2.5:7b", "prompt_version": "v1.0", "confidence": 0.92}',
                    'accepted', TRUE, CURRENT_TIMESTAMP
                )
                """,
                [sample_insight_md],
            )


    # -------------------------------------------------------------
    # Time Filter Resolver
    # -------------------------------------------------------------
    @staticmethod
    def resolve_time_filter(
        mode: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Converts time filter specifications into concrete start and end datetime bounds.
        """
        now = datetime.now(timezone.utc)
        if mode == "last_7_days":
            return now - timedelta(days=7), now
        elif mode == "last_30_days":
            return now - timedelta(days=30), now
        elif mode == "this_year":
            start_year = datetime(now.year, 1, 1, tzinfo=timezone.utc)
            return start_year, now
        elif mode == "custom_range":
            s_dt = None
            e_dt = None
            if start_date:
                try:
                    s_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                except Exception:
                    pass
            if end_date:
                try:
                    e_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    # A date-only upper bound means the whole day, not 00:00.
                    if len(end_date.strip()) == 10:
                        e_dt = e_dt.replace(
                            hour=23, minute=59, second=59, microsecond=999999
                        )
                except Exception:
                    pass
            return s_dt, e_dt
        return None, None  # all_time

    # -------------------------------------------------------------
    # Note Ingestion & Queries
    # -------------------------------------------------------------
    def insert_notes_batch(
        self, device_id: str, notes: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Idempotent append-only ingestion of notes from mobile or web.
        Uses INSERT OR IGNORE by note id. Returns list of synced IDs.
        """
        synced_ids: List[str] = []
        with self._lock:
            for n in notes:
                n_id = n.get("id")
                content = n.get("content", "")
                created_at = n.get("created_at")
                source = n.get("source", "cintamani-android")
                input_mode = n.get("input_mode", "text")

                meta = n.get("metadata", {}) or {}
                typing_wpm = meta.get("typing_wpm")
                backspace_count = meta.get("backspace_count")
                compose_duration_ms = meta.get("compose_duration_ms")
                vocal_wpm = meta.get("vocal_wpm")
                rms_db_avg = meta.get("rms_db_avg")
                rms_db_peak = meta.get("rms_db_peak")
                coarse_lat = meta.get("coarse_lat")
                coarse_lon = meta.get("coarse_lon")
                plugin_flags_json = json.dumps(meta.get("plugin_flags", {}))

                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO micro_notes (
                        id, device_id, content, created_at, source, input_mode,
                        typing_wpm, backspace_count, compose_duration_ms,
                        vocal_wpm, rms_db_avg, rms_db_peak,
                        coarse_lat, coarse_lon, plugin_flags_json
                    ) VALUES (?, ?, ?, ?::TIMESTAMPTZ, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        n_id,
                        device_id,
                        content,
                        created_at,
                        source,
                        input_mode,
                        typing_wpm,
                        backspace_count,
                        compose_duration_ms,
                        vocal_wpm,
                        rms_db_avg,
                        rms_db_peak,
                        coarse_lat,
                        coarse_lon,
                        plugin_flags_json,
                    ],
                )
                synced_ids.append(n_id)

        return synced_ids

    def create_web_note(
        self, note_id: str, content: str, plugin_flags: Dict[str, str]
    ) -> Dict[str, Any]:
        """Creates a note directly from the web dashboard."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO micro_notes (
                    id, device_id, content, created_at, source, input_mode, plugin_flags_json
                ) VALUES (?, 'web-dashboard', ?, ?::TIMESTAMPTZ, 'cintamani-web', 'text', ?)
                """,
                [note_id, content, now_iso, json.dumps(plugin_flags)],
            )
        return {
            "id": note_id,
            "device_id": "web-dashboard",
            "content": content,
            "created_at": now_iso,
            "source": "cintamani-web",
            "input_mode": "text",
            "metadata": {"plugin_flags": plugin_flags},
        }

    def get_notes(
        self,
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieves micro_notes with optional time window pre-filtering."""
        s_dt, e_dt = self.resolve_time_filter(mode, start_date, end_date)
        where_clauses = []
        params = []

        if s_dt:
            where_clauses.append("created_at >= ?::TIMESTAMPTZ")
            params.append(s_dt.isoformat())
        if e_dt:
            where_clauses.append("created_at <= ?::TIMESTAMPTZ")
            params.append(e_dt.isoformat())

        where_sql = (
            "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        )

        with self._lock:
            # Count total
            count_res = self._conn.execute(
                f"SELECT COUNT(*) FROM micro_notes {where_sql}", params
            ).fetchone()
            total_count = count_res[0] if count_res else 0

            # Fetch rows
            query = f"""
                SELECT id, device_id, content, created_at, source, input_mode,
                       typing_wpm, backspace_count, compose_duration_ms,
                       vocal_wpm, rms_db_avg, rms_db_peak, coarse_lat, coarse_lon,
                       plugin_flags_json, ingested_at
                FROM micro_notes
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            rows = self._conn.execute(query, params + [limit, offset]).fetchall()

        notes = []
        for r in rows:
            flags = {}
            if r[14]:
                try:
                    flags = json.loads(r[14])
                except Exception:
                    flags = {}

            notes.append(
                {
                    "id": r[0],
                    "device_id": r[1],
                    "content": r[2],
                    "created_at": str(r[3]),
                    "source": r[4],
                    "input_mode": r[5],
                    "metadata": {
                        "typing_wpm": r[6],
                        "backspace_count": r[7],
                        "compose_duration_ms": r[8],
                        "vocal_wpm": r[9],
                        "rms_db_avg": r[10],
                        "rms_db_peak": r[11],
                        "coarse_lat": r[12],
                        "coarse_lon": r[13],
                        "plugin_flags": flags,
                    },
                    "ingested_at": str(r[15]),
                }
            )

        return notes, total_count

    def get_notes_by_ids(self, note_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetches a specific list of notes by ID for Provenance Jejak Audit."""
        if not note_ids:
            return []

        placeholders = ", ".join(["?"] * len(note_ids))
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT id, device_id, content, created_at, source, input_mode,
                       typing_wpm, vocal_wpm, coarse_lat, coarse_lon
                FROM micro_notes
                WHERE id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                note_ids,
            ).fetchall()

        results = []
        for r in rows:
            results.append(
                {
                    "id": r[0],
                    "device_id": r[1],
                    "content": r[2],
                    "created_at": str(r[3]),
                    "source": r[4],
                    "input_mode": r[5],
                    "typing_wpm": r[6],
                    "vocal_wpm": r[7],
                    "coarse_lat": r[8],
                    "coarse_lon": r[9],
                }
            )
        return results

    def count_notes_in_period(
        self,
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> int:
        """Returns the number of notes recorded in the given time frame."""
        s_dt, e_dt = self.resolve_time_filter(mode, start_date, end_date)
        where_clauses = []
        params = []
        if s_dt:
            where_clauses.append("created_at >= ?::TIMESTAMPTZ")
            params.append(s_dt.isoformat())
        if e_dt:
            where_clauses.append("created_at <= ?::TIMESTAMPTZ")
            params.append(e_dt.isoformat())

        where_sql = (
            "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        )
        with self._lock:
            res = self._conn.execute(
                f"SELECT COUNT(*) FROM micro_notes {where_sql}", params
            ).fetchone()
            return res[0] if res else 0

    # -------------------------------------------------------------
    # Vector Indexing & Embeddings
    # -------------------------------------------------------------
    def get_unembedded_notes(
        self,
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Finds notes that do not yet have an embedding in vector_index."""
        s_dt, e_dt = self.resolve_time_filter(mode, start_date, end_date)
        where_clauses = ["v.note_id IS NULL"]
        params = []

        if s_dt:
            where_clauses.append("n.created_at >= ?::TIMESTAMPTZ")
            params.append(s_dt.isoformat())
        if e_dt:
            where_clauses.append("n.created_at <= ?::TIMESTAMPTZ")
            params.append(e_dt.isoformat())

        where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT n.id, n.content, n.created_at
                FROM micro_notes n
                LEFT JOIN vector_index v ON n.id = v.note_id
                {where_sql}
                ORDER BY n.created_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()

        return [{"id": r[0], "content": r[1], "created_at": str(r[2])} for r in rows]

    def save_embedding(
        self, note_id: str, embedding: List[float], model_name: str
    ) -> None:
        """Stores or replaces a note's semantic embedding vector."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO vector_index (
                    note_id, embedding, embedding_dim, model_name, created_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [note_id, embedding, len(embedding), model_name],
            )

    # -------------------------------------------------------------
    # Search Engine: Keyword, Semantic & Hybrid
    # -------------------------------------------------------------
    def search_keyword(
        self,
        query_text: str,
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Exact case-insensitive keyword search with SQL time pre-filtering."""
        s_dt, e_dt = self.resolve_time_filter(mode, start_date, end_date)
        where_clauses = ["content ILIKE ?"]
        params = [f"%{query_text}%"]

        if s_dt:
            where_clauses.append("created_at >= ?::TIMESTAMPTZ")
            params.append(s_dt.isoformat())
        if e_dt:
            where_clauses.append("created_at <= ?::TIMESTAMPTZ")
            params.append(e_dt.isoformat())

        where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT id, content, created_at, source, input_mode
                FROM micro_notes
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()

        return [
            {
                "id": r[0],
                "content": r[1],
                "created_at": str(r[2]),
                "source": r[3],
                "input_mode": r[4],
                "score": 1.0,
                "match_type": "keyword",
            }
            for r in rows
        ]

    def search_semantic(
        self,
        query_vector: List[float],
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Cosine similarity search against vector_index with SQL time pre-filtering on micro_notes.
        """
        s_dt, e_dt = self.resolve_time_filter(mode, start_date, end_date)
        where_clauses = []
        params = []

        if s_dt:
            where_clauses.append("n.created_at >= ?::TIMESTAMPTZ")
            params.append(s_dt.isoformat())
        if e_dt:
            where_clauses.append("n.created_at <= ?::TIMESTAMPTZ")
            params.append(e_dt.isoformat())

        where_sql = (
            "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        )

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT n.id, n.content, n.created_at, n.source, n.input_mode, v.embedding
                FROM micro_notes n
                JOIN vector_index v ON n.id = v.note_id
                {where_sql}
                """,
                params,
            ).fetchall()

        if not rows:
            return []

        # Calculate cosine similarity in python
        def cosine_sim(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for r in rows:
            emb = r[5]
            sim = cosine_sim(query_vector, emb)
            scored.append(
                {
                    "id": r[0],
                    "content": r[1],
                    "created_at": str(r[2]),
                    "source": r[3],
                    "input_mode": r[4],
                    "score": round(sim, 4),
                    "match_type": "semantic",
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def search_hybrid(
        self,
        query_text: str,
        query_vector: Optional[List[float]],
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Combines keyword and semantic search results using Reciprocal Rank Fusion / scoring.
        """
        kw_results = self.search_keyword(query_text, mode, start_date, end_date, limit=limit)
        sem_results = []
        if query_vector:
            sem_results = self.search_semantic(
                query_vector, mode, start_date, end_date, limit=limit
            )

        combined_scores: Dict[str, Dict[str, Any]] = {}

        for item in kw_results:
            n_id = item["id"]
            combined_scores[n_id] = {
                "id": item["id"],
                "content": item["content"],
                "created_at": item["created_at"],
                "source": item["source"],
                "input_mode": item["input_mode"],
                "score": 0.5,
                "match_type": "hybrid (keyword)",
            }

        for item in sem_results:
            n_id = item["id"]
            if n_id in combined_scores:
                combined_scores[n_id]["score"] += item["score"] * 0.5
                combined_scores[n_id]["match_type"] = "hybrid (both)"
            else:
                combined_scores[n_id] = {
                    "id": item["id"],
                    "content": item["content"],
                    "created_at": item["created_at"],
                    "source": item["source"],
                    "input_mode": item["input_mode"],
                    "score": item["score"] * 0.5,
                    "match_type": "hybrid (semantic)",
                }

        results = list(combined_scores.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    # -------------------------------------------------------------
    # Insights Management (The Blackboard)
    # -------------------------------------------------------------
    def save_insight(
        self,
        insight_id: str,
        plugin_name: str,
        title: str,
        summary_markdown: str,
        payload: Dict[str, Any],
        source_note_ids: List[str],
        time_filter: Dict[str, Any],
        ai_metadata: Dict[str, Any],
    ) -> None:
        """Stores a new insight into the universal Blackboard table."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO insights (
                    id, plugin_name, title, summary_markdown,
                    payload_json, source_note_ids_json, time_filter_json,
                    ai_metadata_json, feedback_status, is_pinned, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unreviewed', FALSE, CURRENT_TIMESTAMP)
                """,
                [
                    insight_id,
                    plugin_name,
                    title,
                    summary_markdown,
                    json.dumps(payload),
                    json.dumps(source_note_ids),
                    json.dumps(time_filter),
                    json.dumps(ai_metadata),
                ],
            )

    def list_insights(
        self,
        plugin_name: Optional[str] = None,
        feedback_status: Optional[str] = None,
        pinned_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Lists insights with optional filtering.
        Enriches each insight with the full original notes from source_note_ids.
        """
        where_clauses = []
        params = []
        if plugin_name:
            where_clauses.append("plugin_name = ?")
            params.append(plugin_name)
        if feedback_status:
            where_clauses.append("feedback_status = ?")
            params.append(feedback_status)
        if pinned_only:
            where_clauses.append("is_pinned = TRUE")

        where_sql = (
            "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        )

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT id, plugin_name, title, summary_markdown, payload_json,
                       source_note_ids_json, time_filter_json, ai_metadata_json,
                       feedback_status, is_pinned, created_at
                FROM insights
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()

        insights = []
        for r in rows:
            payload = json.loads(r[4]) if r[4] else {}
            source_ids = json.loads(r[5]) if r[5] else []
            time_filter = json.loads(r[6]) if r[6] else {}
            ai_metadata = json.loads(r[7]) if r[7] else {}

            # Fetch source notes text for Provenance Jejak Audit
            source_notes = self.get_notes_by_ids(source_ids)

            insights.append(
                {
                    "id": r[0],
                    "plugin_name": r[1],
                    "title": r[2],
                    "summary_markdown": r[3],
                    "payload": payload,
                    "source_note_ids": source_ids,
                    "source_notes": source_notes,
                    "time_filter": time_filter,
                    "ai_metadata": ai_metadata,
                    "feedback_status": r[8],
                    "is_pinned": bool(r[9]),
                    "created_at": str(r[10]),
                }
            )

        return insights

    def get_insight_by_id(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single insight by its unique ID."""
        with self._lock:
            r = self._conn.execute(
                """
                SELECT id, plugin_name, title, summary_markdown, payload_json,
                       source_note_ids_json, time_filter_json, ai_metadata_json,
                       feedback_status, is_pinned, created_at
                FROM insights
                WHERE id = ?
                """,
                [insight_id],
            ).fetchone()

        if not r:
            return None

        source_ids = json.loads(r[5]) if r[5] else []
        return {
            "id": r[0],
            "plugin_name": r[1],
            "title": r[2],
            "summary_markdown": r[3],
            "payload": json.loads(r[4]) if r[4] else {},
            "source_note_ids": source_ids,
            "source_notes": self.get_notes_by_ids(source_ids),
            "time_filter": json.loads(r[6]) if r[6] else {},
            "ai_metadata": json.loads(r[7]) if r[7] else {},
            "feedback_status": r[8],
            "is_pinned": bool(r[9]),
            "created_at": str(r[10]),
        }

    def update_insight_feedback(
        self,
        insight_id: str,
        feedback_status: Optional[str] = None,
        is_pinned: Optional[bool] = None,
    ) -> bool:
        """Updates feedback_status ('accepted'/'rejected'/'unreviewed') or is_pinned."""
        updates = []
        params = []
        if feedback_status is not None:
            updates.append("feedback_status = ?")
            params.append(feedback_status)
        if is_pinned is not None:
            updates.append("is_pinned = ?")
            params.append(is_pinned)

        if not updates:
            return False

        params.append(insight_id)
        sql = f"UPDATE insights SET {', '.join(updates)} WHERE id = ?"
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM insights WHERE id = ?", [insight_id]
            ).fetchone()
            if not exists:
                return False
            self._conn.execute(sql, params)
        return True

    # -------------------------------------------------------------
    # Knowledge Graph: thought_relations
    # -------------------------------------------------------------
    def save_thought_relations(self, relations: List[Dict[str, Any]]) -> None:
        """Stores relations generated by plugins into thought_relations."""
        if not relations:
            return
        with self._lock:
            for rel in relations:
                rel_id = rel.get("id")
                source_id = rel.get("source_id")
                target_id = rel.get("target_id")
                rel_type = rel.get("relationship_type", "related")
                weight = rel.get("weight", 0.5)
                reason = rel.get("reason", "")
                gen_by = rel.get("generated_by", "plugin")

                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO thought_relations (
                        id, source_id, target_id, relationship_type, weight, reason, generated_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    [rel_id, source_id, target_id, rel_type, weight, reason, gen_by],
                )

    def get_graph_data(
        self,
        mode: str = "all_time",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns nodes (micro_notes in range) and edges (thought_relations)
        formatted for Vis-Network rendering in the web dashboard.
        """
        notes, _ = self.get_notes(mode, start_date, end_date, limit=300)
        note_id_set = {n["id"] for n in notes}

        nodes = []
        for n in notes:
            # Preview label (first 25 chars)
            label = n["content"][:28] + "..." if len(n["content"]) > 28 else n["content"]
            nodes.append(
                {
                    "id": n["id"],
                    "label": label,
                    "title": n["content"],  # full text tooltip
                    "created_at": n["created_at"],
                    "source": n["source"],
                    "input_mode": n["input_mode"],
                }
            )

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, source_id, target_id, relationship_type, weight, reason, generated_by
                FROM thought_relations
                """
            ).fetchall()

        edges = []
        for r in rows:
            # Only include edges where at least one node is in current view or both
            s_id, t_id = r[1], r[2]
            if s_id in note_id_set or t_id in note_id_set:
                edges.append(
                    {
                        "id": r[0],
                        "from": s_id,
                        "to": t_id,
                        "label": r[3],
                        "relationship_type": r[3],
                        "weight": r[4],
                        "title": r[5],  # reason tooltip
                        "generated_by": r[6],
                    }
                )

        return {"nodes": nodes, "edges": edges}

    # -------------------------------------------------------------
    # Asynchronous Job Tracking: analysis_jobs
    # -------------------------------------------------------------
    def create_job(
        self, job_id: str, plugin_name: str, request_data: Dict[str, Any]
    ) -> None:
        """Records a new analysis job with queued status."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO analysis_jobs (
                    job_id, plugin_name, status, request_json, created_at
                ) VALUES (?, ?, 'queued', ?, CURRENT_TIMESTAMP)
                """,
                [job_id, plugin_name, json.dumps(request_data)],
            )

    def update_job_status(
        self,
        job_id: str,
        status: str,
        result_insight_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Updates the status and optional results/error of an analysis job."""
        now_sql = "CURRENT_TIMESTAMP" if status in ["completed", "failed"] else "NULL"
        with self._lock:
            self._conn.execute(
                f"""
                UPDATE analysis_jobs
                SET status = ?,
                    result_insight_id = COALESCE(?, result_insight_id),
                    error_message = COALESCE(?, error_message),
                    completed_at = {now_sql}
                WHERE job_id = ?
                """,
                [status, result_insight_id, error_message, job_id],
            )

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves current execution status of a job."""
        with self._lock:
            r = self._conn.execute(
                """
                SELECT job_id, plugin_name, status, result_insight_id, error_message, created_at, completed_at
                FROM analysis_jobs
                WHERE job_id = ?
                """,
                [job_id],
            ).fetchone()

        if not r:
            return None

        return {
            "job_id": r[0],
            "plugin_name": r[1],
            "status": r[2],
            "result_insight_id": r[3],
            "error_message": r[4],
            "created_at": str(r[5]),
            "completed_at": str(r[6]) if r[6] else None,
        }

    # -------------------------------------------------------------
    # Complete JSON Export (Export My Brain)
    # -------------------------------------------------------------
    def export_all_data(self) -> Dict[str, Any]:
        """
        Exports all records from micro_notes, insights, and thought_relations
        into a single structured JSON document for 1-Click Backup.
        """
        with self._lock:
            notes_rows = self._conn.execute(
                "SELECT * FROM micro_notes ORDER BY created_at ASC"
            ).fetchall()
            notes_cols = [c[0] for c in self._conn.description]

            insights_rows = self._conn.execute(
                "SELECT * FROM insights ORDER BY created_at ASC"
            ).fetchall()
            insights_cols = [c[0] for c in self._conn.description]

            rel_rows = self._conn.execute(
                "SELECT * FROM thought_relations ORDER BY created_at ASC"
            ).fetchall()
            rel_cols = [c[0] for c in self._conn.description]

        export_notes = [dict(zip(notes_cols, [str(v) if isinstance(v, (datetime,)) else v for v in row])) for row in notes_rows]
        export_insights = [dict(zip(insights_cols, [str(v) if isinstance(v, (datetime,)) else v for v in row])) for row in insights_rows]
        export_relations = [dict(zip(rel_cols, [str(v) if isinstance(v, (datetime,)) else v for v in row])) for row in rel_rows]

        return {
            "cintamani_version": "1.0.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "server_name": get_config().get("server_name"),
            "data": {
                "micro_notes": export_notes,
                "insights": export_insights,
                "thought_relations": export_relations,
            },
        }


def get_db() -> DuckDBManager:
    """Helper to access singleton DuckDBManager."""
    return DuckDBManager()
