import asyncio
import logging
import os
import re
import time

from google import genai as google_genai
from google.genai import types as google_types
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

logger = logging.getLogger("utils.rag")

RAG_TICKERS = {"NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META"}

_TICKER_RE = re.compile(
    r"\b(NVDA|TSLA|AAPL|MSFT|AMZN|GOOGL|META"
    r"|nvidia|tesla|apple|microsoft|amazon|google|meta)\b",
    re.IGNORECASE,
)
_ALIAS = {
    "nvidia": "NVDA", "tesla": "TSLA", "apple": "AAPL",
    "microsoft": "MSFT", "amazon": "AMZN", "google": "GOOGL", "meta": "META",
}

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIMS  = 768

_store: PGVector | None = None


class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key: str):
        self._client = google_genai.Client(api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), 50):
            batch = texts[i : i + 50]
            result = self._client.models.embed_content(
                model=EMBED_MODEL,
                contents=batch,
                config=google_types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBED_DIMS,
                ),
            )
            all_embeddings.extend([e.values for e in result.embeddings])
            time.sleep(0.3)
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self._client.models.embed_content(
            model=EMBED_MODEL,
            contents=[text],
            config=google_types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=EMBED_DIMS,
            ),
        )
        return result.embeddings[0].values


def _get_store() -> PGVector:
    global _store
    if _store is None:
        url  = os.getenv("DATABASE_URL", "")
        conn = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)
        logger.info(f"RAG: building PGVector store, conn prefix={conn[:30]}")
        _store = PGVector(
            embeddings=GeminiEmbeddings(api_key=os.getenv("GEMINI_API_KEY", "")),
            collection_name="finsight_filings",
            connection=conn,
            use_jsonb=True,
        )
    return _store


def detect_tickers(text: str) -> set[str]:
    found = set()
    for m in _TICKER_RE.finditer(text):
        word = m.group().lower()
        found.add(_ALIAS.get(word, word.upper()))
    return found


def _search(store: PGVector, query: str, top_k: int, tickers: list[str]):
    # Try with ticker filter first, fall back to unfiltered if it errors
    try:
        filter_expr = {"ticker": {"$in": tickers}}
        return store.similarity_search(query, k=top_k, filter=filter_expr)
    except Exception as e:
        logger.warning(f"RAG: filtered search failed ({e}), trying unfiltered")
        docs = store.similarity_search(query, k=top_k)
        # manually filter to relevant tickers
        return [d for d in docs if d.metadata.get("ticker") in tickers]


async def retrieve_context(query: str, held_tickers: set[str], top_k: int = 4) -> list[dict]:
    mentioned = detect_tickers(query)
    tickers   = list(mentioned & RAG_TICKERS)
    logger.info(f"RAG: query='{query[:60]}' detected={mentioned} searching={tickers}")

    if not tickers:
        return []

    try:
        store = _get_store()
        docs  = await asyncio.to_thread(_search, store, query, top_k, tickers)
        logger.info(f"RAG: retrieved {len(docs)} chunks for {tickers}")
        return [
            {
                "ticker":  d.metadata.get("ticker", ""),
                "content": d.page_content,
                "source":  d.metadata.get("source", ""),
            }
            for d in docs
        ]
    except Exception as e:
        logger.error(f"RAG: retrieval failed — {e}", exc_info=True)
        return []
