import { Button } from "@/components/ui/button"
import { useState } from "react"
import Markdown from "react-markdown"
import { cn } from "./lib/utils"
import { Sparkles } from "lucide-react"
import { SkullShader } from "./SkullShader"
import { useTheme } from "@/components/theme-provider"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

type SSEEvent = {
  type: "summary_chunk" | "title" | "error"
  content: string
}

export default function SummarizerLayout() {
  // const [theme, setTheme] = useState<"light" | "dark">(
  //   document.documentElement.classList.contains("dark") ? "dark" : "light"
  // )

  const { theme } = useTheme()

  const [url, setUrl] = useState("")
  const [title, setTitle] = useState("")
  const [summary, setSummary] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [summaryClicked, setSummaryClicked] = useState(false)

  // useEffect(() => {
  //   const handleKeyDown = (e: KeyboardEvent) => {
  //     // Don't toggle while typing in the URL input
  //     if (
  //       e.target instanceof HTMLInputElement ||
  //       e.target instanceof HTMLTextAreaElement
  //     ) {
  //       return
  //     }

  //     if (e.key.toLowerCase() === "d") {
  //       const nextTheme = theme === "dark" ? "light" : "dark"

  //       document.documentElement.classList.toggle("dark", nextTheme === "dark")

  //       setTheme(nextTheme)
  //     }
  //   }

  //   window.addEventListener("keydown", handleKeyDown)

  //   return () => {
  //     window.removeEventListener("keydown", handleKeyDown)
  //   }
  // }, [theme])

  const handleSummarize = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url) return

    setLoading(true)
    setSummary("")
    setTitle("")
    setError("")
    setSummaryClicked(true)

    try {
      const response = await fetch(`${API_URL}/api/summarize-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null)
        throw new Error(
          errorBody?.detail ?? `Request failed (${response.status})`
        )
      }
      if (!response.body) throw new Error("No response body")

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      let accumulatedSummary = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split("\n\n")
        buffer = events.pop() ?? ""

        for (const rawEvent of events) {
          const dataLine = rawEvent
            .split("\n")
            .find((line) => line.startsWith("data: "))
          if (!dataLine) continue

          const payload = dataLine.slice("data: ".length).trim()
          if (payload === "[DONE]") continue

          let parsed: SSEEvent
          try {
            parsed = JSON.parse(payload)
          } catch {
            continue
          }

          if (parsed.type === "summary_chunk") {
            accumulatedSummary += parsed.content
            setSummary(accumulatedSummary)
          } else if (parsed.type === "title") {
            setTitle(parsed.content)
          } else if (parsed.type === "error") {
            setError(parsed.content)
          }
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to process request."
      )
      console.error("Error", err)
    } finally {
      setLoading(false)
      setUrl("")
    }
  }

  return (
    <div className="relative flex h-full w-full flex-1 overflow-hidden bg-background">
      {/* Full-screen WebGPU background */}
      {!summaryClicked && (
        <div className="pointer-events-none absolute inset-0 z-0">
          <SkullShader
            theme={theme}
            background={{
              dark: "#090909",
              light: "#ffffff",
            }}
          />
        </div>
      )}
      {/* Foreground content */}
      <div
        className={cn(
          "relative z-10 flex flex-1 flex-col p-4",
          summaryClicked
            ? "justify-between overflow-y-auto"
            : "items-center justify-center"
        )}
      >
        {summaryClicked && (
          <div className="flex w-full flex-col items-start justify-baseline">
            {summary && (
              <div className="w-full bg-accent/80 p-2">
                {title && (
                  <h2 className="bg-accent/80 p-4 pt-8 text-center font-bold text-wrap text-foreground">
                    {title}
                  </h2>
                )}

                <div className="mt-4 items-start bg-accent/80 p-4 text-foreground">
                  <Markdown>{summary}</Markdown>
                </div>
              </div>
            )}
          </div>
        )}

        <div
          className={cn(
            "flex flex-col items-center",
            summaryClicked ? "hidden" : "w-1/2 rounded-xl p-4"
          )}
        >
          {!summaryClicked && (
            <div className="flex w-full items-center justify-between px-2 py-6">
              <h1 className="font-mono text-2xl font-bold">
                Welcome to Bookmarks Summarizer
              </h1>
              <Sparkles />
            </div>
          )}
          <form
            onSubmit={handleSummarize}
            className="flex w-full max-w-2xl items-center gap-2 pt-4"
          >
            <input
              type="url"
              placeholder="https://example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              className="flex-1 rounded-md border border-input bg-background p-2 text-sm font-medium text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
            />
            <Button
              type="submit"
              disabled={loading}
              style={{ padding: "8px 16px", cursor: "pointer" }}
            >
              {loading ? "Streaming..." : "Summarize"}
            </Button>
          </form>

          {error && (
            <div
              style={{
                background: "#fdecea",
                color: "#611a15",
                padding: "12px 16px",
                borderRadius: "6px",
                marginTop: "12px",
              }}
              className="w-full max-w-2xl"
            >
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
