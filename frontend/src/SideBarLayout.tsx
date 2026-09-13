// import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"
// import Markdown from "react-markdown"
import { cn } from "./lib/utils"

import {
  EllipsisVertical,
  PanelLeftClose,
  Settings,
  //   Sparkles,
  Star,
  StarPlus,
} from "lucide-react"
import { Outlet, useNavigate } from "react-router-dom"

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// type SSEEvent = {
//   type: "summary_chunk" | "title" | "error"
//   content: string
// }

type SummaryItem = {
  id: number
  title: string
  url: string
  created_at: string
}

const SidebarLayout = () => {
  //   const [url, setUrl] = useState("")
  const [title, setTitle] = useState("")
  //   const [summary, setSummary] = useState("")
  //   const [error, setError] = useState("")
  //   const [loading, setLoading] = useState(false)
  const [titles, setTitles] = useState<SummaryItem[]>([])
  const [sidebarVisibility, setSidebarVisibility] = useState(true)
  const [logoSideBar, setLogoSideBar] = useState(false)
  //   const [summaryClicked, setSummaryClicked] = useState(false)

  const navigate = useNavigate()

  useEffect(() => {
    const fetchTitles = async () => {
      try {
        const response = await fetch(`${API_URL}/api/summaries`)

        if (!response.ok) {
          throw new Error(`Failed to fetch summaries (${response.status})`)
        }

        const data: SummaryItem[] = await response.json()
        setTitles(data)
      } catch (err) {
        console.error("Failed to fetch titles:", err)
      }
    }

    fetchTitles()
  }, [title])

  const handleNewChat = () => {
    // setUrl("")
    // setSummary("")
    // setError("")
    // setSummaryClicked(false)
    // setLoading(false)

    setTitle("")
    navigate("/")
  }
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <div
        className={cn(
          "flex flex-col overflow-hidden bg-accent/20 p-4 shadow-2xs transition-all duration-300 ease-in-out",
          sidebarVisibility ? "w-1/5" : "w-16"
        )}
      >
        <div className="relative mt-2 flex h-1/4 items-center justify-between">
          <div className="flex flex-col">
            <div
              className={cn(
                "absolute top-0 font-bold whitespace-nowrap transition-opacity duration-200",
                sidebarVisibility
                  ? "opacity-100"
                  : "pointer-events-none hidden opacity-0"
              )}
            >
              Bookmarks Summarizer
            </div>

            {sidebarVisibility ? (
              <PanelLeftClose
                className="absolute top-0 right-[0.48rem] shrink-0 cursor-pointer hover:scale-110"
                onClick={() => setSidebarVisibility(false)}
              />
            ) : (
              <div
                className="absolute top-0 right-1 mx-auto flex cursor-pointer items-center justify-center"
                onMouseEnter={() => setLogoSideBar(true)}
                onMouseLeave={() => setLogoSideBar(false)}
                onClick={() => setSidebarVisibility(true)}
              >
                {logoSideBar ? (
                  <PanelLeftClose className="hover:scale-110" />
                ) : (
                  <Star />
                )}
              </div>
            )}
            <div
              className={cn(
                "absolute top-15 flex w-full justify-between truncate rounded-md pt-2 pb-2 shadow-md transition-all duration-200 ease-in-out hover:bg-primary/20 dark:hover:bg-primary",
                sidebarVisibility ? "px-2" : "px-1"
              )}
            >
              {sidebarVisibility && (
                <p
                  className={cn(
                    "font-semibold",
                    sidebarVisibility
                      ? "opacity-100"
                      : "pointer-events-none hidden opacity-0"
                  )}
                  onClick={handleNewChat}
                >
                  New chat
                </p>
              )}
              <StarPlus
                className={cn(
                  sidebarVisibility
                    ? "right-0 hover:scale-110"
                    : "right-2 hover:scale-110"
                )}
              />
            </div>
          </div>
        </div>

        <div
          className={cn(
            "truncate transition-all duration-200 ease-in-out",
            sidebarVisibility
              ? "h-px w-full bg-gray-200 dark:bg-white"
              : "pointer-events-none hidden opacity-0"
          )}
        ></div>

        <h2
          className={cn(
            "my-4 font-sans text-lg font-bold",
            sidebarVisibility
              ? "opacity-100"
              : "pointer-events-none hidden opacity-0"
          )}
        >
          History
        </h2>

        <div
          className={cn(
            "truncate transition-all duration-200 ease-in-out",
            sidebarVisibility
              ? "h-px w-full bg-gray-200 dark:bg-white"
              : "pointer-events-none hidden opacity-0"
          )}
        ></div>

        <div
          className={cn(
            "mt-6 h-1/2 flex-1 scroll-fade scrollbar-thin scrollbar-thumb-accent overflow-y-auto transition-opacity duration-200",
            sidebarVisibility ? "opacity-100" : "pointer-events-none opacity-0"
          )}
        >
          <div className="flex flex-col gap-2">
            {titles.map((item) => (
              <button
                key={item.id}
                className="truncate rounded-md p-2 text-left hover:bg-primary/20 dark:hover:bg-primary"
                onClick={() => navigate(`/summary/${item.id}`)}
              >
                <div className="flex items-center justify-between gap-4">
                  {item.title.length > 25 ? (
                    <span>{item.title.slice(0, 25) + "..."}</span>
                  ) : (
                    <span>{item.title}</span>
                  )}
                  <EllipsisVertical className="h-4 transition-all duration-300 ease-in-out hover:scale-110 hover:rotate-90" />
                </div>
              </button>
            ))}
          </div>
        </div>
        <div className="flex h-16 items-center justify-between truncate pt-5 transition-all duration-300 ease-in-out">
          <div
            className={cn(
              "ml-2 font-semibold",
              sidebarVisibility
                ? "opacity-100"
                : "pointer-events-none hidden opacity-0"
            )}
          >
            userName
          </div>
          <Settings
            className={cn(
              sidebarVisibility
                ? "right-0 mr-2 hover:scale-110"
                : "right-2 hover:scale-110"
            )}
          />
        </div>
      </div>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}

export default SidebarLayout
