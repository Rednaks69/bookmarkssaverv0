import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import Markdown from "react-markdown"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

type Summary = {
  id: number
  title: string
  url: string
  summary: string
  created_at: string
}

export default function SummaryPage() {
  const { id } = useParams<{ id: string }>()

  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!id) return

    const fetchSummary = async () => {
      try {
        setLoading(true)
        setError("")

        const response = await fetch(`${API_URL}/api/summaries/${id}`)

        if (!response.ok) {
          throw new Error("Summary not found")
        }

        const data: Summary = await response.json()
        setSummary(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load summary")
      } finally {
        setLoading(false)
      }
    }

    fetchSummary()
  }, [id])

  if (loading) {
    return <div className="p-6">Loading summary...</div>
  }

  if (error) {
    return <div className="p-6 text-red-500">{error}</div>
  }

  if (!summary) return null

  return (
    <div className="mx-auto w-full max-w-4xl p-6">
      <a className="cursor-pointer text-sm text-gray-400" href={summary.url}>
        {summary.url}
      </a>
      <h1 className="mt-12 mb-6 text-center text-3xl font-bold">
        {summary.title}
      </h1>

      <div className="prose dark:prose-invert max-w-none rounded-sm bg-accent p-6">
        <Markdown>{summary.summary}</Markdown>
      </div>
    </div>
  )
}
