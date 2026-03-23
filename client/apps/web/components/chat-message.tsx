import * as React from "react"
import { cn } from "@workspace/ui/lib/utils"

interface ChatMessageProps {
  role: "assistant" | "user"
  content: string
  isTyping?: boolean
}

// Renders a single line with **bold** support
function InlineMd({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        ),
      )}
    </>
  )
}

function renderMarkdown(content: string) {
  const lines = content.split("\n")
  const elements: React.ReactNode[] = []
  let listItems: string[] = []
  let listType: "ol" | "ul" | null = null

  function flushList() {
    if (listItems.length === 0) return
    if (listType === "ol") {
      elements.push(
        <ol key={elements.length} className="list-decimal list-inside space-y-1 my-2">
          {listItems.map((item, i) => (
            <li key={i}><InlineMd text={item} /></li>
          ))}
        </ol>,
      )
    } else {
      elements.push(
        <ul key={elements.length} className="list-disc list-inside space-y-1 my-2">
          {listItems.map((item, i) => (
            <li key={i}><InlineMd text={item} /></li>
          ))}
        </ul>,
      )
    }
    listItems = []
    listType = null
  }

  for (const line of lines) {
    const olMatch = line.match(/^\d+\.\s+(.*)/)
    const ulMatch = line.match(/^[-*]\s+(.*)/)

    if (olMatch) {
      if (listType && listType !== "ol") flushList()
      listType = "ol"
      listItems.push(olMatch[1]!)
    } else if (ulMatch) {
      if (listType && listType !== "ul") flushList()
      listType = "ul"
      listItems.push(ulMatch[1]!)
    } else {
      flushList()
      if (line.trim() === "") {
        elements.push(<div key={elements.length} className="h-2" />)
      } else {
        elements.push(
          <p key={elements.length}><InlineMd text={line} /></p>,
        )
      }
    }
  }
  flushList()
  return elements
}

export function ChatMessage({ role, content, isTyping }: ChatMessageProps) {
  const isAssistant = role === "assistant"

  return (
    <div className={cn("flex", isAssistant ? "justify-start" : "justify-end")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isAssistant
            ? "bg-[#f5f5f7] text-[#1d1d1f]"
            : "bg-primary/10 text-[#1d1d1f]",
        )}
      >
        {isTyping ? (
          <div className="flex items-center gap-1 py-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="size-1.5 rounded-full bg-[#aeaeb2] animate-bounce"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-1">{renderMarkdown(content)}</div>
        )}
      </div>
    </div>
  )
}
