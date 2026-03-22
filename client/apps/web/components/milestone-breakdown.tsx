"use client"

import { cn } from "@workspace/ui/lib/utils"
import type { MilestoneScore } from "@/lib/types"

export function MilestoneBreakdown({ milestones }: { milestones: MilestoneScore[] }) {
  const weightedScore = milestones.reduce((acc, m) => acc + m.score * m.weight, 0)

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm font-semibold text-[#1d1d1f]">Milestone Scores</p>
        <span className="text-xs text-[#6e6e73]">
          Weighted total: <span className="font-semibold text-[#1d1d1f]">{(weightedScore * 100).toFixed(0)}%</span>
        </span>
      </div>
      <div className="space-y-4">
        {milestones.map((m) => (
          <div key={m.name}>
            <div className="flex items-center justify-between text-sm mb-1.5">
              <div className="flex items-center gap-2">
                <span className="text-[#1d1d1f]">{m.name}</span>
                <span className="text-[10px] text-[#aeaeb2] bg-[#f5f5f7] px-1.5 py-0.5 rounded-full">
                  {(m.weight * 100).toFixed(0)}%
                </span>
              </div>
              <span className="font-mono text-[#1d1d1f] font-medium tabular-nums">
                {(m.score * 100).toFixed(0)}
              </span>
            </div>
            <div className="h-2 rounded-full bg-[#f5f5f7] overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  m.score >= 0.8 ? "bg-primary" : m.score >= 0.5 ? "bg-[#ff9f0a]" : "bg-red-400",
                )}
                style={{ width: `${m.score * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
