"use client"

import * as React from "react"
import { use } from "react"
import { Copy, Check, Lightning, ArrowCounterClockwise, Export, ShieldCheck } from "@phosphor-icons/react"
import { EnclaveSigBadge } from "@/components/enclave-sig-badge"
import { StatusPill } from "@/components/status-pill"
import { FieldCell, ResultExpandedRow } from "@/components/result-renderer"
import { api } from "@/lib/api"
import type { DisplayMap, NoveltyResult } from "@/lib/types"
import { cn } from "@workspace/ui/lib/utils"
import Link from "next/link"
import { ArrowLeft } from "@phosphor-icons/react"

type Tab = "overview" | "submissions" | "results" | "traces"

export default function DashboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [tab, setTab] = React.useState<Tab>("overview")
  const [adminToken, setAdminToken] = React.useState<string | null>(null)
  const [tokenInput, setTokenInput] = React.useState("")
  const [results, setResults] = React.useState<NoveltyResult[]>([])
  const [display, setDisplay] = React.useState<DisplayMap>({})
  const [subCount, setSubCount] = React.useState(0)
  const [threshold, setThreshold] = React.useState(5)
  const [triggering, setTriggering] = React.useState(false)
  const [triggered, setTriggered] = React.useState(false)
  const [copied, setCopied] = React.useState(false)

  // Load admin token from localStorage
  React.useEffect(() => {
    const raw = localStorage.getItem(`ndai_instance_${id}`)
    if (raw) {
      const data = JSON.parse(raw)
      setAdminToken(data.admin_token)
    }
  }, [id])

  // Poll instance status + fetch skill display hints (public endpoints — no auth needed)
  React.useEffect(() => {
    async function fetchStatus() {
      try {
        const inst = await api.checkInstance(id)
        setSubCount(inst.submissions)
        setThreshold(inst.threshold)
        if (inst.triggered) setTriggered(true)
        // Fetch skill display hints once on first successful status call
        if (inst.skill_name) {
          api.getSkill(inst.skill_name).then((card) => {
            if (card.user_display) setDisplay(card.user_display)
          }).catch(() => {})
        }
      } catch {
        // instance missing or server down — ignore
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000)
    return () => clearInterval(interval)
  }, [id])

  // Once we have the admin token, fetch results if analysis already ran
  React.useEffect(() => {
    if (!adminToken) return
    api.getAllResults(adminToken).then((r) => {
      if (r.results.length > 0) {
        setResults(r.results)
        setTriggered(true)
      }
    }).catch(() => {})
  }, [adminToken])

  async function runAnalysis() {
    if (!adminToken) return
    setTriggering(true)
    await api.trigger(adminToken)
    const r = await api.getAllResults(adminToken)
    setResults(r.results)
    setTriggered(true)
    setTriggering(false)
  }

  async function copyLink() {
    const url = `${window.location.origin}/i/${id}`
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Token gate
  if (!adminToken) {
    return (
      <div className="min-h-screen bg-[#f5f5f7] flex items-center justify-center px-6">
        <div className="w-full max-w-sm rounded-2xl border border-[#d2d2d7] bg-white p-8 text-center shadow-sm">
          <div className="size-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <ShieldCheck weight="fill" className="size-7 text-primary" />
          </div>
          <h1 className="font-bold text-xl text-[#1d1d1f] tracking-apple mb-2">Enter admin token</h1>
          <p className="text-sm text-[#6e6e73] mb-6">
            Paste the admin token issued when you created this instance.
          </p>
          <input
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="adm_…"
            className="w-full rounded-xl border border-[#d2d2d7] bg-[#f5f5f7] px-4 py-2.5 text-sm font-mono text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 mb-3 transition-all"
          />
          <button
            onClick={() => setAdminToken(tokenInput.trim())}
            disabled={!tokenInput.trim()}
            className="w-full rounded-full bg-primary py-2.5 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 transition-all"
          >
            Access Dashboard
          </button>
        </div>
      </div>
    )
  }

  const participantUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/i/${id}`
  const status = triggered ? "complete" : subCount >= threshold ? "analyzing" : "accepting"

  return (
    <div className="min-h-screen bg-[#f5f5f7]">
      {/* Top bar */}
      <div className="border-b border-[#d2d2d7]/60 bg-white/80 backdrop-blur-xl sticky top-0 z-20">
        <div className="mx-auto max-w-[980px] px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <Link href="/" className="text-[#6e6e73] hover:text-[#1d1d1f] transition-colors">
                <ArrowLeft className="size-4" />
              </Link>
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="font-semibold text-base text-[#1d1d1f] tracking-apple">Hackathon Novelty</h1>
                  <StatusPill status={status} />
                </div>
                <p className="text-xs text-[#aeaeb2] font-mono mt-0.5">{id}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={copyLink}
                className="flex items-center gap-1.5 rounded-full border border-[#d2d2d7] bg-white px-4 py-1.5 text-sm text-[#6e6e73] hover:text-[#1d1d1f] hover:border-[#aeaeb2] transition-all"
              >
                {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
                {copied ? "Copied!" : "Copy participant link"}
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-4 -mb-px">
            {(["overview", "submissions", "results", "traces"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "px-4 py-2 text-sm font-medium capitalize rounded-t-lg border-b-2 transition-all",
                  tab === t
                    ? "border-primary text-primary"
                    : "border-transparent text-[#6e6e73] hover:text-[#1d1d1f]",
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[980px] px-6 py-8">
        {/* Overview */}
        {tab === "overview" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Submissions", value: subCount },
                { label: "Threshold", value: threshold },
                { label: "Analyzed", value: triggered ? results.length : "—" },
                { label: "Status", value: triggered ? "Complete" : "Open" },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-2xl border border-[#d2d2d7] bg-white p-5">
                  <p className="text-xs font-medium text-[#6e6e73] mb-1.5">{label}</p>
                  <p className="text-3xl font-bold text-[#1d1d1f] tracking-apple">{value}</p>
                </div>
              ))}
            </div>

            <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
              <div className="flex items-center justify-between mb-4">
                <p className="text-base font-semibold text-[#1d1d1f] tracking-apple">Submission progress</p>
                <span className="text-sm text-[#6e6e73]">{subCount} / {threshold} — analysis triggers at {threshold}</span>
              </div>
              <div className="h-2 rounded-full bg-[#f5f5f7] overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${Math.min((subCount / threshold) * 100, 100)}%` }}
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={runAnalysis}
                disabled={triggering || triggered || subCount === 0}
                className="flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {triggering ? (
                  <><ArrowCounterClockwise className="size-4 animate-spin" /> Running…</>
                ) : triggered ? (
                  <><Check className="size-4" /> Analysis complete</>
                ) : (
                  <><Lightning weight="fill" className="size-4" /> Run Analysis</>
                )}
              </button>

              {triggered && (
                <button
                  onClick={() => {
                    const csv = [
                      ["submission_id", "novelty_score", "percentile", "cluster", "status"].join(","),
                      ...results.map((r) =>
                        [r.submission_id, r.novelty_score, r.percentile, r.cluster, r.status].join(","),
                      ),
                    ].join("\n")
                    const blob = new Blob([csv], { type: "text/csv" })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement("a")
                    a.href = url
                    a.download = `results_${id}.csv`
                    a.click()
                  }}
                  className="flex items-center gap-2 rounded-full border border-[#d2d2d7] bg-white px-6 py-2.5 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] transition-all"
                >
                  <Export className="size-4" /> Export CSV
                </button>
              )}
            </div>
          </div>
        )}

        {/* Submissions */}
        {tab === "submissions" && (
          <div>
            <div className="rounded-2xl border border-[#ff9f0a]/30 bg-[#ff9f0a]/5 px-5 py-3.5 text-sm text-[#ff9f0a] mb-6">
              Submission content is processed inside the enclave only. You cannot read raw submissions.
            </div>
            <div className="rounded-2xl border border-[#d2d2d7] bg-white overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#e8e8ed] bg-[#f5f5f7]">
                    {["#", "Submitted at", "Text", "PDF", "GitHub", "Status"].map((h) => (
                      <th key={h} className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: subCount }).map((_, i) => (
                    <tr key={i} className="border-b border-[#e8e8ed] last:border-0 hover:bg-[#f5f5f7]/50 transition-colors">
                      <td className="px-5 py-3.5 text-sm text-[#6e6e73]">{i + 1}</td>
                      <td className="px-5 py-3.5 text-sm font-mono text-[#6e6e73]">
                        {new Date(Date.now() - i * 3600000).toLocaleString()}
                      </td>
                      <td className="px-5 py-3.5"><Check className="size-4 text-success" /></td>
                      <td className="px-5 py-3.5 text-sm text-[#aeaeb2]">—</td>
                      <td className="px-5 py-3.5"><Check className="size-4 text-success" /></td>
                      <td className="px-5 py-3.5">
                        <span className="text-xs text-[#6e6e73] bg-[#f5f5f7] rounded-full px-2.5 py-1">
                          received
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Results */}
        {tab === "results" && (
          <div>
            {!triggered ? (
              <div className="text-center py-24">
                <p className="text-[#6e6e73] text-base mb-6">No results yet. Run analysis to see results.</p>
                <button
                  onClick={runAnalysis}
                  disabled={triggering}
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white hover:bg-[#5a2fd4] transition-all"
                >
                  <Lightning weight="fill" className="size-4" /> Run Analysis
                </button>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <ShieldCheck weight="fill" className="size-5 text-success" />
                  <span className="text-sm text-success font-medium">Results signed by enclave</span>
                </div>
                <ResultsTable results={results} display={display} />
              </div>
            )}
          </div>
        )}

        {/* Traces */}
        {tab === "traces" && (
          <div className="rounded-2xl border border-[#d2d2d7] bg-white p-10 text-center">
            <p className="text-base text-[#6e6e73] mb-2">Trace data will appear here after analysis runs.</p>
            <p className="text-sm text-[#aeaeb2]">
              Traces show which tools Claude called per submission, output filter pass/fail, and jailbreak test results.
              They contain no raw submission content.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function ResultsTable({
  results,
  display,
}: {
  results: NoveltyResult[]
  display: DisplayMap
}) {
  // Table columns: all display hints except score_table (shown in expanded row)
  const colFields = Object.entries(display).filter(([, h]) => h.type !== "score_table")
  const colCount = 1 + colFields.length // +1 for submission_id

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#e8e8ed] bg-[#f5f5f7]">
            <th className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">
              Submission ID
            </th>
            {colFields.map(([key, hint]) => (
              <th key={key} className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">
                {hint.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <ResultRow key={r.submission_id} result={r} colFields={colFields} colCount={colCount} display={display} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ResultRow({
  result,
  colFields,
  colCount,
  display,
}: {
  result: NoveltyResult
  colFields: [string, import("@/lib/types").DisplayHint][]
  colCount: number
  display: DisplayMap
}) {
  const [expanded, setExpanded] = React.useState(false)
  const row = result as unknown as Record<string, unknown>

  return (
    <>
      <tr
        className="border-b border-[#e8e8ed] last:border-0 hover:bg-[#f5f5f7]/50 transition-colors cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-5 py-3.5 font-mono text-sm text-[#6e6e73]">{result.submission_id}</td>
        {colFields.map(([key, hint]) => (
          <td key={key} className="px-5 py-3.5">
            <FieldCell hint={hint} value={row[key]} />
          </td>
        ))}
      </tr>
      {expanded && (
        <tr className="border-b border-[#e8e8ed] bg-[#f5f5f7]/50">
          <td colSpan={colCount} className="px-6 py-5">
            <ResultExpandedRow result={row} display={display} />
            {result.enclave_signature && (
              <div className="mt-4">
                <EnclaveSigBadge
                  signature={result.enclave_signature}
                  verifyUrl="https://cloud-api.phala.network/api/v1/attestations/verify"
                />
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}
