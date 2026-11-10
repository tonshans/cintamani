"""
Cintamani FastAPI Server Entrypoint.
Initializes DuckDB, discovers plugins on startup, mounts /api/v1 routes,
and serves the Web Dashboard (web_ui/) with zero build step.
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import get_config
from app.core.database import get_db
from app.core.ollama_client import get_ollama_client
from app.core.plugin_registry import get_plugin_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cintamani.server")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_UI_DIR = BASE_DIR / "web_ui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("Initializing Cintamani Home Server & Brain Engine...")

    # 1. Initialize DuckDB Tables
    db = get_db()
    logger.info("DuckDB Manager initialized successfully.")

    # 2. Discover Plugins
    registry = get_plugin_registry()
    plugins = registry.discover_plugins()
    logger.info(f"Discovered {len(plugins)} cognitive plugins: {list(plugins.keys())}")

    # 3. Check LLM Connectivity
    ollama = get_ollama_client()
    reachable, msg = await ollama.check_health()
    logger.info(f"LLM Provider status: {msg}")

    yield

    logger.info("Shutting down Cintamani Home Server.")


app = FastAPI(
    title="Cintamani Home Brain Engine",
    description="The Personal AI Knowledge Graph & Cognitive Neo-Brutalism Exploration Dashboard.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount REST API Router
app.include_router(api_router)

# Mount Static Assets
css_dir = WEB_UI_DIR / "css"
js_dir = WEB_UI_DIR / "js"
if css_dir.exists():
    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
if js_dir.exists():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")


# Serve Web Dashboard Index at root
@app.get("/")
async def serve_index():
    index_file = WEB_UI_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Cintamani API Server Active. Web UI files are in preparation."}
