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
} from "@phosphor-icons/react"
import { AttestationWidget } from "@/components/attestation-widget"
import { EnclaveSigBadge } from "@/components/enclave-sig-badge"
import { api } from "@/lib/api"
import type { NoveltyResult, SubmitResponse } from "@/lib/types"
import { cn } from "@workspace/ui/lib/utils"
import { Suspense } from "react"


type PageState = "login" | "attest" | "form" | "pending" | "results"

function ParticipantContent({ id }: { id: string }) {
  const [pageState, setPageState] = React.useState<PageState>("login")
  const [userToken, setUserToken] = React.useState("")

  // --- OTP auth state ---
  const [email, setEmail] = React.useState("")
  const [otpCode, setOtpCode] = React.useState("")
  const [otpSent, setOtpSent] = React.useState(false)
  const [authLoading, setAuthLoading] = React.useState(false)
  const [authError, setAuthError] = React.useState("")

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
      setUserToken(user_token)
      setPageState("attest")
    } catch {
      setAuthError("Invalid or expired OTP. Try again.")
    }
    setAuthLoading(false)
  }
  const [ideaText, setIdeaText] = React.useState("")
  const [repoUrl, setRepoUrl] = React.useState("")
  const [repoSummary, setRepoSummary] = React.useState<string | null>(null)
  const [repoLoading, setRepoLoading] = React.useState(false)
  const [githubConnected, setGithubConnected] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [submitResponse, setSubmitResponse] = React.useState<SubmitResponse | null>(null)
  const [result, setResult] = React.useState<NoveltyResult | null>(null)
  const [submissionId] = React.useState(() => `sub_${Math.random().toString(36).slice(2, 9)}`)

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
      // Failed silently
    }
    setRepoLoading(false)
  }

  async function handleSubmit() {
    if (!ideaText.trim() || !userToken) return
    setSubmitting(true)
    const res = await api.submit(userToken, {
      submission_id: submissionId,
      idea_text: ideaText,
      repo_summary: repoSummary ?? "",
      deck_text: "",
    })
    setSubmitResponse(res)
    setSubmitting(false)
    setPageState("pending")
  }

  const canSubmit = ideaText.trim().length > 20 && !submitting

  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-[680px] px-6 py-16">
        {/* Instance header */}
        <div className="mb-12 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-success/30 bg-success/10 px-3.5 py-1.5 text-sm text-success mb-5">
            <span className="size-1.5 rounded-full bg-success animate-pulse" />
            Accepting submissions
          </div>
          <h1 className="text-3xl font-bold tracking-apple-tight text-[#1d1d1f] mb-3">
            Hackathon Novelty Scoring
          </h1>
          <p className="text-base text-[#6e6e73]">
            Submit your idea for anonymous novelty scoring. Your data stays inside the enclave.
          </p>
        </div>

        {/* Progress steps */}
        <div className="flex items-center gap-2 mb-12 justify-center">
          {(["Login", "Verify", "Submit", "Wait", "Results"] as const).map((label, i) => {
            const stateOrder: PageState[] = ["login", "attest", "form", "pending", "results"]
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
                {i < 4 && <ArrowRight className="size-3 text-[#d2d2d7] shrink-0" />}
              </React.Fragment>
            )
          })}
        </div>

        {/* Step 0: Login (Supabase OTP) */}
        {pageState === "login" && (
          <div className="space-y-5 max-w-sm mx-auto">
            {!otpSent ? (
              <>
                <div>
                  <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">Your email address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendOtp()}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                    disabled={authLoading}
                  />
                </div>
                {authError && <p className="text-sm text-red-500">{authError}</p>}
                <button
                  onClick={handleSendOtp}
                  disabled={!email.trim() || authLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-full bg-primary py-3 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {authLoading ? <CircleNotch className="size-4 animate-spin" /> : "Send one-time code"}
                </button>
                <p className="text-xs text-[#aeaeb2] text-center">
                  We'll email you a 6-digit code. No password needed.
                </p>
              </>
            ) : (
              <>
                <p className="text-sm text-[#6e6e73] text-center">
                  Code sent to <span className="font-medium text-[#1d1d1f]">{email}</span>
                </p>
                <div>
                  <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">Enter 6-digit code</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    onKeyDown={(e) => e.key === "Enter" && handleVerifyOtp()}
                    placeholder="123456"
                    className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-mono text-center tracking-widest text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                    disabled={authLoading}
                  />
                </div>
                {authError && <p className="text-sm text-red-500">{authError}</p>}
                <button
                  onClick={handleVerifyOtp}
                  disabled={otpCode.length !== 6 || authLoading}
                  className="w-full flex items-center justify-center gap-2 rounded-full bg-primary py-3 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {authLoading ? <CircleNotch className="size-4 animate-spin" /> : "Verify & continue"}
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

        {/* Step 1: Attestation */}
        {pageState === "attest" && (
          <div className="space-y-6">
            <AttestationWidget onVerified={() => setPageState("form")} />
            <p className="text-sm text-[#aeaeb2] text-center">
              The submission form unlocks after enclave verification.
            </p>
          </div>
        )}

        {/* Step 2: Submission form */}
        {pageState === "form" && (
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-3">
              <Check weight="bold" className="size-4" /> Enclave verified
            </div>

            {/* Idea text */}
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

            {/* GitHub repo */}
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
                      <span>Connected: your-org/your-repo</span>
                    </div>
                    <button
                      onClick={() => setGithubConnected(false)}
                      className="text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
                    >
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
                <p className="text-xs text-[#aeaeb2] mt-1.5">
                  Authorizes the enclave&apos;s GitHub App to fetch your repo. The app runs inside the TEE.
                </p>
              </div>
            </div>

            {/* Pitch deck */}
            <div>
              <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">
                Pitch deck (optional)
              </label>
              <div className="rounded-xl border border-dashed border-[#d2d2d7] bg-[#f5f5f7] px-4 py-10 text-center hover:border-primary/30 transition-colors cursor-pointer">
                <FilePdf className="size-8 text-[#aeaeb2] mx-auto mb-2" />
                <p className="text-sm text-[#6e6e73]">Drag & drop PDF or click to upload</p>
                <p className="text-xs text-[#aeaeb2] mt-1">Sent directly to the enclave over TLS</p>
              </div>
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
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

        {/* Step 3: Pending */}
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

        {/* Step 4: Results */}
        {pageState === "results" && result && (
          <div className="space-y-6">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-3">
              <Check weight="bold" className="size-4" /> Analysis complete
            </div>

            {/* Novelty score */}
            <div className="rounded-2xl border border-[#d2d2d7] bg-white p-10 text-center">
              <p className="text-sm text-[#6e6e73] mb-4">Novelty Score</p>
              <div className="relative inline-flex items-center justify-center mb-4">
                <svg className="size-32 -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="#f5f5f7" strokeWidth="6" />
                  <circle
                    cx="50" cy="50" r="42" fill="none"
                    stroke="#6e3ff3" strokeWidth="6"
                    strokeDasharray={`${result.novelty_score * 264} 264`}
                    strokeLinecap="round"
                  />
                </svg>
                <span className="absolute text-4xl font-bold text-[#1d1d1f] tracking-apple-tight">
                  {(result.novelty_score * 100).toFixed(0)}
                </span>
              </div>
              <p className="text-base text-[#6e6e73]">
                Top {100 - result.percentile}% of submissions
              </p>
            </div>

            {/* Percentile + cluster */}
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-2xl border border-[#d2d2d7] bg-white p-5 text-center">
                <p className="text-xs text-[#6e6e73] mb-1.5">Percentile</p>
                <p className="text-3xl font-bold text-[#1d1d1f] tracking-apple">{result.percentile}<span className="text-sm text-[#aeaeb2]">th</span></p>
              </div>
              <div className="rounded-2xl border border-[#d2d2d7] bg-white p-5 text-center">
                <p className="text-xs text-[#6e6e73] mb-1.5">Cluster</p>
                <span className="inline-block mt-1.5 text-sm bg-primary/10 text-primary font-medium rounded-full px-3 py-1">
                  {result.cluster}
                </span>
              </div>
            </div>

            {/* Criteria breakdown */}
            <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
              <p className="text-sm font-semibold text-[#1d1d1f] tracking-apple mb-5">Criteria breakdown</p>
              <div className="space-y-4">
                {Object.entries(result.criteria_scores).map(([k, v]) => (
                  <div key={k}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-[#1d1d1f] capitalize">{k}</span>
                      <span className="text-[#6e6e73] font-mono">{v}/10</span>
                    </div>
                    <div className="h-2 rounded-full bg-[#f5f5f7] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${(v / 10) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Signature */}
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
