"""
Cintamani Asynchronous Job Runner.
Dispatches background AI analysis tasks using ThreadPoolExecutor.
Updates analysis_jobs table in DuckDB to enable UI polling.
"""

from __future__ import annotations
import asyncio
import logging
import secrets
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from app.core.database import get_db
from app.core.plugin_registry import get_plugin_registry

logger = logging.getLogger("cintamani.jobs")


class JobRunner:
    """Manages asynchronous background jobs for AI explorations."""

    _instance: Optional[JobRunner] = None

    def __new__(cls) -> JobRunner:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._executor = ThreadPoolExecutor(
                max_workers=3, thread_name_prefix="cintamani-worker"
            )
        return cls._instance

    def submit_job(
        self,
        plugin_name: str,
        time_filter: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> str:
        """
        Creates and queues a job immediately, returning job_id in < 50ms.
        """
        job_id = f"job-{secrets.token_hex(4)}"
        db = get_db()

        request_data = {
            "plugin_name": plugin_name,
            "time_filter": time_filter,
            "parameters": parameters,
        }

        # Record queued job
        db.create_job(job_id, plugin_name, request_data)

        # Dispatch to thread worker
        self._executor.submit(
            self._worker_execute, job_id, plugin_name, time_filter, parameters
        )

        return job_id

    def _worker_execute(
        self,
        job_id: str,
        plugin_name: str,
        time_filter: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> None:
        """Worker thread function executing the plugin logic."""
        db = get_db()
        registry = get_plugin_registry()

        try:
            # Update to running
            db.update_job_status(job_id, status="running")

            # Execute plugin in event loop
            result = asyncio.run(
                registry.execute_plugin(plugin_name, time_filter, parameters)
            )

            insight_id = result.get("insight_id")
            db.update_job_status(
                job_id, status="completed", result_insight_id=insight_id
            )
            logger.info(f"Job {job_id} ({plugin_name}) completed successfully.")

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Job {job_id} ({plugin_name}) failed: {err_msg}")
            db.update_job_status(job_id, status="failed", error_message=err_msg)


def get_job_runner() -> JobRunner:
    """Helper to access singleton JobRunner."""
    return JobRunner()
