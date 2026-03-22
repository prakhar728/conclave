"use client"

import { ShieldCheck } from "@phosphor-icons/react"

interface ProcurementScorecardProps {
  partialScore: number
  proposedPayment: number
  maxBudget?: number
  reservePrice?: number
  role?: "buyer" | "seller"
}

export function ProcurementScorecard({
  partialScore,
  proposedPayment,
  maxBudget,
  reservePrice,
  role = "buyer",
}: ProcurementScorecardProps) {
  const pct = Math.max(0, Math.min(1, partialScore))
  const circumference = 264
  const strokeDash = pct * circumference

  const scoreColor =
    pct >= 0.8 ? "#34c759" : pct >= 0.5 ? "#ff9f0a" : "#ff3b30"

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
      <div className="flex items-center gap-2 mb-5">
        <ShieldCheck weight="fill" className="size-4 text-success" />
        <p className="text-xs font-semibold text-[#6e6e73] uppercase tracking-wider">
          Evaluation Summary
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Score gauge */}
        <div className="text-center">
          <p className="text-xs text-[#6e6e73] mb-3">Score (S)</p>
          <div className="relative inline-flex items-center justify-center">
            <svg className="size-24 -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="#f5f5f7" strokeWidth="8" />
              <circle
                cx="50"
                cy="50"
                r="42"
                fill="none"
                stroke={scoreColor}
                strokeWidth="8"
                strokeDasharray={`${strokeDash} ${circumference}`}
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute text-2xl font-bold text-[#1d1d1f]">
              {(pct * 100).toFixed(0)}
            </span>
          </div>
          <p className="text-xs text-[#aeaeb2] mt-1">out of 100</p>
        </div>

        {/* Payment */}
        <div className="text-center flex flex-col justify-center">
          <p className="text-xs text-[#6e6e73] mb-1">
            {role === "buyer" ? "Proposed Payment" : "Eligibility Amount"}
          </p>
          <p className="text-3xl font-bold text-[#1d1d1f] mt-1">
            ${proposedPayment.toLocaleString()}
          </p>
          {maxBudget && role === "buyer" && (
            <p className="text-xs text-[#aeaeb2] mt-1">of ${maxBudget.toLocaleString()} max</p>
          )}
          {reservePrice && role === "seller" && (
            <p
              className={
                proposedPayment >= reservePrice
                  ? "text-xs text-success mt-1"
                  : "text-xs text-red-500 mt-1"
              }
            >
              {proposedPayment >= reservePrice ? "Meets" : "Below"} reserve (${reservePrice.toLocaleString()})
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
