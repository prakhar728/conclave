"use client"

import * as React from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { ArrowLeft, ArrowRight, PaperPlaneTilt, Copy, Check } from "@phosphor-icons/react"
import { TemplateCard, TEMPLATE_CATALOG } from "@/components/template-card"
import { ChatMessage } from "@/components/chat-message"
import { api } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"
import type { InitResponse } from "@/lib/types"
import Link from "next/link"
import { Suspense } from "react"

type Step = 1 | 2 | 3

interface Message {
  role: "assistant" | "user"
  content: string
}

interface ConfigPreview {
  criteria: Array<{ name: string; weight: number }>
  threshold?: number
  hasGuidelines: boolean
}

function SetupContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const initialSkill = searchParams.get("skill") ?? ""

  const [step, setStep] = React.useState<Step>(initialSkill ? 2 : 1)
  const [selectedSkill, setSelectedSkill] = React.useState(initialSkill)

  // Step 2 state
  const [messages, setMessages] = React.useState<Message[]>([])
  const [input, setInput] = React.useState("")
  const [isTyping, setIsTyping] = React.useState(false)
  const [instanceId, setInstanceId] = React.useState<string | null>(null)
  const [configPreview, setConfigPreview] = React.useState<ConfigPreview>({
    criteria: [],
    hasGuidelines: false,
  })

  // Step 3 state
  const [result, setResult] = React.useState<InitResponse | null>(null)
  const [copied, setCopied] = React.useState<string | null>(null)

  const messagesEndRef = React.useRef<HTMLDivElement>(null)

  // Start conversation when entering step 2
  React.useEffect(() => {
    if (step === 2 && messages.length === 0) {
      startConversation()
    }
  }, [step])

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  async function startConversation() {
    setIsTyping(true)
    const res = await api.initInstance({ skill_name: selectedSkill, message: "start" })
    setInstanceId(res.instance_id)
    setIsTyping(false)
    setMessages([{ role: "assistant", content: res.message }])
  }

  async function sendMessage() {
    if (!input.trim() || isTyping || !instanceId) return
    const userMsg = input.trim()
    setInput("")
    setMessages((m) => [...m, { role: "user", content: userMsg }])
    setIsTyping(true)

    const res = await api.initInstance({
      skill_name: selectedSkill,
      message: userMsg,
      instance_id: instanceId,
    })

    setIsTyping(false)

    if (res.status === "ready") {
      setMessages((m) => [...m, { role: "assistant", content: res.message }])
      setResult(res)
      // Save to localStorage
      localStorage.setItem(
        `ndai_instance_${res.instance_id}`,
        JSON.stringify({
          instance_id: res.instance_id,
          skill_name: selectedSkill,
          admin_token: res.admin_token,
          user_token: res.user_token,
          created_at: new Date().toISOString(),
        }),
      )
      setTimeout(() => setStep(3), 1000)
    } else {
      setMessages((m) => [...m, { role: "assistant", content: res.message }])
      updateConfigPreview(userMsg)
    }
  }

  function updateConfigPreview(msg: string) {
    const lower = msg.toLowerCase()
    const newCriteria: Array<{ name: string; weight: number }> = []
    const pairs: Array<[string, RegExp]> = [
      ["Originality", /original/i],
      ["Feasibility", /feasib/i],
      ["Impact", /impact/i],
      ["Innovation", /innovat/i],
      ["Technical Merit", /techni/i],
    ]
    pairs.forEach(([name, re]) => {
      if (re.test(msg)) newCriteria.push({ name, weight: 33 })
    })
    if (newCriteria.length > 0) {
      const equal = Math.floor(100 / newCriteria.length)
      newCriteria.forEach((c, i) => {
        c.weight = i === newCriteria.length - 1 ? 100 - equal * (newCriteria.length - 1) : equal
      })
      setConfigPreview((p) => ({ ...p, criteria: newCriteria }))
    }
    if (/guideline|instruct|judge|prefer/i.test(lower)) {
      setConfigPreview((p) => ({ ...p, hasGuidelines: true }))
    }
    const thresholdMatch = lower.match(/(\d+)\s+submission/)
    if (thresholdMatch) {
      setConfigPreview((p) => ({ ...p, threshold: parseInt(thresholdMatch[1]!) }))
    }
  }

  async function copyToClipboard(text: string, key: string) {
    await navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const participantUrl = result
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/i/${result.instance_id}?token=${result.user_token}`
    : ""

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="border-b border-[#d2d2d7]/60 bg-[#f5f5f7]">
        <div className="mx-auto max-w-[980px] px-6 py-5 flex items-center justify-between">
          <Link
            href="/templates"
            className="inline-flex items-center gap-1.5 text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
          >
            <ArrowLeft className="size-3.5" /> Templates
          </Link>

          {/* Step indicator */}
          <div className="flex items-center gap-2 text-sm">
            {(["Choose Template", "Configure", "Ready"] as const).map((label, i) => {
              const n = (i + 1) as Step
              const active = step === n
              const done = step > n
              return (
                <React.Fragment key={label}>
                  <div className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors",
                    active && "bg-primary/10 text-primary",
                    done && "text-success",
                    !active && !done && "text-[#aeaeb2]",
                  )}>
                    <span className={cn(
                      "size-5 rounded-full flex items-center justify-center text-[11px] font-medium",
                      active && "bg-primary text-white",
                      done && "bg-success text-white",
                      !active && !done && "bg-[#e8e8ed] text-[#aeaeb2]",
                    )}>
                      {done ? "✓" : n}
                    </span>
                    <span className="hidden sm:inline">{label}</span>
                  </div>
                  {i < 2 && <ArrowRight className="size-3 text-[#d2d2d7]" />}
                </React.Fragment>
              )
            })}
          </div>

          <div className="w-20" />
        </div>
      </div>

      {/* Step 1 — Choose Template */}
      {step === 1 && (
        <div className="mx-auto max-w-[980px] px-6 py-16">
          <h1 className="text-3xl font-bold tracking-apple-tight text-[#1d1d1f] mb-3">
            Choose a template
          </h1>
          <p className="text-base text-[#6e6e73] mb-10">
            Select the skill that matches your use case.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            {TEMPLATE_CATALOG.map((t) => (
              <TemplateCard
                key={t.name}
                template={t}
                selectable
                selected={selectedSkill === t.name}
                onSelect={() => setSelectedSkill(t.name)}
              />
            ))}
          </div>
          <div className="flex justify-end">
            <button
              onClick={() => setStep(2)}
              disabled={!selectedSkill}
              className="flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              Next <ArrowRight className="size-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — Configure (chat) */}
      {step === 2 && (
        <div className="mx-auto max-w-[980px] px-6 py-8 flex gap-6 h-[calc(100vh-130px)]">
          {/* Chat panel */}
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 overflow-y-auto space-y-4 pr-2 pb-4">
              {messages.map((m, i) => (
                <ChatMessage key={i} role={m.role} content={m.content} />
              ))}
              {isTyping && <ChatMessage role="assistant" content="" isTyping />}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="flex gap-3 pt-4 border-t border-[#e8e8ed]">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
                placeholder="Describe your hackathon, criteria, guidelines…"
                className="flex-1 rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                disabled={isTyping}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || isTyping}
                className="rounded-xl bg-primary px-4 py-2.5 text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                <PaperPlaneTilt weight="fill" className="size-4" />
              </button>
            </div>
          </div>

          {/* Config preview panel */}
          <div className="hidden lg:block w-72 shrink-0">
            <div className="rounded-2xl border border-[#d2d2d7] bg-[#f5f5f7] p-5 sticky top-6">
              <p className="text-xs font-semibold text-[#6e6e73] uppercase tracking-widest mb-5">
                Config Preview
              </p>

              {configPreview.criteria.length === 0 ? (
                <p className="text-sm text-[#aeaeb2]">
                  Criteria will appear here as we chat…
                </p>
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-[#6e6e73] mb-3">Criteria</p>
                    {configPreview.criteria.map((c) => (
                      <div key={c.name} className="mb-3">
                        <div className="flex justify-between text-xs mb-1.5">
                          <span className="text-[#1d1d1f] font-medium">{c.name}</span>
                          <span className="text-[#6e6e73]">{c.weight}%</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white overflow-hidden">
                          <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{ width: `${c.weight}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  {configPreview.threshold && (
                    <div className="text-sm">
                      <span className="text-[#6e6e73]">Threshold: </span>
                      <span className="text-[#1d1d1f] font-medium">{configPreview.threshold} submissions</span>
                    </div>
                  )}
                  {configPreview.hasGuidelines && (
                    <div className="text-sm text-success flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-success" />
                      Guidelines detected
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 3 — Ready */}
      {step === 3 && result && (
        <div className="mx-auto max-w-xl px-6 py-20 text-center">
          <div className="size-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-6">
            <Check weight="bold" className="size-8 text-success" />
          </div>
          <h1 className="text-3xl font-bold tracking-apple-tight text-[#1d1d1f] mb-3">
            Instance created
          </h1>
          <p className="text-base text-[#6e6e73] mb-12">
            Share the participant link to start collecting submissions.
          </p>

          <div className="space-y-4 text-left">
            <TokenRow
              label="Participant link"
              value={participantUrl}
              onCopy={() => copyToClipboard(participantUrl, "link")}
              copied={copied === "link"}
              highlight
            />
            <TokenRow
              label="Admin token"
              value={result.admin_token ?? ""}
              onCopy={() => copyToClipboard(result.admin_token ?? "", "admin")}
              copied={copied === "admin"}
              warning="Save this — it cannot be recovered"
            />
          </div>

          <div className="flex flex-col sm:flex-row gap-3 mt-12">
            <Link
              href={`/dashboard/${result.instance_id}`}
              className="flex-1 rounded-full bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-[#5a2fd4] transition-all text-center"
            >
              Go to Dashboard
            </Link>
            <Link
              href="/setup"
              onClick={() => {
                setStep(1)
                setSelectedSkill("")
                setMessages([])
                setInstanceId(null)
                setResult(null)
              }}
              className="flex-1 rounded-full border border-[#d2d2d7] px-4 py-3 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] transition-all text-center"
            >
              Create another
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

export default function SetupPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <SetupContent />
    </Suspense>
  )
}

function TokenRow({
  label,
  value,
  onCopy,
  copied,
  highlight = false,
  warning,
}: {
  label: string
  value: string
  onCopy: () => void
  copied: boolean
  highlight?: boolean
  warning?: string
}) {
  return (
    <div className={cn(
      "rounded-2xl border p-5",
      highlight ? "border-primary/30 bg-primary/5" : "border-[#d2d2d7] bg-[#f5f5f7]",
    )}>
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-xs font-semibold text-[#6e6e73] uppercase tracking-widest">{label}</span>
        <button
          onClick={onCopy}
          className="flex items-center gap-1 text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
        >
          {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <p className="font-mono text-xs text-[#1d1d1f] break-all leading-relaxed">{value}</p>
      {warning && (
        <p className="mt-2.5 text-xs text-[#ff9f0a]">⚠ {warning}</p>
      )}
    </div>
  )
}
