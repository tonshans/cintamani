"""
Cintamani Plugin Registry & Execution Context.
Enforces the 5 Laws of The Plugin Contract:
1. The Read-Only Rule on micro_notes
2. The Blackboard Rule on insights table
3. The Provenance Rule with source_note_ids and ai_metadata
4. The Registry Rule (Service Locator call_plugin)
5. Time-Aware Prompting and SQL Pre-Filtering
"""

from __future__ import annotations
import asyncio
import importlib.util
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.database import DuckDBManager, get_db
from app.core.ollama_client import (
    OllamaClient,
    build_time_aware_system_prompt,
    get_ollama_client,
)

logger = logging.getLogger("cintamani.plugins")


class PluginExecutionContext:
    """
    Context provided to every plugin during execution.
    Provides read-only access to DuckDB, LLM client, and the Service Locator.
    """

    def __init__(
        self,
        registry: PluginRegistry,
        db: DuckDBManager,
        ollama: OllamaClient,
        time_filter: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> None:
        self._registry = registry
        self.db = db
        self.ollama = ollama
        self.time_filter = time_filter
        self.parameters = parameters

    def build_time_aware_system_prompt(self, base_prompt: str) -> str:
        """Helper to inject current time frame into the system prompt."""
        return build_time_aware_system_prompt(base_prompt, self.time_filter)

    def get_notes(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Read-Only query returning notes strictly filtered by the current time window.
        """
        mode = self.time_filter.get("mode", "all_time")
        start_date = self.time_filter.get("start_date")
        end_date = self.time_filter.get("end_date")
        notes, _ = self.db.get_notes(
            mode=mode, start_date=start_date, end_date=end_date, limit=limit
        )
        return notes

    def count_notes(self) -> int:
        """Returns the number of notes in the current time window."""
        mode = self.time_filter.get("mode", "all_time")
        start_date = self.time_filter.get("start_date")
        end_date = self.time_filter.get("end_date")
        return self.db.count_notes_in_period(
            mode=mode, start_date=start_date, end_date=end_date
        )

    def call_plugin(self, plugin_name: str, **kwargs) -> Any:
        """
        Service Locator: Enables plugins to invoke other plugins
        (e.g. vector_embedder) without hardcoded imports.
        """
        return self._registry.call_plugin_from_context(
            plugin_name, self.time_filter, kwargs
        )


class PluginRegistry:
    """
    Dynamic scanner, dependency checker, and execution supervisor for Cintamani plugins.
    """

    _instance: Optional[PluginRegistry] = None

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: Dict[str, Dict[str, Any]] = {}
            cls._plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
        return cls._instance

    def discover_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        Scans app/plugins/ directory for Python plugin modules.
        Ignores __init__.py and files ending with .disabled.
        """
        self._plugins.clear()
        if not self._plugins_dir.exists():
            return self._plugins

        for filepath in self._plugins_dir.glob("*.py"):
            filename = filepath.name
            if filename == "__init__.py" or filename.endswith(".disabled.py"):
                continue

            module_name = filepath.stem
            try:
                spec = importlib.util.spec_from_file_location(
                    f"app.plugins.{module_name}", filepath
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    manifest = getattr(mod, "__manifest__", None)
                    execute_fn = getattr(mod, "execute", None)

                    if manifest and execute_fn and callable(execute_fn):
                        p_name = manifest.get("plugin_name", module_name)
                        self._plugins[p_name] = {
                            "manifest": manifest,
                            "execute": execute_fn,
                            "module": mod,
                            "filepath": filepath,
                            "dependencies_met": True,
                        }
                    else:
                        logger.warning(
                            f"Plugin {filename} is missing __manifest__ or execute() function."
                        )
            except Exception as e:
                logger.error(f"Failed to load plugin {filename}: {str(e)}")

        # Check dependency graph
        self._verify_dependencies()
        return self._plugins

    def _verify_dependencies(self) -> None:
        """Validates that all required plugins in 'requires' are registered."""
        for p_name, data in self._plugins.items():
            reqs = data["manifest"].get("requires", [])
            for req in reqs:
                if req not in self._plugins:
                    data["dependencies_met"] = False
                    logger.warning(
                        f"Plugin '{p_name}' dependency not met: missing '{req}'"
                    )

    def get_plugin(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Returns plugin registration data by name."""
        return self._plugins.get(plugin_name)

    def list_plugins_info(self, time_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Returns dynamic plugin list with threshold evaluation for Web UI sidebar.
        """
        db = get_db()
        mode = time_filter.get("mode", "all_time")
        start_date = time_filter.get("start_date")
        end_date = time_filter.get("end_date")
        total_notes = db.count_notes_in_period(mode, start_date, end_date)

        results = []
        for p_name, data in self._plugins.items():
            manifest = data["manifest"]
            threshold = manifest.get("min_notes_threshold", 0)
            missing = max(0, threshold - total_notes)
            is_ready = (missing == 0) and data.get("dependencies_met", True)

            results.append(
                {
                    "plugin_name": manifest.get("plugin_name", p_name),
                    "display_name": manifest.get("display_name", p_name),
                    "category": manifest.get("category", "understand"),
                    "description": manifest.get("description", ""),
                    "render_view_type": manifest.get("render_view_type", "document"),
                    "min_notes_threshold": threshold,
                    "is_ready": is_ready,
                    "missing_notes_count": missing,
                    "requires": manifest.get("requires", []),
                    "dependencies_met": data.get("dependencies_met", True),
                    "default_timeframe": manifest.get("default_timeframe", "all_time"),
                    "prompt_version": manifest.get("prompt_version", "v1.0"),
                }
            )

        # Sort: utility first, then understand, connect, challenge, create
        order = {"utility": 0, "understand": 1, "connect": 2, "challenge": 3, "create": 4}
        results.sort(key=lambda x: order.get(x["category"], 99))
        return results

    def call_plugin_from_context(
        self,
        plugin_name: str,
        time_filter: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Any:
        """Internal synchronous/async invocation for Service Locator."""
        if plugin_name not in self._plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not registered.")

        plugin_data = self._plugins[plugin_name]
        ctx = PluginExecutionContext(
            registry=self,
            db=get_db(),
            ollama=get_ollama_client(),
            time_filter=time_filter,
            parameters=parameters,
        )

        fn = plugin_data["execute"]
        if asyncio.iscoroutinefunction(fn):
            try:
                asyncio.get_running_loop()
                # Caller (an async plugin) awaits this coroutine; never schedule a copy.
                return fn(ctx)
            except RuntimeError:
                return asyncio.run(fn(ctx))
        return fn(ctx)

    async def execute_plugin(
        self,
        plugin_name: str,
        time_filter: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes a plugin, enforces Blackboard and Provenance rules,
        and saves output to insights and thought_relations.
        """
        if plugin_name not in self._plugins:
            raise ValueError(f"Plugin '{plugin_name}' tidak ditemukan.")

        plugin_data = self._plugins[plugin_name]
        if not plugin_data.get("dependencies_met", True):
            raise ValueError(
                f"Plugin '{plugin_name}' tidak dapat dijalankan karena dependensi belum terpenuhi."
            )

        manifest = plugin_data["manifest"]
        db = get_db()
        ollama = get_ollama_client()

        # Check threshold
        mode = time_filter.get("mode", "all_time")
        start_date = time_filter.get("start_date")
        end_date = time_filter.get("end_date")
        total_notes = db.count_notes_in_period(mode, start_date, end_date)
        threshold = manifest.get("min_notes_threshold", 0)

        if total_notes < threshold:
            missing = threshold - total_notes
            raise ValueError(
                f"Catatan belum mencukupi untuk menjalankan {manifest.get('display_name')}. "
                f"Dibutuhkan minimal {threshold} catatan (kurang {missing} catatan)."
            )

        ctx = PluginExecutionContext(
            registry=self,
            db=db,
            ollama=ollama,
            time_filter=time_filter,
            parameters=parameters,
        )

        t_start = time.time()
        fn = plugin_data["execute"]

        if asyncio.iscoroutinefunction(fn):
            result = await fn(ctx)
        else:
            result = fn(ctx)

        execution_ms = int((time.time() - t_start) * 1000)

        # ---------------------------------------------------------
        # The Blackboard Rule & Provenance Rule Enforcement
        # ---------------------------------------------------------
        # Special utility plugins (like vector_embedder) might not create an insight card
        if manifest.get("category") == "utility":
            return result

        insight_id = f"ins-{uuid.uuid4().hex[:12]}"
        title = result.get("title", f"Wawasan {manifest.get('display_name')}")
        summary_markdown = result.get("summary_markdown", "")
        payload = result.get("payload", {})
        source_note_ids = result.get("source_note_ids", [])

        ai_metadata = {
            "model_name": ollama.model_name,
            "llm_provider": ollama.provider,
            "prompt_version": manifest.get("prompt_version", "v1.0"),
            "execution_ms": execution_ms,
            "confidence": result.get("confidence", 0.85),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Auto-save to universal insights table
        db.save_insight(
            insight_id=insight_id,
            plugin_name=plugin_name,
            title=title,
            summary_markdown=summary_markdown,
            payload=payload,
            source_note_ids=source_note_ids,
            time_filter=time_filter,
            ai_metadata=ai_metadata,
        )

        # Save thought relations if produced
        relations = result.get("relations", [])
        if relations:
            db.save_thought_relations(relations)

        return {
            "insight_id": insight_id,
            "plugin_name": plugin_name,
            "title": title,
            "summary_markdown": summary_markdown,
            "payload": payload,
            "source_note_ids": source_note_ids,
            "ai_metadata": ai_metadata,
            "relations_count": len(relations),
        }


def get_plugin_registry() -> PluginRegistry:
    """Helper to access singleton PluginRegistry."""
    return PluginRegistry()
