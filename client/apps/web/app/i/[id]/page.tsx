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
import { ResultDetail } from "@/components/result-renderer"
import { api, ApiError } from "@/lib/api"
import type { DisplayMap, NoveltyResult, SubmitResponse } from "@/lib/types"
import { cn } from "@workspace/ui/lib/utils"
import { Suspense } from "react"


type PageState = "login" | "attest" | "form" | "pending" | "results"

const TOKEN_CACHE_KEY = (instanceId: string) => `conclave_user_token_${instanceId}`

function ParticipantContent({ id }: { id: string }) {
  const [pageState, setPageState] = React.useState<PageState>("login")
  const [userToken, setUserToken] = React.useState("")
  const [instanceMissing, setInstanceMissing] = React.useState(false)
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

  // After we have a user_token, check if they've already submitted.
  // If yes, restore their submission_id and route to pending/results.
  async function checkPriorSubmission(token: string) {
    try {
      const { submission_ids } = await api.getMySubmissions(token)
      if (submission_ids.length === 0) {
        setPageState("attest")
        return
      }
      const sid = submission_ids[0]!
      setSubmissionId(sid)
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
    } catch (err) {
      handleAuthError(err)
      if (!(err instanceof ApiError && err.status === 403)) {
        setPageState("attest")
      }
    }
  }

  // On mount: verify the instance exists first, fetch skill display hints, then restore session.
  React.useEffect(() => {
    api.checkInstance(id).then((inst) => {
      if (inst.skill_name) {
        api.getSkill(inst.skill_name).then((card) => {
          if (card.user_display) setSkillDisplay(card.user_display)
        }).catch(() => {})
      }
    }).catch(() => setInstanceMissing(true))

    const cached = localStorage.getItem(TOKEN_CACHE_KEY(id))
    if (cached) {
      setUserToken(cached)
      checkPriorSubmission(cached)
      return
    }
    // Check if returning from GitHub/Google OAuth redirect
    import("@/lib/supabase").then(({ supabase }) => {
      supabase.auth.getSession().then(async ({ data }) => {
        const access_token = data.session?.access_token
        if (!access_token) return
        setAuthLoading(true)
        try {
          const { user_token } = await api.verifyToken(access_token, id)
          saveToken(user_token)
          await checkPriorSubmission(user_token)
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

  const [ideaText, setIdeaText] = React.useState("")
  const [repoUrl, setRepoUrl] = React.useState("")
  const [repoSummary, setRepoSummary] = React.useState<string | null>(null)
  const [repoLoading, setRepoLoading] = React.useState(false)
  const [githubConnected, setGithubConnected] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [submitResponse, setSubmitResponse] = React.useState<SubmitResponse | null>(null)
  const [result, setResult] = React.useState<NoveltyResult | null>(null)
  const [submissionId, setSubmissionId] = React.useState("")

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
      idea_text: ideaText,
      repo_summary: repoSummary ?? "",
      deck_text: "",
    })
    setSubmissionId(res.submission_id)
    setSubmitResponse(res)
    setSubmitting(false)
    setPageState("pending")
  }

  const canSubmit = ideaText.trim().length > 20 && !submitting

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

  return (
    <div className="min-h-screen bg-white">
      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 rounded-2xl border border-[#d2d2d7] bg-white px-5 py-3 shadow-lg text-sm text-[#1d1d1f] max-w-sm w-[calc(100%-3rem)]">
          <span className="size-2 rounded-full bg-[#ff9f0a] shrink-0" />
          {toast}
        </div>
      )}

      {/* Top bar with logout */}
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

        {/* Step 0: Login */}
        {pageState === "login" && (
          <div className="space-y-4 max-w-sm mx-auto">
            {authLoading ? (
              <div className="flex justify-center py-8">
                <CircleNotch className="size-6 text-primary animate-spin" />
              </div>
            ) : !otpSent ? (
              <>
                {/* GitHub */}
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

                {/* Google */}
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

                {/* Divider */}
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-[#e8e8ed]" />
                  <span className="text-xs text-[#aeaeb2]">or</span>
                  <div className="flex-1 h-px bg-[#e8e8ed]" />
                </div>

                {/* Email OTP */}
                <div>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendOtp()}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
                  />
                </div>
                {authError && <p className="text-sm text-red-500">{authError}</p>}
                <button
                  onClick={handleSendOtp}
                  disabled={!email.trim()}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-[#d2d2d7] bg-white py-3 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] hover:bg-[#f5f5f7] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  Send one-time code
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
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-success font-medium mb-3">
              <Check weight="bold" className="size-4" /> Analysis complete
            </div>

            <ResultDetail
              result={result as unknown as Record<string, unknown>}
              display={skillDisplay}
            />

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
