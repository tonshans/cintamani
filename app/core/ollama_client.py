"""
Cintamani Multi-Provider LLM & Embedding Client.
Communicates with Ollama, any OpenAI-compatible API (OpenAI, DeepSeek, OpenRouter,
Groq, Together, LM Studio), Google Gemini, and Anthropic Claude using pure httpx.
Includes Time-Aware System Prompt builder and graceful offline fallback.
"""

from __future__ import annotations
import hashlib
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import get_config

logger = logging.getLogger("cintamani.llm")

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "claude": "https://api.anthropic.com/v1",
}

DEFAULT_MODELS = {
    "ollama": "qwen2.5:7b",
    "openai": "gpt-4o-mini",
    "openai_compatible": "",
    "gemini": "gemini-2.5-flash",
    "claude": "claude-sonnet-4-5",
}

DEFAULT_EMBEDDING_MODELS = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
    "openai_compatible": "text-embedding-3-small",
    "gemini": "text-embedding-004",
}

KEY_FIELDS = {
    "openai": "openai_api_key",
    "openai_compatible": "openai_api_key",
    "gemini": "gemini_api_key",
    "claude": "anthropic_api_key",
}

SUPPORTED_EMBEDDING_PROVIDERS = {"ollama", "openai", "openai_compatible", "gemini"}


def build_time_aware_system_prompt(
    base_prompt: str, time_filter_dict: Dict[str, Any]
) -> str:
    """
    Surgically injects the user-selected temporal timeframe into the System Prompt.
    Ensures LLM does not suffer from time blindness when analyzing chronological thoughts.
    """
    mode = time_filter_dict.get("mode", "all_time")
    start_date = time_filter_dict.get("start_date")
    end_date = time_filter_dict.get("end_date")

    mode_labels = {
        "all_time": "Seluruh Waktu (All Time)",
        "last_7_days": "7 Hari Terakhir (Last 7 Days)",
        "last_30_days": "30 Hari Terakhir (Last 30 Days)",
        "this_year": "Tahun Ini (This Year)",
        "custom_range": f"Rentang Kustom ({start_date} s/d {end_date})",
    }
    time_label = mode_labels.get(mode, mode)

    temporal_block = (
        "\n\n[KONTEKS TEMPORAL & WAKTU ANALISIS]\n"
        f"Periode data yang sedang dianalisis: {time_label}.\n"
        "Perhatikan kronologi 'created_at' pada setiap catatan yang diberikan. "
        "Jangan menyimpulkan urutan yang bertentangan dengan timestamp catatan asli.\n"
        "Gunakan bahasa Indonesia yang tajam, reflektif, dan objektif.\n"
    )

    return f"{base_prompt.strip()}{temporal_block}"


class OllamaClient:
    """
    Client for Ollama, OpenAI-compatible APIs, Gemini, and Claude.
    Defaults to configuration in data/config.json.
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    @property
    def provider(self) -> str:
        return self.config.get("llm_provider", "ollama").lower()

    @property
    def embedding_provider(self) -> str:
        return (self.config.get("embedding_provider") or self.provider).lower()

    @property
    def base_url(self) -> str:
        return self.config.get("ollama_base_url", "http://localhost:11434").rstrip("/")

    def _base_for(self, provider: str) -> str:
        """Base URL for a provider: explicit llm_base_url wins, else provider default."""
        configured = (self.config.get("llm_base_url") or "").strip().rstrip("/")
        return configured or DEFAULT_BASE_URLS.get(provider, "")

    def _key_for(self, provider: str) -> str:
        """API key: generic llm_api_key wins, then provider-specific field, then env."""
        generic = (self.config.get("llm_api_key") or "").strip()
        field = KEY_FIELDS.get(provider, "")
        specific = (self.config.get(field) or "").strip() if field else ""
        return generic or specific or os.environ.get("LLM_API_KEY", "").strip()

    @property
    def model_name(self) -> str:
        value = (self.config.get("llm_model") or "").strip()
        # Switching provider in the UI keeps the old model name; use the provider
        # default instead of sending e.g. qwen2.5:7b to OpenAI.
        if self.provider != "ollama" and value in ("", DEFAULT_MODELS["ollama"]):
            return DEFAULT_MODELS.get(self.provider, value)
        return value or DEFAULT_MODELS.get(self.provider, "")

    @property
    def embedding_model(self) -> str:
        value = (self.config.get("embedding_model") or "").strip()
        if self.embedding_provider != "ollama" and value in ("", DEFAULT_EMBEDDING_MODELS["ollama"]):
            return DEFAULT_EMBEDDING_MODELS.get(self.embedding_provider, value)
        return value or DEFAULT_EMBEDDING_MODELS.get(self.embedding_provider, "")

    @property
    def embedding_dim(self) -> int:
        return int(self.config.get("embedding_dim", 768))

    # -------------------------------------------------------------
    # Health & Connectivity Check
    # -------------------------------------------------------------
    async def check_health(self) -> Tuple[bool, str]:
        """
        Verifies if the configured LLM provider and service are reachable.
        Returns (is_reachable, details_message).
        """
        provider = self.provider

        if provider in ("openai", "openai_compatible"):
            if not self._key_for(provider):
                return False, "API key LLM belum dikonfigurasi (llm_api_key / OPENAI_API_KEY)."
            if not self._base_for(provider):
                return False, "llm_base_url belum dikonfigurasi untuk provider openai_compatible."
            return True, f"OpenAI-compatible {self._base_for(provider)} (Active: {self.model_name})"

        if provider == "gemini":
            if not self._key_for(provider):
                return False, "GEMINI_API_KEY belum dikonfigurasi."
            return True, f"Google Gemini (Active: {self.model_name})"

        if provider == "claude":
            if not self._key_for(provider):
                return False, "ANTHROPIC_API_KEY belum dikonfigurasi."
            return True, f"Anthropic Claude (Active: {self.model_name})"

        # Ollama default
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    has_model = any(self.model_name in m for m in models)
                    status_str = f"Ollama aktif di {self.base_url} ({len(models)} model tersedia)"
                    if not has_model and models:
                        status_str += f" - Peringatan: model '{self.model_name}' belum di-pull."
                    return True, status_str
                return False, f"Ollama merespons status code {resp.status_code}"
        except Exception as e:
            return False, f"Ollama tidak terjangkau di {self.base_url}: {str(e)}"

    # -------------------------------------------------------------
    # Embeddings Generation
    # -------------------------------------------------------------
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generates semantic embedding vector for a note text.
        Supports Ollama, OpenAI-compatible, Gemini, with deterministic fallback if offline.
        """
        provider = self.embedding_provider

        try:
            if provider == "ollama":
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.embedding_model, "prompt": text},
                    )
                    if resp.status_code == 200:
                        emb = resp.json().get("embedding")
                        if emb and isinstance(emb, list):
                            return emb
                    logger.warning("Ollama embedding gagal: HTTP %s", resp.status_code)

            elif provider == "gemini":
                api_key = self._key_for(provider)
                if api_key:
                    base = self._base_for(provider)
                    url = f"{base}/models/{self.embedding_model}:embedContent?key={api_key}"
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(
                            url,
                            json={
                                "model": f"models/{self.embedding_model}",
                                "content": {"parts": [{"text": text}]},
                            },
                        )
                        if resp.status_code == 200:
                            values = resp.json().get("embedding", {}).get("values")
                            if values and isinstance(values, list):
                                return values
                        logger.warning("Gemini embedding gagal: HTTP %s", resp.status_code)
                else:
                    logger.warning("Gemini embedding dipilih tapi GEMINI_API_KEY kosong.")

            elif provider in ("openai", "openai_compatible"):
                api_key = self._key_for(provider)
                base = self._base_for(provider)
                if not api_key or not base:
                    logger.warning(
                        "Embedding provider=%s but key/base_url missing.", provider
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(
                            f"{base}/embeddings",
                            headers={"Authorization": f"Bearer {api_key}"},
                            json={"model": self.embedding_model, "input": text},
                        )
                        if resp.status_code == 200:
                            data = resp.json().get("data") or []
                            if data and data[0].get("embedding"):
                                return data[0]["embedding"]
                        logger.warning("Embedding %s gagal: HTTP %s", provider, resp.status_code)

            else:
                logger.warning(
                    "Provider embedding '%s' tidak didukung, memakai hash fallback.", provider
                )
        except Exception as e:
            logger.warning("Embedding provider=%s gagal: %s", provider, e)

        # Deterministic Lightweight Fallback (Bag of Words / Hash Projection)
        # Guarantees that vector search and clustering work smoothly even without GPU/Ollama
        return self._generate_fallback_embedding(text, dim=self.embedding_dim)

    def _generate_fallback_embedding(self, text: str, dim: int = 768) -> List[float]:
        """Generates normalized deterministic pseudo-semantic hash embedding."""
        words = re.findall(r"\w+", text.lower())
        vec = [0.0] * dim
        if not words:
            return vec

        for word in words:
            # Hash word into bucket
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h >> 4) % 2 == 0 else -1.0
            vec[idx] += sign

        # Normalize vector
        magnitude = math.sqrt(sum(x * x for x in vec))
        if magnitude > 0:
            vec = [round(x / magnitude, 6) for x in vec]
        return vec

    # -------------------------------------------------------------
    # Provider-specific completion helpers
    # -------------------------------------------------------------
    async def _ollama_completion(
        self, prompt: str, system_prompt: Optional[str], model: str
    ) -> str:
        payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    async def _gemini_completion(
        self, prompt: str, system_prompt: Optional[str], model: str
    ) -> str:
        api_key = self._key_for("gemini")
        if not api_key:
            raise ValueError("GEMINI_API_KEY belum dikonfigurasi.")
        url = f"{self._base_for('gemini')}/models/{model}:generateContent?key={api_key}"
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Dimengerti. Saya akan mematuhi instruksi sistem tersebut."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"contents": contents},
            )
            resp.raise_for_status()
            candidates = resp.json().get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts).strip()
            return ""

    async def _openai_completion(
        self, prompt: str, system_prompt: Optional[str], model: str
    ) -> str:
        provider = self.provider
        api_key = self._key_for(provider)
        base = self._base_for(provider)
        if not api_key:
            raise ValueError("API key LLM belum dikonfigurasi.")
        if not base:
            raise ValueError("llm_base_url belum dikonfigurasi.")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    async def _anthropic_completion(
        self, prompt: str, system_prompt: Optional[str], model: str
    ) -> str:
        api_key = self._key_for("claude")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY belum dikonfigurasi.")
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self._base_for('claude')}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            blocks = resp.json().get("content", [])
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    # -------------------------------------------------------------
    # Text Completion & Generation
    # -------------------------------------------------------------
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generates completion text from the configured LLM provider."""
        provider = self.provider
        target_model = model or self.model_name

        try:
            if provider == "ollama":
                return await self._ollama_completion(prompt, system_prompt, target_model)
            if provider == "gemini":
                return await self._gemini_completion(prompt, system_prompt, target_model)
            if provider in ("openai", "openai_compatible"):
                return await self._openai_completion(prompt, system_prompt, target_model)
            if provider == "claude":
                return await self._anthropic_completion(prompt, system_prompt, target_model)
            raise ValueError(f"Provider LLM tidak dikenal: {provider}")
        except Exception as e:
            logger.warning(
                "LLM gagal (provider=%s, model=%s): %s", provider, target_model, e
            )

        # Fallback offline synthesis if LLM is unreachable
        return f"[Analisis Sintesis Otomatis]\nBerdasarkan data catatan yang dievaluasi:\n{prompt[:300]}..."

    # -------------------------------------------------------------
    # Structured JSON Completion
    # -------------------------------------------------------------
    async def generate_json_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Requests structured JSON output and safely parses it."""
        json_instruction = (
            "\n\nPENTING: Kembalikan respon HANYA dalam format JSON valid murni tanpa markdown wrapper atau teks penjelasan di luar JSON."
        )
        full_system = f"{system_prompt or ''}{json_instruction}"

        raw_output = await self.generate_completion(
            prompt=prompt, system_prompt=full_system, model=model
        )

        return self._clean_and_parse_json(raw_output)

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """Extracts and parses JSON from markdown fences or raw text."""
        # Clean markdown code blocks ```json ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)

        try:
            return json.loads(cleaned)
        except Exception:
            # Try finding first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except Exception:
                    pass

            return {
                "raw_response": text,
                "error": "Failed to parse structured JSON output",
            }


def get_ollama_client() -> OllamaClient:
    """Helper to access OllamaClient."""
    return OllamaClient()
