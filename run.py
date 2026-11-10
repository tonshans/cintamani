#!/usr/bin/env python3
"""
Cintamani Home Server Portable Runner.
Starts Uvicorn serving FastAPI and the Web Dashboard on the configured port.
"""

import os
import sys
import uvicorn
from app.core.config import get_config

BANNER = r"""
===================================================================
       ____ ___ _   _ _____ _    __  __    _    _   _ ___ 
      / ___|_ _| \ | |_   _/ \  |  \/  |  / \  | \ | |_ _|
     | |    | ||  \| | | |/ _ \ | |\/| | / _ \ |  \| || | 
     | |___ | || |\  | | / ___ \| |  | |/ ___ \| |\  || | 
      \____|___|_| \_| |_/_/   \_\_|  |_/_/   \_\_| \_|___|
               HOME SERVER & BRAIN ENGINE v1.0
===================================================================
"""


def main():
    cfg = get_config()
    all_cfg = cfg.get_all()

    # Port can be configured in config.json or overridden by PORT environment variable
    env_port = os.environ.get("PORT")
    try:
        port = int(env_port) if env_port else int(all_cfg.get("port", 3000))
    except ValueError:
        print(f" [!] Invalid PORT='{env_port}', falling back to config port.")
        port = int(all_cfg.get("port", 3000))
    host = all_cfg.get("host", "0.0.0.0")
    token = all_cfg.get("api_token")

    print(BANNER)
    print(f" [*] Server Name     : {all_cfg.get('server_name')}")
    print(f" [*] Web Dashboard   : http://localhost:{port}")
    print(f" [*] Network Listen  : http://{host}:{port}")
    print(f" [*] Active Bearer   : {token}")
    print(f" [*] LLM Provider    : {all_cfg.get('llm_provider')} ({all_cfg.get('llm_model')})")
    print(f" [*] DuckDB Storage  : {all_cfg.get('duckdb_path')}")
    print("===================================================================\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
