import { cn } from "@workspace/ui/lib/utils"

interface ChatMessageProps {
  role: "assistant" | "user"
  content: string
  isTyping?: boolean
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
          content
        )}
      </div>
    </div>
  )
}
