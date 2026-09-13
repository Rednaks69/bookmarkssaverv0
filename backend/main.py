"""
URL summarization service with PostgreSQL persistence.

Pipeline: crawl a URL with Crawl4AI -> stream a summary from a local
Ollama model -> generate a short title -> save to PostgreSQL.
Results are streamed to the client as Server-Sent Events (SSE).
"""

import asyncio
import ipaddress
import json
import logging
import os
import socket
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import asyncpg
import ollama
from crawl4ai import AsyncWebCrawler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen2.5:3b")
MAX_CONTENT_CHARS = int(os.getenv("MAX_CONTENT_CHARS", "15000"))
CRAWL_TIMEOUT_SECONDS = int(os.getenv("CRAWL_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_MODEL_CALLS = int(os.getenv("MAX_CONCURRENT_MODEL_CALLS", "1"))
ALLOWED_URL_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
GENERATION_TIMEOUT_SECONDS = int(os.getenv("GENERATION_TIMEOUT_SECONDS", "120"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/summarizer_db")

SUMMARY_PROMPT_TEMPLATE = (
    """ 
      <task-context>
      You are a helpful assistant that summarizes the content of a URL.
      </task-context>
      <rules>
      - Use quotes from the content of the website to your output.
      - Use paragraphs in your output to separate content by including an empty line between paragraphs.
      - Use bullet points in your output.
      - do not use numbered lists in your output.
      - Use code blocks in your output if the content is code snippets and color them.
      - Not use the word "summary" or "Summary" or "SUMMARY" in your output.
      - break a line when there is new subtitle ### or ## or # in the content.    
      </rules>
      """
    " it's very important to highlight key takeaways:\n\n{content}"
)
TITLE_PROMPT_TEMPLATE = (
    "Based on the following summary, generate a short, punchy title. "
    "Return ONLY the title text with no extra commentary, prefixes, or markdown formatting.\n\n"
    "Summary:\n{summary}"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", filename="summarizer.log", filemode="w", force=True)
logger = logging.getLogger("summarizer")

model_semaphore = asyncio.Semaphore(MAX_CONCURRENT_MODEL_CALLS)


# --------------------------------------------------------------------------
# App setup & Lifespan (Database Pool)
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ollama_client = ollama.AsyncClient()

    # Initialize PostgreSQL connection pool and ensure table exists
    app.state.db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with app.state.db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
    yield
    
    app.state.db_pool = await asyncpg.create_pool(DATABASE_URL)
    logger.info("Connected to Postgres, DSN=%s", DATABASE_URL)
    async with app.state.db_pool.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS summaries (...)""")
        logger.info("Ensured summaries table exists")
    
    
    await app.state.db_pool.close()


app = FastAPI(lifespan=lifespan)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [origin.strip() for origin in frontend_url.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# SSRF protection: hostname resolution + IP validation
# --------------------------------------------------------------------------

async def resolve_and_check_host(hostname: str) -> None:
    """Resolve hostname to all its IPs and reject if any are private/internal.

    Note: this closes the "obvious hostname" gap (localhost, 127.0.0.1, etc.)
    but does not fully close DNS rebinding, since crawl_url() performs its
    own separate resolution later. For full protection, resolve once here,
    validate the IP, then pass that IP directly to the crawler (with the
    original Host header) instead of re-resolving — or enforce network-level
    egress rules blocking private ranges from the crawler's environment.
    """
    try:
        loop = asyncio.get_event_loop()
        # getaddrinfo returns all A/AAAA records - check every one,
        # not just the first, since DNS can return multiple IPs
        addrinfo = await loop.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {hostname}") from exc

    for family, _, _, _, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local      # covers 169.254.0.0/16 - cloud metadata range
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(
                f"URL host resolves to a disallowed address ({ip_str})"
            )


# --------------------------------------------------------------------------
# Request schema
# --------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, value: str) -> str:
        """Sync checks only: scheme + hostname presence.

        DNS-based checks (resolve_and_check_host) run separately in the
        route handler since they require async I/O and can't live in a
        sync Pydantic validator.
        """
        parsed = urlparse(value)
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            raise ValueError(f"URL scheme must be one of {ALLOWED_URL_SCHEMES}")
        if not parsed.hostname:
            raise ValueError("URL must include a hostname")
        if parsed.hostname.lower() in BLOCKED_HOSTS:
            raise ValueError("URL host is not allowed")
        return value


# --------------------------------------------------------------------------
# SSE helpers
# --------------------------------------------------------------------------

def sse_event(event_type: str, content: str) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


SSE_DONE = "data: [DONE]\n\n"


# --------------------------------------------------------------------------
# Pipeline steps
# --------------------------------------------------------------------------

async def crawl_url(url: str) -> str:
    try:
        async with AsyncWebCrawler() as crawler:
            result = await asyncio.wait_for(
                crawler.arun(url=url), timeout=CRAWL_TIMEOUT_SECONDS
            )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Crawl timed out.") from exc

    if not result.success:
        raise HTTPException(status_code=400, detail="Crawl failed.")
    if not result.markdown:
        raise HTTPException(status_code=400, detail="No content found.")

    return result.markdown


async def generate_title(client: ollama.AsyncClient, summary: str) -> str:
    prompt = TITLE_PROMPT_TEMPLATE.format(summary=summary)
    async with model_semaphore:
        response = await client.chat(
            model=LOCAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
    return response["message"]["content"].strip().strip('"')


# --------------------------------------------------------------------------
# Route
# --------------------------------------------------------------------------



@app.post("/api/summarize-url")
async def summarize_url(data: ScrapeRequest):
    hostname = urlparse(data.url).hostname
    try:
        await resolve_and_check_host(hostname)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    markdown_content = await crawl_url(data.url)

    async def event_generator():
        client: ollama.AsyncClient = app.state.ollama_client
        accumulated_summary = ""

        async def run_stream():
            nonlocal accumulated_summary
            async with model_semaphore:
                stream = await client.chat(
                    model=LOCAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    options={
                        "num_predict": 800,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 256,
                    },
                )
                async for chunk in stream:
                    token = chunk["message"]["content"]
                    accumulated_summary += token
                    yield sse_event("summary_chunk", token)

        try:
            prompt = SUMMARY_PROMPT_TEMPLATE.format(content=markdown_content[:MAX_CONTENT_CHARS])

            try:
                async with asyncio.timeout(GENERATION_TIMEOUT_SECONDS):
                    async for event in run_stream():
                        yield event
            except TimeoutError:
                logger.warning("Generation timed out after %ss", GENERATION_TIMEOUT_SECONDS)
                yield sse_event("summary_chunk", "\n\n[Response truncated: generation took too long.]")

            title = await generate_title(client, accumulated_summary)
            yield sse_event("title", title)

            pool: asyncpg.Pool = app.state.db_pool
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO summaries (url, title, summary) VALUES ($1, $2, $3)",
                    data.url, title, accumulated_summary
                )

        except Exception:
            logger.exception("Summarization pipeline failed for url=%s", data.url)
            yield sse_event("error", "Something went wrong while generating the summary.")
        finally:
            yield SSE_DONE

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/summaries")
async def get_summaries():
    pool: asyncpg.Pool = app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, url, created_at
            FROM summaries
            ORDER BY created_at DESC
        """)
        
    if not rows:
        raise HTTPException(status_code=404, detail="No summaries found.")

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "url": row["url"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]
    
@app.get("/api/summaries/{summary_id}")
async def get_summary(summary_id: int):
    pool: asyncpg.Pool = app.state.db_pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, title, url, summary, created_at
            FROM summaries
            WHERE id = $1
        """, summary_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Summary not found"
        )

    return {
        "id": row["id"],
        "title": row["title"],
        "url": row["url"],
        "summary": row["summary"],
        "created_at": row["created_at"].isoformat(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)