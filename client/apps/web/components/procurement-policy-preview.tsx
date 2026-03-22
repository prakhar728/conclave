"use client"

import { ShieldCheck } from "@phosphor-icons/react"
import type { BuyerPolicy } from "@/lib/types"

interface ProcurementPolicyPreviewProps {
  policy: Partial<BuyerPolicy>
}

export function ProcurementPolicyPreview({ policy }: ProcurementPolicyPreviewProps) {
  const isEmpty =
    !policy.max_budget &&
    !policy.min_row_count &&
    (!policy.required_columns || policy.required_columns.length === 0) &&
    (!policy.milestone_weights || Object.keys(policy.milestone_weights).length === 0)

  if (isEmpty) {
    return (
      <p className="text-sm text-[#aeaeb2]">
        Procurement policy will appear here as we configure…
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {/* Budget */}
      {policy.max_budget != null && (
        <Section label="Budget">
          <Row label="Max budget" value={`$${policy.max_budget.toLocaleString()}`} />
        </Section>
      )}

      {/* Hard constraints */}
      {(policy.min_row_count != null || policy.max_null_rate != null || policy.max_duplicate_rate != null) && (
        <Section label="Hard Constraints">
          {policy.min_row_count != null && (
            <Row label="Min rows" value={policy.min_row_count.toLocaleString()} />
          )}
          {policy.max_null_rate != null && (
            <Row label="Max null rate" value={`${(policy.max_null_rate * 100).toFixed(0)}%`} />
          )}
          {policy.max_duplicate_rate != null && (
            <Row label="Max dup rate" value={`${(policy.max_duplicate_rate * 100).toFixed(0)}%`} />
          )}
        </Section>
      )}

      {/* Required columns */}
      {policy.required_columns && policy.required_columns.length > 0 && (
        <Section label="Required Columns">
          <div className="flex flex-wrap gap-1">
            {policy.required_columns.map((col) => (
              <span key={col} className="text-xs bg-primary/10 text-primary rounded px-1.5 py-0.5 font-mono">
                {col}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Milestones */}
      {policy.milestone_weights && Object.keys(policy.milestone_weights).length > 0 && (
        <Section label="Milestone Weights">
          {Object.entries(policy.milestone_weights).map(([name, weight]) => (
            <div key={name} className="mb-2">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-[#1d1d1f] capitalize">{name.replace(/_/g, " ")}</span>
                <span className="text-[#6e6e73]">{(weight * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-white overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${weight * 100}%` }}
                />
              </div>
            </div>
          ))}
        </Section>
      )}

      {/* Renegotiation */}
      {policy.renegotiation_enabled != null && (
        <Section label="Renegotiation">
          <div className="flex items-center gap-1.5 text-sm">
            {policy.renegotiation_enabled ? (
              <>
                <span className="size-2 rounded-full bg-success" />
                <span className="text-success">One round enabled</span>
              </>
            ) : (
              <>
                <span className="size-2 rounded-full bg-[#aeaeb2]" />
                <span className="text-[#6e6e73]">Disabled</span>
              </>
            )}
          </div>
        </Section>
      )}

      {/* Release mode */}
      {policy.release_mode && (
        <Section label="Release Mode">
          <div className="flex items-center gap-1.5 text-sm">
            <ShieldCheck weight="fill" className="size-3.5 text-success" />
            <span className="text-[#1d1d1f] capitalize">{policy.release_mode}</span>
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-[#6e6e73] uppercase tracking-widest mb-2">{label}</p>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm mb-1">
      <span className="text-[#6e6e73]">{label}</span>
      <span className="text-[#1d1d1f] font-medium">{value}</span>
    </div>
  )
}
