from __future__ import annotations

import os
import json
from typing import Any, Dict, List

import requests

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # optional

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The OpenAI Python client is required. Install it with 'pip install openai'."
    ) from exc


EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def _ensure_env_loaded() -> None:
    if load_dotenv is not None:
        # Do not override existing env vars
        load_dotenv(override=False)


def _openai_client() -> OpenAI:
    return OpenAI()


def embed_text(text: str) -> List[float]:
    client = _openai_client()
    # Handle both Responses API and embeddings API depending on SDK version
    if hasattr(client, "embeddings"):
        emb = client.embeddings.create(model=EMBED_MODEL, input=text)
        return emb.data[0].embedding  # type: ignore[no-any-return]
    # Fallback should not be needed for SDK >=1.0.0
    raise RuntimeError("OpenAI client missing embeddings.create; upgrade openai>=1.0.0")


def _sb_headers() -> Dict[str, str]:
    url = os.getenv("SUPABASE_URL") or ""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_*_KEY in environment")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def retrieve_context(query: str, k: int = 8, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
    """Return top-k semantic matches from Supabase via the match_units RPC.

    Expects the SQL in supabase/schema_rag.sql to be applied in the project.
    """
    _ensure_env_loaded()
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    if not url:
        return []

    query_embedding = embed_text(query)
    rpc_url = f"{url}/rest/v1/rpc/match_units"
    payload = {
        "query_embedding": query_embedding,
        "match_count": int(k),
        "min_similarity": float(min_similarity),
    }
    try:
        resp = requests.post(rpc_url, headers=_sb_headers(), data=json.dumps(payload), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data  # list of {row_id, content, metadata, similarity}
    except Exception:
        return []


def format_context_for_prompt(matches: List[Dict[str, Any]]) -> str:
    if not matches:
        return ""
    lines: List[str] = []
    for m in matches:
        meta = m.get("metadata") or {}
        prefix = []
        if "id" in meta:
            prefix.append(f"row_id={meta['id']}")
        if "bloco" in meta:
            prefix.append(f"bloco={meta['bloco']}")
        if "unidade" in meta:
            prefix.append(f"unidade={meta['unidade']}")
        if "tipologia" in meta:
            prefix.append(f"tipologia={meta['tipologia']}")
        head = (" ".join(prefix)).strip()
        if head:
            head = f"[{head}] "
        lines.append(f"- {head}{(m.get('content') or '').strip()}")
    return "\n".join(lines)

