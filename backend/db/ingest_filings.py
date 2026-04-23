"""
One-time ingestion script: fetches the latest 10-K for each stock from
SEC EDGAR, splits it with LangChain's RecursiveCharacterTextSplitter,
embeds it with Google's gemini-embedding-001, and stores it in PostgreSQL
via LangChain's PGVector.

Run once from D:\Wealth_Management\finsight\backend:
    python db/ingest_filings.py
"""

import asyncio
import os
import re
import time

import httpx
from dotenv import load_dotenv, find_dotenv

from google import genai as google_genai
from google.genai import types as google_types
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from langchain_core.documents import Document

load_dotenv(find_dotenv(), override=True)

TICKERS = {
    "NVDA":  "0001045810",
    "TSLA":  "0001318605",
    "AAPL":  "0000320193",
    "MSFT":  "0000789019",
    "AMZN":  "0001018724",
    "GOOGL": "0001652044",
    "META":  "0001326801",
}

EDGAR_HEADERS = {"User-Agent": "FinSight mastergowtham1906@gmail.com"}
COLLECTION    = "finsight_filings"
MAX_CHARS     = 80000
EMBED_MODEL   = "models/gemini-embedding-001"
EMBED_DIMS    = 768


class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key: str):
        self._client = google_genai.Client(api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), 50):
            batch = texts[i : i + 50]
            while True:
                try:
                    result = self._client.models.embed_content(
                        model=EMBED_MODEL,
                        contents=batch,
                        config=google_types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=EMBED_DIMS,
                        ),
                    )
                    all_embeddings.extend([e.values for e in result.embeddings])
                    time.sleep(1.0)
                    break
                except Exception as e:
                    msg = str(e)
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        wait = 65
                        import re as _re
                        m = _re.search(r"retry in (\d+)", msg, _re.IGNORECASE)
                        if m:
                            wait = int(m.group(1)) + 5
                        print(f"  Rate limit hit — waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        raise
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


def pg_connection() -> str:
    url = os.getenv("DATABASE_URL", "")
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)


def build_store(embeddings: Embeddings) -> PGVector:
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION,
        connection=pg_connection(),
        use_jsonb=True,
    )


async def fetch_10k(cik: str, ticker: str, client: httpx.AsyncClient):
    r = await client.get(
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        headers=EDGAR_HEADERS,
    )
    r.raise_for_status()
    data = r.json()

    filings = data["filings"]["recent"]
    for i, form in enumerate(filings["form"]):
        if form != "10-K":
            continue

        accession  = filings["accessionNumber"][i].replace("-", "")
        doc        = filings["primaryDocument"][i]
        year       = filings["filingDate"][i][:4]
        cik_int    = int(cik)
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data"
            f"/{cik_int}/{accession}/{doc}"
        )

        time.sleep(0.2)
        r2 = await client.get(filing_url, headers=EDGAR_HEADERS)
        if r2.status_code != 200:
            continue

        text = re.sub(r"<[^>]+>", " ", r2.text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        text = re.sub(r"&#\d+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_CHARS], year

    return "", ""


async def ingest():
    embeddings = GeminiEmbeddings(api_key=os.getenv("GEMINI_API_KEY", ""))
    store      = build_store(embeddings)
    splitter   = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

    async with httpx.AsyncClient(timeout=60) as client:
        for ticker, cik in TICKERS.items():
            print(f"\n[{ticker}] Fetching 10-K from SEC EDGAR...")
            text, year = await fetch_10k(cik, ticker, client)
            if not text:
                print("  No 10-K found — skipping.")
                continue

            source = f"{ticker} Annual Report (10-K {year}, SEC EDGAR)"
            docs: list[Document] = splitter.create_documents(
                texts=[text],
                metadatas=[{"ticker": ticker, "source": source}],
            )
            print(f"  {len(text):,} chars, {len(docs)} chunks. Embedding and storing...")

            await asyncio.to_thread(store.add_documents, docs)
            print(f"  Done — {ticker} stored.")
            print("  Pausing 65s for API rate limit reset...")
            time.sleep(65)

    print("\nIngestion complete. Support chat now uses RAG.")


if __name__ == "__main__":
    asyncio.run(ingest())
