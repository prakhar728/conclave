"use client"

import { CheckCircle, XCircle } from "@phosphor-icons/react"
import { cn } from "@workspace/ui/lib/utils"
import type { HardConstraintResult } from "@/lib/types"

export function HardConstraintsCard({ constraints }: { constraints: HardConstraintResult[] }) {
  const failCount = constraints.filter((c) => !c.passed).length
  const allPassed = failCount === 0

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold text-[#1d1d1f]">Hard Constraints</p>
        <span
          className={cn(
            "text-xs font-medium px-2.5 py-1 rounded-full",
            allPassed
              ? "bg-success/10 text-success"
              : "bg-red-50 text-red-500 border border-red-200",
          )}
        >
          {allPassed ? "All passed" : `${failCount} failed`}
        </span>
      </div>
      <div className="space-y-3">
        {constraints.map((c, i) => (
          <div key={i} className="flex items-start gap-3">
            {c.passed ? (
              <CheckCircle weight="fill" className="size-4 text-success shrink-0 mt-0.5" />
            ) : (
              <XCircle weight="fill" className="size-4 text-red-500 shrink-0 mt-0.5" />
            )}
            <div>
              <p className="text-sm text-[#1d1d1f]">{c.name}</p>
              {c.detail && <p className="text-xs text-[#6e6e73] mt-0.5">{c.detail}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
