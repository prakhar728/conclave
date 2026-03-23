"use client"

import * as React from "react"
import { use } from "react"
import {
  Lock,
  Check,
  GithubLogo,
  FilePdf,
  ArrowRight,
  CircleNotch,
  ShieldCheck,
} from "@phosphor-icons/react"
import { AttestationWidget } from "@/components/attestation-widget"
import { EnclaveSigBadge } from "@/components/enclave-sig-badge"
import { ResultDetail } from "@/components/result-renderer"
import { DatasetUploadCard } from "@/components/dataset-upload-card"
import { ProcurementScorecard } from "@/components/procurement-scorecard"
import { HardConstraintsCard } from "@/components/hard-constraints-card"
import { MilestoneBreakdown } from "@/components/milestone-breakdown"
import { NegotiationPanel } from "@/components/negotiation-panel"
import { ReleaseTokenCard } from "@/components/release-token-card"
import { api, ApiError } from "@/lib/api"
import type {
  DisplayMap,
  NoveltyResult,
  ProcurementResult,
  NegotiationStatus,
  SellerClaim,
  SubmitResponse,
} from "@/lib/types"
import { cn } from "@workspace/ui/lib/utils"
import { Suspense } from "react"

type PageState =
  | "login"
  | "attest"
  | "form"
  | "pending"
  | "results"
  // Procurement-specific
  | "uploading"
  | "pending_evaluation"
  | "evaluation_complete"
  | "awaiting_negotiation"
  | "released"
  | "rejected"

const TOKEN_CACHE_KEY = (instanceId: string) => `conclave_user_token_${instanceId}`

function ParticipantContent({ id }: { id: string }) {
  const [pageState, setPageState] = React.useState<PageState>("login")
  const [userToken, setUserToken] = React.useState("")
  const [instanceMissing, setInstanceMissing] = React.useState(false)
  const [isProcurement, setIsProcurement] = React.useState(false)
  const [toast, setToast] = React.useState<string | null>(null)

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  function handleAuthError(err: unknown) {
    if (err instanceof ApiError && err.status === 403) {
      localStorage.removeItem(TOKEN_CACHE_KEY(id))
      setUserToken("")
      setPageState("login")
      showToast("Your session has expired. Please log in again.")
    }
  }

  // --- OTP auth state ---
  const [email, setEmail] = React.useState("")
  const [otpCode, setOtpCode] = React.useState("")
  const [otpSent, setOtpSent] = React.useState(false)
  const [authLoading, setAuthLoading] = React.useState(false)
  const [authError, setAuthError] = React.useState("")

  async function checkPriorSubmission(token: string, procurementMode: boolean) {
    try {
      const { submission_ids } = await api.getMySubmissions(token)
      if (submission_ids.length === 0) {
        setPageState("attest")
        return
      }
      const sid = submission_ids[0]!
      setSubmissionId(sid)
      if (procurementMode) {
        try {
          const r = await api.getProcurementResult(token, sid)
          setProcResult(r)
          setPageState("evaluation_complete")
        } catch {
          setPageState("pending_evaluation")
        }
      } else {
        try {
          const r = await api.getOwnResult(token, sid)
          setResult(r)
          setPageState("results")
        } catch {
          const inst = await api.checkInstance(id)
          setSubmitResponse({
            submission_id: sid,
            status: "received_pending",
            submissions_count: inst.submissions,
            threshold: inst.threshold,
          })
          setPageState("pending")
        }
      }
    } catch (err) {
      handleAuthError(err)
      if (!(err instanceof ApiError && err.status === 403)) {
        setPageState("attest")
      }
    }
  }

  React.useEffect(() => {
    api.checkInstance(id).then((inst) => {
      const proc = inst.skill_name === "confidential_data_procurement"
      setIsProcurement(proc)
      if (!proc && inst.skill_name) {
        api.getSkill(inst.skill_name).then((card) => {
          if (card.user_display) setSkillDisplay(card.user_display)
        }).catch(() => {})
      }
    }).catch(() => setInstanceMissing(true))

    const cached = localStorage.getItem(TOKEN_CACHE_KEY(id))
    if (cached) {
      setUserToken(cached)
      // Detect procurement before checking prior submissions
      api.checkInstance(id).then((inst) => {
        const proc = inst.skill_name === "confidential_data_procurement"
        checkPriorSubmission(cached, proc)
      }).catch(() => {})
      return
    }
    import("@/lib/supabase").then(({ supabase }) => {
      supabase.auth.getSession().then(async ({ data }) => {
        const access_token = data.session?.access_token
        if (!access_token) return
        setAuthLoading(true)
        try {
          const { user_token } = await api.verifyToken(access_token, id)
          saveToken(user_token)
          const inst = await api.checkInstance(id)
          const proc = inst.skill_name === "confidential_data_procurement"
          await checkPriorSubmission(user_token, proc)
        } catch (err) {
          handleAuthError(err)
        }
        setAuthLoading(false)
      })
    })
  }, [id])

  function saveToken(token: string) {
    setUserToken(token)
    localStorage.setItem(TOKEN_CACHE_KEY(id), token)
  }

  async function handleSendOtp() {
    if (!email.trim()) return
    setAuthLoading(true)
    setAuthError("")
    try {
      await api.sendOtp(email.trim(), id)
      setOtpSent(true)
    } catch {
      setAuthError("Failed to send OTP. Check the email and try again.")
    }
    setAuthLoading(false)
  }

  async function handleVerifyOtp() {
    if (!otpCode.trim()) return
    setAuthLoading(true)
    setAuthError("")
    try {
      const { user_token } = await api.verifyOtp(email.trim(), otpCode.trim(), id)
      saveToken(user_token)
      setPageState("attest")
    } catch {
      setAuthError("Invalid or expired OTP. Try again.")
    }
    setAuthLoading(false)
  }

  const [skillDisplay, setSkillDisplay] = React.useState<DisplayMap>({})

  // Hackathon form state
  const [ideaText, setIdeaText] = React.useState("")
  const [repoUrl, setRepoUrl] = React.useState("")
  const [repoSummary, setRepoSummary] = React.useState<string | null>(null)
  const [repoLoading, setRepoLoading] = React.useState(false)
  const [githubConnected, setGithubConnected] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [submitResponse, setSubmitResponse] = React.useState<SubmitResponse | null>(null)
  const [result, setResult] = React.useState<NoveltyResult | null>(null)
  const [submissionId, setSubmissionId] = React.useState("")

  // Procurement seller state
  const [datasetName, setDatasetName] = React.useState("")
  const [datasetReference, setDatasetReference] = React.useState("")
  const [datasetFile, setDatasetFile] = React.useState<File | null>(null)
  const [reservePrice, setReservePrice] = React.useState("")
  const [sellerClaims, setSellerClaims] = React.useState<SellerClaim[]>([])
  const [sellerNote, setSellerNote] = React.useState("")
  const [procResult, setProcResult] = React.useState<ProcurementResult | null>(null)

  // Procurement polling
  React.useEffect(() => {
    if (pageState !== "pending_evaluation" || !userToken || !submissionId) return
    const interval = setInterval(async () => {
      try {
        const r = await api.getProcurementResult(userToken, submissionId)
        setProcResult(r)
        setPageState("evaluation_complete")
        clearInterval(interval)
      } catch {
        // Not ready yet
      }
    }, 8000)
    return () => clearInterval(interval)
  }, [pageState, userToken, submissionId])

  // Hackathon polling
  React.useEffect(() => {
    if (pageState !== "pending" || !submitResponse || !userToken) return
    const interval = setInterval(async () => {
      try {
        const r = await api.getOwnResult(userToken, submissionId)
        setResult(r)
        setPageState("results")
        clearInterval(interval)
      } catch {
        // Not ready yet
      }
    }, 8000)
    return () => clearInterval(interval)
  }, [pageState, submitResponse, userToken, submissionId])

  async function fetchRepo() {
    if (!repoUrl || !userToken) return
    setRepoLoading(true)
    try {
      const r = await api.fetchRepo(userToken, repoUrl)
      setRepoSummary(r.repo_summary)
    } catch {
      // ignore
    }
    setRepoLoading(false)
  }

  async function handleHackathonSubmit() {
    if (!ideaText.trim() || !userToken) return
    setSubmitting(true)
    const res = await api.submit(userToken, {
      idea_text: ideaText,
      repo_summary: repoSummary ?? "",
      deck_text: "",
    })
    setSubmissionId(res.submission_id)
    setSubmitResponse(res)
    setSubmitting(false)
    setPageState("pending")
  }

  async function handleDatasetSubmit() {
    if (!datasetName.trim() || !reservePrice || !userToken || !datasetFile) return
    setPageState("uploading")
    try {
      const res = await api.submitDataset(
        userToken,
        {
          dataset_name: datasetName,
          dataset_reference: datasetReference || undefined,
          seller_claims: sellerClaims,
          metadata: {},
          reserve_price: parseFloat(reservePrice.replace(/,/g, "")),
          note: sellerNote || undefined,
        },
        datasetFile,
      )
      setSubmissionId(res.submission_id)
      setPageState("pending_evaluation")
    } catch (err) {
      handleAuthError(err)
      if (!(err instanceof ApiError && err.status === 403)) {
        showToast("Upload failed. Please check your file and try again.")
        setPageState("form")
      }
    }
  }

  async function handleAccept() {
    if (!procResult || !userToken) return
    await api.acceptDeal(userToken, procResult.submission_id)
    const updated = await api.getProcurementResult(userToken, procResult.submission_id)
    setProcResult(updated)
    setPageState("released")
  }

  async function handleReject() {
    if (!procResult || !userToken) return
    await api.rejectDeal(userToken, procResult.submission_id)
    const updated = await api.getProcurementResult(userToken, procResult.submission_id)
    setProcResult(updated)
    setPageState("rejected")
  }

  async function handleRenegotiate(revisedValue: number) {
    if (!procResult || !userToken) return
    await api.submitRenegotiation(userToken, procResult.submission_id, revisedValue)
    const updated = await api.getProcurementResult(userToken, procResult.submission_id)
    setProcResult(updated)
    setPageState("awaiting_negotiation")
  }

  async function handleLogout() {
    const { supabase } = await import("@/lib/supabase")
    await supabase.auth.signOut()
    localStorage.removeItem(TOKEN_CACHE_KEY(id))
    setUserToken("")
    setPageState("login")
    setOtpSent(false)
    setOtpCode("")
    setEmail("")
  }

  const canHackathonSubmit = ideaText.trim().length > 20 && !submitting
  const canDatasetSubmit =
    datasetName.trim().length > 0 &&
    reservePrice.trim().length > 0 &&
    !!datasetFile &&
    pageState === "form"

  if (instanceMissing) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-6">
        <div className="max-w-sm w-full text-center space-y-4">
          <div className="inline-flex items-center justify-center size-14 rounded-2xl bg-red-50 border border-red-100 mb-2">
            <span className="text-2xl">⚠️</span>
          </div>
          <h2 className="text-xl font-bold text-[#1d1d1f] tracking-apple-tight">Instance not found</h2>
          <p className="text-sm text-[#6e6e73]">
            This submission link is invalid or has expired. Ask the organizer for a fresh link.
          </p>
        </div>
      </div>
    )
  }

  const procurementSteps = [
    "Login", "Verify", "Submit", "Evaluating", "Result",
  ] as const
  const procurementStateOrder: PageState[] = [
    "login", "attest", "form", "pending_evaluation", "evaluation_complete",
  ]

  const hackathonSteps = ["Login", "Verify", "Submit", "Wait", "Results"] as const
  const hackathonStateOrder: PageState[] = ["login", "attest", "form", "pending", "results"]

  const steps = isProcurement ? procurementSteps : hackathonSteps
  const stateOrder = isProcurement ? procurementStateOrder : hackathonStateOrder

  return (
    <div className="min-h-screen bg-white">
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 rounded-2xl border border-[#d2d2d7] bg-white px-5 py-3 shadow-lg text-sm text-[#1d1d1f] max-w-sm w-[calc(100%-3rem)]">
          <span className="size-2 rounded-full bg-[#ff9f0a] shrink-0" />
          {toast}
        </div>
      )}

      {pageState !== "login" && (
        <div className="border-b border-[#e8e8ed] px-6 py-3 flex justify-end max-w-[680px] mx-auto">
          <button
            onClick={handleLogout}
            className="text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
          >
            Log out
          </button>
        </div>
      )}

      <div className="mx-auto max-w-[680px] px-6 py-16">
        {/* Header */}
        <div className="mb-12 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-success/30 bg-success/10 px-3.5 py-1.5 text-sm text-success mb-5">
            <span className="size-1.5 rounded-full bg-success animate-pulse" />
            {isProcurement ? "Accepting datasets" : "Accepting submissions"}
          </div>
          <h1 className="text-3xl font-bold tracking-apple-tight text-[#1d1d1f] mb-3">
            {isProcurement ? "Confidential Data Procurement" : "Hackathon Novelty Scoring"}
          </h1>
          <p className="text-base text-[#6e6e73]">
            {isProcurement
              ? "Submit your dataset for confidential evaluation. Raw rows never leave the enclave before agreement."
              : "Submit your idea for anonymous novelty scoring. Your data stays inside the enclave."}
          </p>
        </div>

        {/* Progress steps — hide for terminal procurement states */}
        {!["released", "rejected", "awaiting_negotiation"].includes(pageState) && (
          <div className="flex items-center gap-2 mb-12 justify-center flex-wrap">
            {steps.map((label, i) => {
              const done = stateOrder.indexOf(pageState) > i
              const active = stateOrder.indexOf(pageState) === i
              return (
                <React.Fragment key={label}>
                  <div className={cn(
                    "flex items-center gap-1.5 text-sm",
                    active && "text-primary font-medium",
                    done && "text-success",
                    !active && !done && "text-[#aeaeb2]",
                  )}>
                    <span className={cn(
                      "size-6 rounded-full flex items-center justify-center text-xs font-medium border",
                      active && "bg-primary/10 border-primary/40 text-primary",
                      done && "bg-success/10 border-success/40 text-success",
                      !active && !done && "bg-[#f5f5f7] border-[#d2d2d7] text-[#aeaeb2]",
                    )}>
                      {done ? "✓" : i + 1}
                    </span>
                    {label}
                  </div>
                  {i < steps.length - 1 && <ArrowRight className="size-3 text-[#d2d2d7] shrink-0" />}
                </React.Fragment>
              )
            })}
          </div>
        )}

        {/* ── LOGIN ── */}
        {pageState === "login" && (
          <div className="space-y-4 max-w-sm mx-auto">
            {authLoading ? (
              <div className="flex justify-center py-8">
                <CircleNotch className="size-6 text-primary animate-spin" />
              </div>
            ) : !otpSent ? (
              <>
                <button
                  onClick={async () => {
                    const { supabase } = await import("@/lib/supabase")
                    await supabase.auth.signInWithOAuth({
                      provider: "github",
                      options: { redirectTo: `${window.location.origin}/i/${id}` },
                    })
                  }}
                  className="w-full flex items-center justify-center gap-2.5 rounded-xl border border-[#d2d2d7] bg-white py-3 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] hover:bg-[#f5f5f7] transition-all"
                >
                  <GithubLogo weight="fill" className="size-4" />
                  Continue with GitHub
                </button>
                <button
                  onClick={async () => {
                    const { supabase } = await import("@/lib/supabase")
                    await supabase.auth.signInWithOAuth({
                      provider: "google",
                      options: { redirectTo: `${window.location.origin}/i/${id}` },
                    })
                  }}
                  className="w-full flex items-center justify-center gap-2.5 rounded-xl border border-[#d2d2d7] bg-white py-3 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] hover:bg-[#f5f5f7] transition-all"
                >
                  <svg className="size-4" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                  </svg>
                  Continue with Google
                </button>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-[#e8e8ed]" />
                  <span className="text-xs text-[#aeaeb2]">or</span>
                  <div className="flex-1 h-px bg-[#e8e8ed]" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendOtp()}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                />
                {authError && <p className="text-sm text-red-500">{authError}</p>}
                <button
                  onClick={handleSendOtp}
                  disabled={!email.trim()}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-[#d2d2d7] bg-white py-3 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] hover:bg-[#f5f5f7] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  Send one-time code
                </button>
                <p className="text-xs text-[#aeaeb2] text-center">
                  We&apos;ll email you a 6-digit code. No password needed.
                </p>
              </>
            ) : (
              <>
                <p className="text-sm text-[#6e6e73] text-center">
                  Code sent to <span className="font-medium text-[#1d1d1f]">{email}</span>
                </p>
                <input
                  type="text"
                  inputMode="numeric"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  onKeyDown={(e) => e.key === "Enter" && handleVerifyOtp()}
                  placeholder="123456"
                  className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-mono text-center tracking-widest text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                />
                {authError && <p className="text-sm text-red-500">{authError}</p>}
                <button
                  onClick={handleVerifyOtp}
                  disabled={otpCode.length !== 6}
                  className="w-full flex items-center justify-center gap-2 rounded-full bg-primary py-3 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  Verify & continue
                </button>
                <button
                  onClick={() => { setOtpSent(false); setOtpCode(""); setAuthError("") }}
                  className="w-full text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
                >
                  Use a different email
                </button>
              </>
            )}
          </div>
        )}

        {/* ── ATTEST ── */}
        {pageState === "attest" && (
          <div className="space-y-6">
            <AttestationWidget onVerified={() => setPageState("form")} />
            <p className="text-sm text-[#aeaeb2] text-center">
              The submission form unlocks after enclave verification.
            </p>
          </div>
        )}

        {/* ── FORM — Hackathon ── */}
        {pageState === "form" && !isProcurement && (
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-3">
              <Check weight="bold" className="size-4" /> Enclave verified
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-[#1d1d1f]">Idea description *</label>
                {ideaText.length > 0 && (
                  <span className="flex items-center gap-1.5 text-sm text-success">
                    <Lock weight="fill" className="size-3" /> Secured
                  </span>
                )}
              </div>
              <textarea
                value={ideaText}
                onChange={(e) => setIdeaText(e.target.value)}
                placeholder="Describe your idea in detail — what problem it solves, how it works, why it's novel…"
                rows={6}
                className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-3 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all resize-none leading-relaxed"
              />
              <p className="text-xs text-[#aeaeb2] mt-1.5">
                Sent directly to the enclave over TLS. Not stored anywhere outside.
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">GitHub repo</label>
              <div className="mb-3">
                <p className="text-xs text-[#6e6e73] mb-1.5">Public repo URL</p>
                <div className="flex gap-2">
                  <input
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    onBlur={fetchRepo}
                    placeholder="https://github.com/owner/repo"
                    className="flex-1 rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-mono text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                    disabled={githubConnected}
                  />
                  {repoLoading && <CircleNotch className="size-4 text-[#6e6e73] animate-spin mt-2.5" />}
                  {repoSummary && !repoLoading && <Check className="size-4 text-success mt-2.5" />}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-[#e8e8ed]" />
                <span className="text-xs text-[#aeaeb2]">or</span>
                <div className="flex-1 h-px bg-[#e8e8ed]" />
              </div>
              <div className="mt-3">
                {githubConnected ? (
                  <div className="flex items-center justify-between rounded-xl border border-success/30 bg-success/5 px-4 py-3">
                    <div className="flex items-center gap-2 text-sm text-success">
                      <GithubLogo weight="fill" className="size-4" />
                      <span>Connected</span>
                    </div>
                    <button onClick={() => setGithubConnected(false)} className="text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors">
                      Disconnect
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setGithubConnected(true)}
                    className="w-full flex items-center justify-center gap-2 rounded-xl border border-[#d2d2d7] bg-white py-2.5 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] transition-all"
                  >
                    <GithubLogo weight="fill" className="size-4" />
                    Connect private GitHub repo
                  </button>
                )}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">Pitch deck (optional)</label>
              <div className="rounded-xl border border-dashed border-[#d2d2d7] bg-[#f5f5f7] px-4 py-10 text-center hover:border-primary/30 transition-colors cursor-pointer">
                <FilePdf className="size-8 text-[#aeaeb2] mx-auto mb-2" />
                <p className="text-sm text-[#6e6e73]">Drag & drop PDF or click to upload</p>
                <p className="text-xs text-[#aeaeb2] mt-1">Sent directly to the enclave over TLS</p>
              </div>
            </div>
            <button
              onClick={handleHackathonSubmit}
              disabled={!canHackathonSubmit}
              className="w-full flex items-center justify-center gap-2 rounded-full bg-primary py-3.5 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {submitting ? (
                <><CircleNotch className="size-4 animate-spin" /> Submitting…</>
              ) : (
                <><Lock weight="fill" className="size-4" /> Submit to Enclave</>
              )}
            </button>
          </div>
        )}

        {/* ── FORM — Procurement seller ── */}
        {pageState === "form" && isProcurement && (
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-3">
              <Check weight="bold" className="size-4" /> Enclave verified
            </div>
            <DatasetUploadCard
              datasetName={datasetName}
              onDatasetNameChange={setDatasetName}
              datasetReference={datasetReference}
              onDatasetReferenceChange={setDatasetReference}
              reservePrice={reservePrice}
              onReservePriceChange={setReservePrice}
              claims={sellerClaims}
              onClaimsChange={setSellerClaims}
              note={sellerNote}
              onNoteChange={setSellerNote}
              file={datasetFile}
              onFileChange={setDatasetFile}
            />
            <button
              onClick={handleDatasetSubmit}
              disabled={!canDatasetSubmit}
              className="w-full flex items-center justify-center gap-2 rounded-full bg-primary py-3.5 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Lock weight="fill" className="size-4" /> Submit Dataset to Enclave
            </button>
          </div>
        )}

        {/* ── UPLOADING ── */}
        {pageState === "uploading" && (
          <div className="text-center py-12">
            <CircleNotch className="size-10 text-primary animate-spin mx-auto mb-4" />
            <p className="text-base font-medium text-[#1d1d1f] mb-2">Uploading to enclave…</p>
            <p className="text-sm text-[#6e6e73]">Transferring dataset over TLS directly into the TEE.</p>
          </div>
        )}

        {/* ── PENDING EVALUATION ── */}
        {pageState === "pending_evaluation" && (
          <div className="text-center py-8">
            <div className="space-y-4 mb-10 text-left max-w-xs mx-auto">
              <TimelineItem done label="Dataset submitted" detail={new Date().toLocaleString()} />
              <TimelineItem active label="Enclave evaluating dataset" />
              <TimelineItem label="Claim verification" />
              <TimelineItem label="Evaluation complete" />
            </div>
            <div className="rounded-2xl border border-[#d2d2d7] bg-[#f5f5f7] p-5 text-left max-w-xs mx-auto mb-6">
              <p className="text-xs text-[#6e6e73] mb-1.5">Submission ID</p>
              <p className="font-mono text-sm text-[#1d1d1f]">{submissionId}</p>
            </div>
            <div className="rounded-xl border border-success/30 bg-success/5 px-4 py-3 text-sm text-success max-w-xs mx-auto">
              <ShieldCheck weight="fill" className="size-4 inline mr-1.5" />
              Raw rows are never exposed. Only aggregate metrics leave the enclave.
            </div>
          </div>
        )}

        {/* ── PENDING (hackathon) ── */}
        {pageState === "pending" && (
          <div className="text-center py-8">
            <div className="space-y-4 mb-10 text-left max-w-xs mx-auto">
              <TimelineItem done label="Submitted" detail={new Date().toLocaleString()} />
              <TimelineItem active label="Waiting for analysis to run" />
              <TimelineItem label="Analysis running" />
              <TimelineItem label="Results ready" />
            </div>
            <div className="rounded-2xl border border-[#d2d2d7] bg-[#f5f5f7] p-5 text-left max-w-xs mx-auto">
              <p className="text-xs text-[#6e6e73] mb-1.5">Your submission ID</p>
              <p className="font-mono text-sm text-[#1d1d1f]">{submissionId}</p>
            </div>
            <p className="text-sm text-[#6e6e73] mt-8">
              Your submission is inside the enclave. Not even we can read it.
            </p>
            <p className="text-xs text-[#aeaeb2] mt-2">
              {submitResponse?.submissions_count ?? 0} of {submitResponse?.threshold ?? 5} submissions received.
            </p>
          </div>
        )}

        {/* ── RESULTS (hackathon) ── */}
        {pageState === "results" && result && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-3">
              <Check weight="bold" className="size-4" /> Analysis complete
            </div>
            <ResultDetail result={result as unknown as Record<string, unknown>} display={skillDisplay} />
            {result.enclave_signature && (
              <div>
                <p className="text-xs text-[#6e6e73] mb-2.5">Enclave signature</p>
                <EnclaveSigBadge
                  signature={result.enclave_signature}
                  verifyUrl="https://cloud-api.phala.network/api/v1/attestations/verify"
                  className="w-full"
                />
              </div>
            )}
          </div>
        )}

        {/* ── EVALUATION COMPLETE (procurement seller) ── */}
        {pageState === "evaluation_complete" && procResult && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-1">
              <Check weight="bold" className="size-4" /> Evaluation complete
            </div>
            <ProcurementScorecard
              partialScore={procResult.partial_score}
              proposedPayment={procResult.proposed_payment}
              reservePrice={parseFloat(reservePrice.replace(/,/g, "")) || undefined}
              role="seller"
            />
            <HardConstraintsCard constraints={procResult.hard_constraints} />
            <MilestoneBreakdown milestones={procResult.milestones} />
            {/* Claim results */}
            {Object.keys(procResult.claim_results).length > 0 && (
              <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
                <p className="text-sm font-semibold text-[#1d1d1f] mb-4">Claim Verification</p>
                <div className="space-y-2">
                  {Object.entries(procResult.claim_results).map(([claim, passed]) => (
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
              negotiation={procResult.negotiation}
              role="seller"
              reservePrice={parseFloat(reservePrice.replace(/,/g, "")) || undefined}
              onAccept={handleAccept}
              onReject={handleReject}
              onRenegotiate={handleRenegotiate}
            />
            {procResult.enclave_signature && (
              <EnclaveSigBadge
                signature={procResult.enclave_signature}
                verifyUrl="https://cloud-api.phala.network/api/v1/attestations/verify"
                className="w-full"
              />
            )}
          </div>
        )}

        {/* ── AWAITING NEGOTIATION ── */}
        {pageState === "awaiting_negotiation" && (
          <div className="text-center py-12 space-y-4">
            <CircleNotch className="size-10 text-[#ff9f0a] animate-spin mx-auto" />
            <p className="text-base font-medium text-[#1d1d1f]">Awaiting buyer response</p>
            <p className="text-sm text-[#6e6e73]">
              Your revised reserve price has been submitted to the enclave. The buyer will be notified.
            </p>
            <div className="rounded-2xl border border-[#d2d2d7] bg-[#f5f5f7] p-5 max-w-xs mx-auto text-left">
              <p className="text-xs text-[#6e6e73] mb-1.5">Submission ID</p>
              <p className="font-mono text-sm text-[#1d1d1f]">{submissionId}</p>
            </div>
          </div>
        )}

        {/* ── RELEASED ── */}
        {pageState === "released" && procResult?.release_token && (
          <div className="space-y-4">
            <div className="text-center mb-6">
              <div className="size-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                <Check weight="bold" className="size-8 text-success" />
              </div>
              <h2 className="text-2xl font-bold text-[#1d1d1f] mb-2">Deal complete</h2>
              <p className="text-[#6e6e73] text-sm">Settlement has been authorized for your dataset.</p>
            </div>
            <div className="rounded-2xl border border-[#d2d2d7] bg-white p-5">
              <p className="text-xs text-[#6e6e73] mb-1">Settlement amount</p>
              <p className="text-3xl font-bold text-[#1d1d1f]">${procResult.proposed_payment.toLocaleString()}</p>
            </div>
            <ReleaseTokenCard token={procResult.release_token} />
          </div>
        )}

        {/* ── REJECTED ── */}
        {pageState === "rejected" && (
          <div className="text-center py-12 space-y-4">
            <div className="size-16 rounded-full bg-red-50 flex items-center justify-center mx-auto">
              <span className="text-3xl">✗</span>
            </div>
            <h2 className="text-2xl font-bold text-[#1d1d1f]">Deal rejected</h2>
            <p className="text-sm text-[#6e6e73]">
              This deal did not proceed. No data was shared outside the enclave.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ParticipantPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <ParticipantContent id={id} />
    </Suspense>
  )
}

function TimelineItem({
  label,
  detail,
  done = false,
  active = false,
}: {
  label: string
  detail?: string
  done?: boolean
  active?: boolean
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={cn(
        "size-6 rounded-full flex items-center justify-center shrink-0 border",
        done && "bg-success/10 border-success/40 text-success",
        active && "bg-[#ff9f0a]/10 border-[#ff9f0a]/40 text-[#ff9f0a] animate-pulse",
        !done && !active && "bg-[#f5f5f7] border-[#d2d2d7] text-[#aeaeb2]",
      )}>
        {done ? (
          <Check weight="bold" className="size-3" />
        ) : active ? (
          <CircleNotch className="size-3 animate-spin" />
        ) : (
          <span className="size-1.5 rounded-full bg-current" />
        )}
      </div>
      <div>
        <p className={cn(
          "text-sm font-medium",
          done && "text-success",
          active && "text-[#ff9f0a]",
          !done && !active && "text-[#aeaeb2]",
        )}>
          {label}
        </p>
        {detail && <p className="text-xs text-[#6e6e73]">{detail}</p>}
      </div>
    </div>
  )
}
