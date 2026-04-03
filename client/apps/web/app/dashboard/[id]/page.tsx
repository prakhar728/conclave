"use client"

import * as React from "react"
import { use } from "react"
import {
  Copy,
  Check,
  Lightning,
  ArrowCounterClockwise,
  Export,
  ShieldCheck,
  CaretDown,
} from "@phosphor-icons/react"
import { EnclaveSigBadge } from "@/components/enclave-sig-badge"
import { StatusPill } from "@/components/status-pill"
import { FieldCell, ResultExpandedRow } from "@/components/result-renderer"
import { HardConstraintsCard } from "@/components/hard-constraints-card"
import { MilestoneBreakdown } from "@/components/milestone-breakdown"
import { ProcurementScorecard } from "@/components/procurement-scorecard"
import { NegotiationPanel } from "@/components/negotiation-panel"
import { ReleaseTokenCard } from "@/components/release-token-card"
import { api } from "@/lib/api"
import type { DisplayMap, NoveltyResult, ProcurementResult, SubmissionMeta } from "@/lib/types"
import { cn } from "@workspace/ui/lib/utils"
import Link from "next/link"
import { ArrowLeft } from "@phosphor-icons/react"

type Tab = "overview" | "submissions" | "results" | "deals" | "traces"

export default function DashboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [tab, setTab] = React.useState<Tab>("overview")
  const [adminToken, setAdminToken] = React.useState<string | null>(null)
  const [tokenInput, setTokenInput] = React.useState("")
  const [isProcurement, setIsProcurement] = React.useState(false)

  // Hackathon state
  const [results, setResults] = React.useState<NoveltyResult[]>([])
  const [display, setDisplay] = React.useState<DisplayMap>({})
  const [submissionMetas, setSubmissionMetas] = React.useState<SubmissionMeta[]>([])
  const [triggering, setTriggering] = React.useState(false)
  const [triggered, setTriggered] = React.useState(false)

  // Procurement state
  const [procResults, setProcResults] = React.useState<ProcurementResult[]>([])
  const [dealActions, setDealActions] = React.useState<Record<string, "accepted" | "rejected" | "renegotiating">>({})

  const [subCount, setSubCount] = React.useState(0)
  const [threshold, setThreshold] = React.useState(5)
  const [copied, setCopied] = React.useState(false)

  React.useEffect(() => {
    const raw = localStorage.getItem(`ndai_instance_${id}`)
    if (raw) {
      const data = JSON.parse(raw)
      setAdminToken(data.admin_token)
    }
  }, [id])

  React.useEffect(() => {
    async function fetchStatus() {
      try {
        const inst = await api.checkInstance(id)
        setSubCount(inst.submissions)
        setThreshold(inst.threshold)
        if (inst.triggered) setTriggered(true)
        const proc = inst.skill_name === "confidential_data_procurement"
        setIsProcurement(proc)
        if (!proc && inst.skill_name) {
          api.getSkill(inst.skill_name).then((card) => {
            if (card.user_display) setDisplay(card.user_display)
          }).catch(() => {})
        }
      } catch {
        // ignore
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000)
    return () => clearInterval(interval)
  }, [id])

  React.useEffect(() => {
    if (!adminToken) return
    api.checkInstance(id).then((inst) => {
      if (inst.skill_name === "confidential_data_procurement") {
        api.getProcurementResults(adminToken).then((r) => {
          if (r.results.length > 0) setProcResults(r.results)
        }).catch(() => {})
      } else {
        api.getAllResults(adminToken).then((r) => {
          if (r.results.length > 0) {
            setResults(r.results)
            setTriggered(true)
          }
        }).catch(() => {})
        api.getSubmissions(adminToken).then((r) => {
          if (r.submissions.length > 0) setSubmissionMetas(r.submissions)
        }).catch(() => {})
      }
    }).catch(() => {})
  }, [adminToken])

  async function runAnalysis() {
    if (!adminToken) return
    setTriggering(true)
    await api.trigger(adminToken)
    const [r, s] = await Promise.all([
      api.getAllResults(adminToken),
      api.getSubmissions(adminToken),
    ])
    setResults(r.results)
    setSubmissionMetas(s.submissions)
    setTriggered(true)
    setTriggering(false)
  }

  async function copyLink() {
    const url = `${window.location.origin}/i/${id}`
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function handleAccept(procResult: ProcurementResult) {
    if (!adminToken) return
    await api.acceptDeal(adminToken, procResult.submission_id)
    const token = await api.getReleaseToken(adminToken, procResult.submission_id)
    setDealActions((a) => ({ ...a, [procResult.submission_id]: "accepted" }))
    setProcResults((rs) =>
      rs.map((r) =>
        r.submission_id === procResult.submission_id
          ? { ...r, release_token: token, negotiation: { ...r.negotiation, state: "accepted" }, settlement: { state: "authorized", amount: r.proposed_payment } }
          : r,
      ),
    )
  }

  async function handleReject(procResult: ProcurementResult) {
    if (!adminToken) return
    await api.rejectDeal(adminToken, procResult.submission_id)
    setDealActions((a) => ({ ...a, [procResult.submission_id]: "rejected" }))
    setProcResults((rs) =>
      rs.map((r) =>
        r.submission_id === procResult.submission_id
          ? { ...r, negotiation: { ...r.negotiation, state: "rejected" }, settlement: { state: "failed" } }
          : r,
      ),
    )
  }

  async function handleRenegotiate(procResult: ProcurementResult, revisedBudget: number) {
    if (!adminToken) return
    await api.requestNegotiation(adminToken, procResult.submission_id, revisedBudget)
    setDealActions((a) => ({ ...a, [procResult.submission_id]: "renegotiating" }))
    setProcResults((rs) =>
      rs.map((r) =>
        r.submission_id === procResult.submission_id
          ? { ...r, negotiation: { state: "requested_by_buyer", revised_budget: revisedBudget, used: true } }
          : r,
      ),
    )
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
  const status = triggered || procResults.length > 0
    ? "complete"
    : subCount >= threshold
    ? "analyzing"
    : "accepting"

  // Tabs vary by protocol
  const tabs: Tab[] = isProcurement
    ? ["overview", "submissions", "deals", "traces"]
    : ["overview", "submissions", "results", "traces"]

  // Procurement deal stats
  const acceptedDeals = procResults.filter((r) => r.negotiation.state === "accepted").length
  const pendingDeals = procResults.filter((r) => r.negotiation.state === "none").length
  const totalPayment = procResults
    .filter((r) => r.settlement.state === "authorized")
    .reduce((sum, r) => sum + (r.settlement.amount ?? 0), 0)

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
                  <h1 className="font-semibold text-base text-[#1d1d1f] tracking-apple">
                    {isProcurement ? "Confidential Data Procurement" : "Hackathon Novelty"}
                  </h1>
                  <StatusPill status={status} />
                </div>
                <p className="text-xs text-[#aeaeb2] font-mono mt-0.5">{id}</p>
              </div>
            </div>
            <button
              onClick={copyLink}
              className="flex items-center gap-1.5 rounded-full border border-[#d2d2d7] bg-white px-4 py-1.5 text-sm text-[#6e6e73] hover:text-[#1d1d1f] hover:border-[#aeaeb2] transition-all"
            >
              {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
              {copied ? "Copied!" : isProcurement ? "Copy seller link" : "Copy participant link"}
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-4 -mb-px">
            {tabs.map((t) => (
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

        {/* ── OVERVIEW ── */}
        {tab === "overview" && (
          <div className="space-y-6">
            {isProcurement ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: "Seller Submissions", value: subCount },
                    { label: "Evaluated", value: procResults.length },
                    { label: "Deals Closed", value: acceptedDeals },
                    { label: "Total Settled", value: totalPayment > 0 ? `$${totalPayment.toLocaleString()}` : "—" },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-2xl border border-[#d2d2d7] bg-white p-5">
                      <p className="text-xs font-medium text-[#6e6e73] mb-1.5">{label}</p>
                      <p className="text-3xl font-bold text-[#1d1d1f] tracking-apple">{value}</p>
                    </div>
                  ))}
                </div>

                {procResults.length > 0 && (
                  <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
                    <p className="text-sm font-semibold text-[#1d1d1f] mb-4">Deal Pipeline</p>
                    <div className="space-y-3">
                      {procResults.map((r) => (
                        <div key={r.submission_id} className="flex items-center justify-between text-sm">
                          <span className="font-mono text-[#6e6e73]">{r.submission_id}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-[#1d1d1f]">${r.proposed_payment.toLocaleString()}</span>
                            <DealStatusBadge state={r.negotiation.state} settlement={r.settlement.state} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {procResults.length === 0 && (
                  <div className="rounded-2xl border border-[#d2d2d7] bg-white p-10 text-center">
                    <p className="text-[#6e6e73]">No evaluated submissions yet.</p>
                    <p className="text-sm text-[#aeaeb2] mt-1">
                      Sellers submit datasets via the seller link. Results appear here after the enclave evaluates each one.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
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
                          ["submission_id", "novelty_score", "status"].join(","),
                          ...results.map((r) => [r.submission_id, r.novelty_score, r.status].join(",")),
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
              </>
            )}
          </div>
        )}

        {/* ── SUBMISSIONS ── */}
        {tab === "submissions" && (
          <div>
            <div className="rounded-2xl border border-[#ff9f0a]/30 bg-[#ff9f0a]/5 px-5 py-3.5 text-sm text-[#ff9f0a] mb-6">
              {isProcurement
                ? "Dataset content is processed inside the enclave only. Raw rows are never visible here."
                : "Submission content is processed inside the enclave only. You cannot read raw submissions."}
            </div>
            <div className="rounded-2xl border border-[#d2d2d7] bg-white overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#e8e8ed] bg-[#f5f5f7]">
                    {isProcurement
                      ? ["#", "Submitted at", "Dataset", "Eval status", "Score", "Payment"].map((h) => (
                          <th key={h} className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">{h}</th>
                        ))
                      : ["#", "Submitted at", "Text", "PDF", "GitHub", "Status"].map((h) => (
                          <th key={h} className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">{h}</th>
                        ))
                    }
                  </tr>
                </thead>
                <tbody>
                  {isProcurement
                    ? procResults.length > 0
                      ? procResults.map((r, i) => (
                          <tr key={r.submission_id} className="border-b border-[#e8e8ed] last:border-0 hover:bg-[#f5f5f7]/50 transition-colors">
                            <td className="px-5 py-3.5 text-sm text-[#6e6e73]">{i + 1}</td>
                            <td className="px-5 py-3.5 text-sm font-mono text-[#6e6e73]">
                              {new Date(Date.now() - i * 3600000).toLocaleString()}
                            </td>
                            <td className="px-5 py-3.5 text-sm font-mono text-[#6e6e73]">{r.submission_id}</td>
                            <td className="px-5 py-3.5">
                              <DealStatusBadge state={r.negotiation.state} settlement={r.settlement.state} />
                            </td>
                            <td className="px-5 py-3.5 text-sm font-mono text-[#1d1d1f]">
                              {(r.partial_score * 100).toFixed(0)}
                            </td>
                            <td className="px-5 py-3.5 text-sm text-[#1d1d1f]">
                              ${r.proposed_payment.toLocaleString()}
                            </td>
                          </tr>
                        ))
                      : Array.from({ length: subCount }).map((_, i) => (
                          <tr key={i} className="border-b border-[#e8e8ed] last:border-0">
                            <td className="px-5 py-3.5 text-sm text-[#6e6e73]">{i + 1}</td>
                            <td className="px-5 py-3.5 text-sm font-mono text-[#6e6e73]">
                              {new Date(Date.now() - i * 3600000).toLocaleString()}
                            </td>
                            <td className="px-5 py-3.5 text-sm text-[#aeaeb2]">—</td>
                            <td className="px-5 py-3.5">
                              <span className="text-xs text-[#6e6e73] bg-[#f5f5f7] rounded-full px-2.5 py-1">pending</span>
                            </td>
                            <td className="px-5 py-3.5 text-[#aeaeb2]">—</td>
                            <td className="px-5 py-3.5 text-[#aeaeb2]">—</td>
                          </tr>
                        ))
                    : submissionMetas.length > 0
                      ? submissionMetas.map((s, i) => (
                          <tr key={s.submission_id} className="border-b border-[#e8e8ed] last:border-0 hover:bg-[#f5f5f7]/50 transition-colors">
                            <td className="px-5 py-3.5 text-sm text-[#6e6e73]">{i + 1}</td>
                            <td className="px-5 py-3.5 text-sm font-mono text-[#6e6e73]">
                              {s.submitted_at ? new Date(s.submitted_at).toLocaleString() : "—"}
                            </td>
                            <td className="px-5 py-3.5">{s.has_text ? <Check className="size-4 text-success" /> : <span className="text-[#aeaeb2]">—</span>}</td>
                            <td className="px-5 py-3.5">{s.has_file ? <Check className="size-4 text-success" /> : <span className="text-[#aeaeb2]">—</span>}</td>
                            <td className="px-5 py-3.5">{s.has_repo ? <Check className="size-4 text-success" /> : <span className="text-[#aeaeb2]">—</span>}</td>
                            <td className="px-5 py-3.5">
                              <span className="text-xs text-[#6e6e73] bg-[#f5f5f7] rounded-full px-2.5 py-1">received</span>
                            </td>
                          </tr>
                        ))
                      : Array.from({ length: subCount }).map((_, i) => (
                          <tr key={i} className="border-b border-[#e8e8ed] last:border-0">
                            <td className="px-5 py-3.5 text-sm text-[#6e6e73]">{i + 1}</td>
                            <td className="px-5 py-3.5 text-sm text-[#aeaeb2]">—</td>
                            <td className="px-5 py-3.5 text-[#aeaeb2]">—</td>
                            <td className="px-5 py-3.5 text-[#aeaeb2]">—</td>
                            <td className="px-5 py-3.5 text-[#aeaeb2]">—</td>
                            <td className="px-5 py-3.5">
                              <span className="text-xs text-[#6e6e73] bg-[#f5f5f7] rounded-full px-2.5 py-1">received</span>
                            </td>
                          </tr>
                        ))
                  }
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── DEALS (procurement) ── */}
        {tab === "deals" && isProcurement && (
          <div className="space-y-4">
            {procResults.length === 0 ? (
              <div className="text-center py-24">
                <p className="text-[#6e6e73] text-base">No evaluated datasets yet.</p>
                <p className="text-sm text-[#aeaeb2] mt-2">Results appear here automatically after the enclave evaluates each seller submission.</p>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck weight="fill" className="size-5 text-success" />
                  <span className="text-sm text-success font-medium">Results signed by enclave</span>
                </div>
                {procResults.map((r) => (
                  <DealCard
                    key={r.submission_id}
                    result={r}
                    onAccept={() => handleAccept(r)}
                    onReject={() => handleReject(r)}
                    onRenegotiate={(val) => handleRenegotiate(r, val)}
                  />
                ))}
              </>
            )}
          </div>
        )}

        {/* ── RESULTS (hackathon) ── */}
        {tab === "results" && !isProcurement && (
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

        {/* ── TRACES ── */}
        {tab === "traces" && (
          <div className="rounded-2xl border border-[#d2d2d7] bg-white p-10 text-center">
            <p className="text-base text-[#6e6e73] mb-2">Trace data will appear here after analysis runs.</p>
            <p className="text-sm text-[#aeaeb2]">
              {isProcurement
                ? "Traces show which evaluation tools ran, output filter pass/fail per constraint, and claim-verification results. No raw dataset content."
                : "Traces show which tools Claude called per submission, output filter pass/fail, and jailbreak test results. They contain no raw submission content."}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Procurement deal card
// ---------------------------------------------------------------------------

function DealCard({
  result,
  onAccept,
  onReject,
  onRenegotiate,
}: {
  result: ProcurementResult
  onAccept: () => void
  onReject: () => void
  onRenegotiate: (revisedBudget: number) => void
}) {
  const [expanded, setExpanded] = React.useState(false)

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-[#f5f5f7]/50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-4">
          <span className="font-mono text-sm text-[#6e6e73]">{result.submission_id}</span>
          <DealStatusBadge state={result.negotiation.state} settlement={result.settlement.state} />
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-[#6e6e73]">Score</p>
            <p className="text-sm font-semibold text-[#1d1d1f]">{(result.partial_score * 100).toFixed(0)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-[#6e6e73]">Proposed</p>
            <p className="text-sm font-semibold text-[#1d1d1f]">${result.proposed_payment.toLocaleString()}</p>
          </div>
          <CaretDown className={cn("size-4 text-[#6e6e73] transition-transform", expanded && "rotate-180")} />
        </div>
      </div>

      {/* Expanded deal detail */}
      {expanded && (
        <div className="border-t border-[#e8e8ed] px-6 py-6 space-y-4 bg-[#f5f5f7]/30">
          <ProcurementScorecard
            partialScore={result.partial_score}
            proposedPayment={result.proposed_payment}
            role="buyer"
          />
          <HardConstraintsCard constraints={result.hard_constraints} />
          <MilestoneBreakdown milestones={result.milestones} />

          {/* Claim results */}
          {Object.keys(result.claim_results).length > 0 && (
            <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
              <p className="text-sm font-semibold text-[#1d1d1f] mb-4">Claim Verification</p>
              <div className="space-y-2">
                {Object.entries(result.claim_results).map(([claim, passed]) => (
                  <div key={claim} className="flex items-center gap-2.5 text-sm">
                    <span className={cn("size-4 rounded-full flex items-center justify-center text-[10px] font-bold", passed ? "bg-success/10 text-success" : "bg-red-50 text-red-500")}>
                      {passed ? "✓" : "✗"}
                    </span>
                    <span className="text-[#1d1d1f]">{claim}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <NegotiationPanel
            negotiation={result.negotiation}
            role="buyer"
            onAccept={onAccept}
            onReject={onReject}
            onRenegotiate={onRenegotiate}
          />

          {result.release_token && <ReleaseTokenCard token={result.release_token} />}

          {result.enclave_signature && (
            <EnclaveSigBadge
              signature={result.enclave_signature}
              verifyUrl="https://cloud-api.phala.network/api/v1/attestations/verify"
            />
          )}
        </div>
      )}
    </div>
  )
}

function DealStatusBadge({
  state,
  settlement,
}: {
  state: string
  settlement: string
}) {
  if (settlement === "authorized")
    return <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-success/10 text-success">Settled</span>
  if (state === "accepted")
    return <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-success/10 text-success">Accepted</span>
  if (state === "rejected")
    return <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-red-50 text-red-500">Rejected</span>
  if (["requested_by_buyer", "requested_by_seller", "awaiting_counterparty", "renegotiation_submitted"].includes(state))
    return <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-[#ff9f0a]/10 text-[#ff9f0a]">Renegotiating</span>
  return <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary/10 text-primary">Pending decision</span>
}

// ---------------------------------------------------------------------------
// Hackathon results table (unchanged)
// ---------------------------------------------------------------------------

function ResultsTable({ results, display }: { results: NoveltyResult[]; display: DisplayMap }) {
  const colFields = Object.entries(display).filter(([, h]) => h.type !== "score_table")
  const colCount = 1 + colFields.length

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#e8e8ed] bg-[#f5f5f7]">
            <th className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">Submission ID</th>
            {colFields.map(([key, hint]) => (
              <th key={key} className="text-left text-xs font-semibold text-[#6e6e73] uppercase tracking-wider px-5 py-3">{hint.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <HackathonResultRow key={r.submission_id} result={r} colFields={colFields} colCount={colCount} display={display} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HackathonResultRow({
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
