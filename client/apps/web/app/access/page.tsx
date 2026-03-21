"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Lock, ShieldCheck, CircleNotch, ArrowRight } from "@phosphor-icons/react"
import { api, ApiError } from "@/lib/api"
import Link from "next/link"

export default function AccessPage() {
  const router = useRouter()
  const [token, setToken] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState("")

  async function handleAccess() {
    const t = token.trim()
    if (!t) return
    setLoading(true)
    setError("")
    try {
      const { instance_id, role } = await api.resolveToken(t)
      if (role !== "admin") {
        setError("This token doesn't have admin access. Make sure you're using the admin token issued at setup.")
        setLoading(false)
        return
      }
      // Persist token in the same format the dashboard expects
      const existing = localStorage.getItem(`ndai_instance_${instance_id}`)
      const data = existing ? JSON.parse(existing) : {}
      localStorage.setItem(
        `ndai_instance_${instance_id}`,
        JSON.stringify({ ...data, instance_id, admin_token: t }),
      )
      router.push(`/dashboard/${instance_id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Invalid or expired token.")
      } else {
        setError("Could not reach the enclave. Make sure the server is running.")
      }
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f5f7] flex flex-col">
      {/* Nav */}
      <header className="border-b border-[#d2d2d7]/60 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto max-w-[980px] px-6 h-12 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="size-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Lock weight="fill" className="size-3.5 text-primary" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-[#1d1d1f]">NDAI</span>
          </Link>
          <Link href="/setup" className="text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors">
            Create new instance
          </Link>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-md space-y-8">
          {/* Header */}
          <div className="text-center">
            <div className="inline-flex items-center justify-center size-16 rounded-2xl bg-primary/10 mb-6">
              <ShieldCheck weight="fill" className="size-8 text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-[#1d1d1f] mb-3">
              Access your dashboard
            </h1>
            <p className="text-base text-[#6e6e73]">
              Paste the admin token you received when you created the instance.
            </p>
          </div>

          {/* Card */}
          <div className="rounded-2xl border border-[#d2d2d7] bg-white p-8 shadow-sm space-y-4">
            <div>
              <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">Admin token</label>
              <input
                value={token}
                onChange={(e) => { setToken(e.target.value); setError("") }}
                onKeyDown={(e) => e.key === "Enter" && handleAccess()}
                placeholder="adm_…"
                autoFocus
                className="w-full rounded-xl border border-[#d2d2d7] bg-[#f5f5f7] px-4 py-3 text-sm font-mono text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
              />
              {error && (
                <p className="text-sm text-red-500 mt-2">{error}</p>
              )}
            </div>

            <button
              onClick={handleAccess}
              disabled={!token.trim() || loading}
              className="w-full flex items-center justify-center gap-2 rounded-full bg-primary py-3 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <><CircleNotch className="size-4 animate-spin" /> Resolving…</>
              ) : (
                <>Open dashboard <ArrowRight className="size-4" /></>
              )}
            </button>
          </div>

          <p className="text-center text-sm text-[#aeaeb2]">
            Don&apos;t have a token?{" "}
            <Link href="/setup" className="text-primary hover:text-[#5a2fd4] transition-colors">
              Create an instance
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
