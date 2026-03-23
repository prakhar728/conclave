"use client"

import * as React from "react"
import { Key, Copy, Check, DownloadSimple } from "@phosphor-icons/react"
import type { ReleaseToken } from "@/lib/types"

const TEE_URL = process.env.NEXT_PUBLIC_TEE_URL ?? "http://localhost:8000"

export function ReleaseTokenCard({ token }: { token: ReleaseToken }) {
  const [copied, setCopied] = React.useState(false)
  const [downloading, setDownloading] = React.useState(false)

  async function copyToken() {
    await navigator.clipboard.writeText(token.token)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function downloadDataset() {
    setDownloading(true)
    try {
      const res = await fetch(`${TEE_URL}/download/${token.token}`)
      if (!res.ok) throw new Error(`Download failed: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `dataset_${token.token.slice(0, 8)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  const issued = new Date(token.issued_at).toLocaleString()
  const expires = token.expires_at ? new Date(token.expires_at).toLocaleString() : null

  return (
    <div className="rounded-2xl border border-success/30 bg-success/5 p-6">
      <div className="flex items-center gap-2.5 mb-4">
        <Key weight="fill" className="size-5 text-success" />
        <p className="text-sm font-semibold text-success">Download Token Issued</p>
      </div>

      <div className="rounded-xl border border-success/20 bg-white px-4 py-3 mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] font-semibold text-[#6e6e73] uppercase tracking-widest">Token</span>
          <button
            onClick={copyToken}
            className="flex items-center gap-1 text-xs text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
          >
            {copied ? (
              <><Check className="size-3.5 text-success" /> Copied!</>
            ) : (
              <><Copy className="size-3.5" /> Copy</>
            )}
          </button>
        </div>
        <p className="font-mono text-xs text-[#1d1d1f] break-all leading-relaxed">{token.token}</p>
      </div>

      <button
        onClick={downloadDataset}
        disabled={downloading}
        className="w-full flex items-center justify-center gap-2 rounded-full bg-success py-3 text-sm font-medium text-white hover:bg-success/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        <DownloadSimple weight="bold" className="size-4" />
        {downloading ? "Downloading…" : "Download Dataset CSV"}
      </button>

      <div className="space-y-1 text-xs text-[#6e6e73] mt-3">
        <p>Issued: <span className="text-[#1d1d1f]">{issued}</span></p>
        {expires && <p>Expires: <span className="text-[#1d1d1f]">{expires}</span></p>}
      </div>
    </div>
  )
}
