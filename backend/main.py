from crawl4ai import AsyncWebCrawler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import ollama
from pydantic import BaseModel
import os

# -------------------------------------------------------------
LOCAL_MODEL = "qwen2.5:3b"
# Names the local model to use — Qwen 2.5, 3-billion-parameter variant, 
# presumably pulled into Ollama already (ollama pull qwen2.5:3b).

# -------------------------------------------------------------
app = FastAPI()
# Creates the FastAPI application instance
# this object is what you attach routes and middleware to.
# -------------------------------------------------------------
# Read from environment variable with a local fallback
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
# Supports comma-separated list if you ever need multiple origins in production
origins = [origin.strip() for origin in frontend_url.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# This whitelists http://localhost:5173
# (the default Vite dev server port — so this is almost certainly paired with
# a React/Vue/Svelte frontend) to make requests to this API. 
# Without this, a browser at localhost:5173 calling localhost:8000 would get 
# blocked by CORS policy since they're different origins 
# (different ports count as different origins).

# allow_methods=["*"] / allow_headers=["*"] — permits any HTTP method and header
# from that origin.
# allow_credentials=True — allows cookies/auth headers to be sent cross-origin.
# -------------------------------------------------------------
class ScrapeRequest(BaseModel):
  url: str
# Defines the expected JSON body for incoming requests: {"url": "..."}. 
# FastAPI uses this to auto-validate incoming requests and reject 
# malformed ones with a 422 error automatically.
# -------------------------------------------------------------
@app.post("/api/summarize-url")
async def summarize_url(data: ScrapeRequest):
# Registers a POST route at /api/summarize-url. 
# FastAPI parses the incoming JSON into a ScrapeRequest object automatically
# (data.url is guaranteed to be a string if the request reaches this point).
# -------------------------------------------------------------
  # 1. Scrape with Crawl4AI
  async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url=data.url)
    if not result.success:
      raise HTTPException(status_code=400, detail="Crawl failed.")
    markdown_content = result.markdown  
# async with AsyncWebCrawler() as crawler — 
# opens the crawler as an async context manager 
# (handles setup/teardown of the underlying browser instance, 
# likely Playwright under the hood).
# 
# crawler.arun(url=...) — fetches and renders the page, 
# then converts it to markdown (result.markdown), stripping most HTML noise.
# If the crawl fails (bad URL, network error, blocked, etc.), 
# it raises a 400 error immediately with a JSON error message — 
# this is how FastAPI communicates HTTP errors back to the client.
# -------------------------------------------------------------
  if not markdown_content:
    raise HTTPException(status_code=400, detail="No content found.")
# A second guard: even if the crawl "succeeded," the page might 
# have yielded empty content (e.g., JS-only page that didn't render, 
# or truly blank page). This catches that case separately.
# -------------------------------------------------------------
  prompt = (
      """ 
    <task-context>
    You are a helpful assistant that summarizes the content of a URL.
    </task-context>
    <rules>
    - Use quotes from the content of the website to your output.
    - Use paragraphs in your output.
    - do not use bullet points in your output.
    - do not use numbered lists in your output.
    - Use code blocks in your output.    
    </rules>
    <output-format>
    "CRITICAL FORMATTING INSTRUCTION:\n"
    "Line 1 must be a short, punchy title starting with 'TITLE: '.\n"
    "Line 2 and onwards must be the actual summary content.\n\n"
    </output-format>
    """
      f" takeaways:\n\n{markdown_content[:150000]}"
  )
# Constructs the LLM prompt, instructing it to summarize with key takeaways. 
# markdown_content[:15000] truncates to the first 15,000 characters — 
# a crude but simple guard against exceeding the local model's context window 
# (small models like the 3B Qwen variant typically have limited context length). 
# -------------------------------------------------------------

  # 2. Stream generator from Ollama
  def generate():
    stream = ollama.chat(
        model=LOCAL_MODEL, messages=[{"role": "user", "content": prompt}], stream=True
    )
    buffer = ""
    title_sent = False
    
    for chunk in stream:
      content = chunk["message"]["content"]
      buffer += content

      # If we haven't found/sent the title yet, look for a newline
      if not title_sent:
        if "\n" in buffer:
          title_part, rest = buffer.split("\n", 1)
          # Send the title with a special marker or JSON, 
          # or keep it as plain text if you structure it carefully.
          yield f"{title_part}\n---\n"
          title_sent = True
          # Yield whatever text came after the first newline
          if rest:
            yield rest
          buffer = ""
      else:
        # Once title is out, stream the rest normally
        yield content

  return StreamingResponse(generate(), media_type="text/plain")
# generate() is a generator function (uses yield), which is what StreamingResponse 
# needs to progressively send data.
# 
# ollama.chat(..., stream=True) returns an iterator of partial response chunks 
# instead of one blocking call — each chunk contains a fragment of the model's 
# output as it's generated (token-by-token or in small groups).
# 
# The for loop yields each fragment's text content as it arrives, 
# so the client receives the summary as it's being generated rather 
# than waiting for the whole thing.
# 
# StreamingResponse(generate(), media_type="text/plain") wraps this generator 
# so FastAPI streams the HTTP response body chunk-by-chunk to the client — 
# this is what gives you that "typing effect" you see in chat UIs.
# -------------------------------------------------------------

if __name__ == "__main__":
  import uvicorn

  uvicorn.run(app, host="0.0.0.0", port=8000)