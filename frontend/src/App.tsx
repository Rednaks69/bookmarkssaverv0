import { useState } from "react";
import Markdown from "react-markdown";

export default function App() {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSummarize = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true);
    setSummary("");
    setTitle("");

    try {
      const response = await fetch("http://localhost:8000/api/summarize-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulatedText += chunk;

        // Check if the backend's \n---\n separator has arrived in the stream
        if (accumulatedText.includes("\n---\n")) {
          const [rawTitle, bodyPart] = accumulatedText.split("\n---\n");
          setTitle(rawTitle.replace("TITLE: ", "").trim());
          setSummary(bodyPart);
        } else {
          // While the title is still streaming in, keep accumulating it in the view
          setSummary(accumulatedText);
        }
      }
    } catch (err) {
      setSummary("Failed to process request.");
      console.log("Error", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: "600px",
        margin: "40px auto",
        fontFamily: "sans-serif",
        padding: "0 20px",
      }}>
      <h2>URL Summarizer (Crawl4AI + Qwen + Stream)</h2>
      <form
        onSubmit={handleSummarize}
        style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
        <input
          type="url"
          placeholder="https://example.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          style={{ flex: "1", padding: "8px", fontSize: "16px" }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{ padding: "8px 16px", cursor: "pointer" }}>
          {loading ? "Streaming..." : "Summarize"}
        </button>
      </form>

      {summary && (
        <div
          style={{
            background: "#f4f4f4",
            padding: "20px",
            borderRadius: "6px",
          }}>
          {title && <h2 style={{ marginTop: 0, color: "#f00" }}>{title}</h2>}
          <div style={{ whiteSpace: "pre-wrap", color: "#333" }}>
            <Markdown>
              {title ? summary : accumulatedTextForMarkdown(summary)}
            </Markdown>
          </div>
        </div>
      )}
    </div>
  );
}

// Cleans up markdown rendering before the separator finishes arriving
function accumulatedTextForMarkdown(text: string) {
  if (text.includes("\n---\n")) {
    return text.split("\n---\n")[1] || "";
  }
  return text;
}
