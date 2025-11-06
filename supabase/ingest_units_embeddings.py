from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The OpenAI Python client is required. Install it with 'pip install openai'."
    ) from exc


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "units_rows.csv"
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def _ensure_env_loaded() -> None:
    if load_dotenv is not None:
        load_dotenv(override=False)


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


def _openai() -> OpenAI:
    return OpenAI()


def _build_content(row: Dict[str, str]) -> str:
    # Normalize likely column names, tolerant to mojibake on 'preço'
    def norm_ascii(s: str) -> str:
        return "".join(ch for ch in (s or "").lower() if "a" <= ch <= "z")

    price_key = None
    for k in row.keys():
        nk = norm_ascii(k)
        if nk.startswith("preco") or nk.startswith("pre"):
            price_key = k
            break

    parts: List[str] = []
    unidade = (row.get("unidade") or "").strip()
    tipologia = (row.get("tipologia") or "").strip()
    bloco = (row.get("bloco") or "").strip()
    piso = (row.get("piso") or "").strip()
    ahb = (row.get("AHB") or "").strip()
    abe = (row.get("ABE") or "").strip()
    preco = (row.get(price_key) or "").strip() if price_key else ""
    luz = (row.get("luz_natural") or "").strip()
    score = (row.get("score") or "").strip()

    if unidade:
        parts.append(f"Unidade {unidade}")
    if bloco:
        parts.append(f"Bloco {bloco}")
    if tipologia:
        parts.append(f"Tipologia {tipologia}")
    if piso:
        parts.append(f"Piso {piso}")
    if ahb:
        parts.append(f"AHB {ahb}")
    if abe:
        parts.append(f"ABE {abe}")
    if preco:
        parts.append(f"Preço {preco}")
    if luz:
        parts.append(f"Luz Natural {luz}")
    if score:
        parts.append(f"Score {score}")

    return ", ".join(parts)


def _row_metadata(row: Dict[str, str]) -> Dict[str, Any]:
    meta_keys = [
        "id",
        "unidade",
        "tipologia",
        "bloco",
        "piso",
        "AHB",
        "ABE",
        "luz_natural",
        "score",
    ]
    meta: Dict[str, Any] = {}
    for k in meta_keys:
        if k in row and row[k] not in (None, ""):
            meta[k] = row[k]
    return meta


def ingest(csv_path: Path = CSV_PATH, batch: int = 64) -> None:
    _ensure_env_loaded()
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    if not url:
        raise RuntimeError("SUPABASE_URL is required")
    rest_table_url = f"{url}/rest/v1/units_embeddings"

    client = _openai()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    def embed_batch(texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        res = client.embeddings.create(model=EMBED_MODEL, input=texts)
        # Keep order aligned
        return [d.embedding for d in res.data]

    payload_batch: List[Dict[str, Any]] = []
    texts: List[str] = []
    row_ids: List[int] = []

    def flush() -> None:
        if not payload_batch:
            return
        resp = requests.post(
            rest_table_url,
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates"},
            data=json.dumps(payload_batch),
            timeout=60,
        )
        resp.raise_for_status()
        payload_batch.clear()

    for row in rows:
        try:
            rid = int((row.get("id") or "").strip() or 0)
        except Exception:
            # Skip rows without an id
            continue
        content = _build_content(row)
        texts.append(content)
        row_ids.append(rid)

        if len(texts) >= batch:
            embs = embed_batch(texts)
            for rid_i, content_i, emb in zip(row_ids, texts, embs):
                payload_batch.append(
                    {
                        "row_id": rid_i,
                        "content": content_i,
                        "metadata": _row_metadata(rows[rid_i - 1]) if rid_i - 1 < len(rows) else {},
                        "embedding": emb,
                    }
                )
            flush()
            texts.clear()
            row_ids.clear()

    if texts:
        embs = embed_batch(texts)
        for rid_i, content_i, emb in zip(row_ids, texts, embs):
            payload_batch.append(
                {
                    "row_id": rid_i,
                    "content": content_i,
                    "metadata": _row_metadata(rows[rid_i - 1]) if rid_i - 1 < len(rows) else {},
                    "embedding": emb,
                }
            )
        flush()


if __name__ == "__main__":
    ingest()

