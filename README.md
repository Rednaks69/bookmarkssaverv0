# Bookmarks Summarizer (bookmarkssaverv0)
  <img width="1865" height="892" alt="Screenshot 2026-09-22 142854" src="https://github.com/user-attachments/assets/6a992caa-bac6-4806-a344-ae1e862f4dcd" />
  <img width="1869" height="902" alt="Screenshot 2026-09-22 142855" src="https://github.com/user-attachments/assets/f326a758-1ba1-4e82-bafa-6c3d28b9b561" />

## Goal

A full-stack web application that turns any saved webpage URL into a concise
summary and a short title, then persists the result for later retrieval — i.e.
a personal bookmark summarizer / news-aggregator hybrid. A user pastes a URL,
the service fetches the page, summarizes its content using a local language
model, stores the summary + title in a PostgreSQL database, and renders it in a
sidebar history list.

## How It Works

1. **Client** — the React frontend lets a user enter a URL and hit "Summarize".
2. **Backend (FastAPI)** — exposes a POST `/api/summarize-url` endpoint.

3. **SSRF hardening** — the requested hostname is resolved and validated against
   private/internal/loopback/link-local/reserved/multicast/unspecified IPs
   before any fetch.
4. **Crawl** — Crawl4AI fetches the page and extracts Markdown (with a 30s
   timeout).
5. **Summarize** — the Markdown (truncated to 15,000 chars) is streamed through
   a locally hosted Ollama model (`qwen2.5:3b` by default) to produce a bullet-




   point summary. The stream is delivered to the browser as Server-Sent Events
   (SSE) so the summary appears incrementally.
6. **Title** — a second, short prompt + local model call generates a punchy
   title from the summary.
7. **Persist** — the final `title` + `summary` + original `url` are inserted into
   a `summaries` table in PostgreSQL.
8. **History** — the sidebar fetches `/api/summaries` and renders past
   summaries as clickable history items; `/summary/:id` shows the full detail.

## Tech Stack

### Frontend
- React 19 + TypeScript + Vite
- shadcn/ui + Tailwind CSS 4 + Base UI
- react-router-dom (SidebarLayout + routes)
- react-markdown for rendering summaries
- Custom WebGPU shader background (SkullShader)

### Backend
- FastAPI (Python)
- Uvicorn server, port 8000
- Ollama async client (local LLM)
- Crawl4AI (web scraping / Markdown extraction)
- asyncpg (PostgreSQL)
- SSE streaming for incremental summary delivery

### Infrastructure / Data
- PostgreSQL database (`summarizer_db`) with a `summaries` table:
  `id | url | title | summary | created_at`
- Environment-configurable model (`LOCAL_MODEL`), generation timeout, DB URL,
  and frontend URL.

## Scope / Not In Scope

- No bookmark-export, import, or browser-extension plumbing yet.
- No user accounts, auth, or per-user persistence (database is shared/single).
- No full SSRF protection — DNS rebinding is noted as an open hardening item
  in the backend.
- "Welcome to Bookmarks Summarizer" and the SkullShader/WebGPU background are
  present but appear partially scaffolded (recent refactors removed theme-
  toggling and keyboard shortcuts).



