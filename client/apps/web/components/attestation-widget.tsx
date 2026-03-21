"use client"

import * as React from "react"
import { ShieldCheck, CircleNotch, Copy, Check, CaretDown } from "@phosphor-icons/react"
import { cn } from "@workspace/ui/lib/utils"

interface AttestationWidgetProps {
  compact?: boolean
  onVerified?: () => void
  className?: string
}

type AttState = "idle" | "loading" | "verified" | "failed"

const MOCK_DATA = {
  measurement: "a3b8d1f4e2c9a7b6d5f3e1c8a4b7d2f6e9c3a5b8d1f4e2c9a7b6d5f3e1c8a4b7",
  imageDigest: "sha256:7f2a4b9e3d1c8f6a5b4d2e9c7a3f1b8d6e4c2a9",
  gitSha: "e4c2a9b7d5f3e1c8a4b6d2f9",
}

export function AttestationWidget({ compact, onVerified, className }: AttestationWidgetProps) {
  const [state, setState] = React.useState<AttState>("idle")
  const [expanded, setExpanded] = React.useState(false)

  async function verify() {
    setState("loading")
    await new Promise((r) => setTimeout(r, 2000))
    setState("verified")
    onVerified?.()
  }

  return (
    <div
      className={cn(
        "rounded-2xl border bg-white p-6 transition-all",
        state === "verified"
          ? "border-success/40 animate-verified-pulse"
          : state === "idle"
            ? "border-primary/30"
            : "border-border",
        className,
      )}
    >
      {!compact && (
        <div className="mb-5">
          <h3 className="text-lg font-semibold text-[#1d1d1f] tracking-apple mb-1">
            Verify the enclave before you submit
          </h3>
          <p className="text-sm text-[#6e6e73]">
            This confirms your data will only be processed by the code below — and nothing else.
          </p>
        </div>
      )}

      <div className="space-y-3">
        <DataRow label="Measurement" value={MOCK_DATA.measurement} mono truncate />
        <DataRow label="Image digest" value={MOCK_DATA.imageDigest} mono />
        <DataRow label="Git SHA" value={MOCK_DATA.gitSha} mono />
      </div>

      <div className="mt-5 flex items-center gap-3">
        {state === "idle" && (
          <button
            onClick={verify}
            className="rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-[#5a2fd4] transition-colors"
          >
            Verify Enclave
          </button>
        )}
        {state === "loading" && (
          <div className="flex items-center gap-2 text-sm text-[#6e6e73]">
            <CircleNotch className="size-4 animate-spin" />
            Verifying…
          </div>
        )}
        {state === "verified" && (
          <div className="flex items-center gap-2 text-sm text-success font-medium">
            <ShieldCheck weight="fill" className="size-5" />
            Enclave verified ✓
          </div>
        )}
        {state === "failed" && (
          <div className="text-sm text-destructive font-medium">
            Verification failed — enclave measurement does not match.
          </div>
        )}
      </div>

      {!compact && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-4 flex items-center gap-1 text-xs text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
        >
          <CaretDown
            className={cn("size-3 transition-transform", expanded && "rotate-180")}
          />
          {expanded ? "Hide" : "Show"} raw TDX quote
        </button>
      )}

      {expanded && (
        <pre className="mt-3 rounded-lg bg-[#f5f5f7] p-4 text-xs font-mono text-[#1d1d1f] overflow-x-auto leading-relaxed">
          {`{
  "quote_type": "TDX",
  "measurement": "${MOCK_DATA.measurement}",
  "mr_signer": "d4f2a1b7e3c9...",
  "report_data": "0x7f3a2b1c..."
}`}
        </pre>
      )}
    </div>
  )
}

function DataRow({
  label,
  value,
  mono,
  truncate,
}: {
  label: string
  value: string
  mono?: boolean
  truncate?: boolean
}) {
  const [copied, setCopied] = React.useState(false)

  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs font-medium text-[#6e6e73] shrink-0">{label}</span>
      <div className="flex items-center gap-2 min-w-0">
        <span
          className={cn(
            "text-xs text-[#1d1d1f]",
            mono && "font-mono bg-[#f5f5f7] px-2 py-0.5 rounded-md",
            truncate && "truncate max-w-[200px]",
          )}
        >
          {value}
        </span>
        <button
          onClick={async () => {
            await navigator.clipboard.writeText(value)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          }}
          className="text-[#aeaeb2] hover:text-[#6e6e73] transition-colors shrink-0"
        >
          {copied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
        </button>
      </div>
    </div>
  )
}
