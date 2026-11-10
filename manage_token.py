#!/usr/bin/env python3
"""
CLI Utility to manage Cintamani Bearer API Token and Server Configuration.
Usage:
    python manage_token.py --show
    python manage_token.py --generate
    python manage_token.py --set-ollama-model qwen2.5:7b
    python manage_token.py --set-ollama-url http://localhost:11434
    python manage_token.py --set-provider gemini
    python manage_token.py --set-port 3000
"""

import argparse
import sys
from app.core.config import get_config


def main():
    parser = argparse.ArgumentParser(
        description="Cintamani Home Server Token & Configuration Manager"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the currently active Bearer API Token and server info",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate and rotate a new Bearer API Token",
    )
    parser.add_argument(
        "--set-ollama-model",
        type=str,
        help="Update the target Ollama LLM model name (e.g. qwen2.5:7b)",
    )
    parser.add_argument(
        "--set-ollama-url",
        type=str,
        help="Update the Ollama host URL (e.g. http://192.168.1.50:11434)",
    )
    parser.add_argument(
        "--set-provider",
        type=str,
        choices=["ollama", "gemini", "openai", "claude"],
        help="Set the primary LLM provider",
    )
    parser.add_argument(
        "--set-port",
        type=int,
        help="Set the HTTP server port (e.g. 3000)",
    )

    args = parser.parse_args()
    cfg = get_config()

    if args.generate:
        new_token = cfg.rotate_token()
        print("\n[+] Successfully generated new API Token:")
        print(f"    {new_token}")
        print("\n[*] Please update this token in your cintamani-android settings and Web UI.\n")
        return

    if args.set_ollama_model:
        cfg.set("llm_model", args.set_ollama_model)
        print(f"[+] LLM Model updated to: {args.set_ollama_model}")

    if args.set_ollama_url:
        cfg.set("ollama_base_url", args.set_ollama_url)
        print(f"[+] Ollama base URL updated to: {args.set_ollama_url}")

    if args.set_provider:
        cfg.set("llm_provider", args.set_provider)
        print(f"[+] Primary LLM provider set to: {args.set_provider}")

    if args.set_port:
        cfg.set("port", args.set_port)
        print(f"[+] Server port updated to: {args.set_port}")

    if args.show or (not any(vars(args).values())):
        all_cfg = cfg.get_all()
        print("\n=======================================================")
        print("          CINTAMANI HOME SERVER CONFIGURATION          ")
        print("=======================================================")
        print(f" Server Name     : {all_cfg.get('server_name')}")
        print(f" Host & Port     : {all_cfg.get('host')}:{all_cfg.get('port')}")
        print(f" Active Token    : {all_cfg.get('api_token')}")
        print(f" LLM Provider    : {all_cfg.get('llm_provider')}")
        print(f" LLM Model       : {all_cfg.get('llm_model')}")
        print(f" Ollama Base URL : {all_cfg.get('ollama_base_url')}")
        print(f" Embedding Model : {all_cfg.get('embedding_model')}")
        print(f" DuckDB Path     : {all_cfg.get('duckdb_path')}")
        print("=======================================================\n")


if __name__ == "__main__":
    main()
