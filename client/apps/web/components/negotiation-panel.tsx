"use client"

import * as React from "react"
import { Warning, X, Check, ArrowCounterClockwise } from "@phosphor-icons/react"
import { cn } from "@workspace/ui/lib/utils"
import type { NegotiationStatus } from "@/lib/types"

interface NegotiationPanelProps {
  negotiation: NegotiationStatus
  role: "buyer" | "seller"
  maxBudget?: number
  reservePrice?: number
  proposedPayment?: number
  onAccept: () => void
  onReject: () => void
  onRenegotiate: (revisedValue: number) => void
  disabled?: boolean
}

export function NegotiationPanel({
  negotiation,
  role,
  maxBudget,
  reservePrice,
  proposedPayment,
  onAccept,
  onReject,
  onRenegotiate,
  disabled = false,
}: NegotiationPanelProps) {
  const [showWarning, setShowWarning] = React.useState(false)
  const [showRenegotiateForm, setShowRenegotiateForm] = React.useState(false)
  const [revisedValue, setRevisedValue] = React.useState("")

  const { state, used } = negotiation
  const isTerminal = ["accepted", "rejected"].includes(state)

  // Is it this party's turn to respond?
  const myTurn =
    (role === "seller" && state === "requested_by_buyer") ||
    (role === "buyer" && state === "requested_by_seller")

  // Did this party already respond and the other hasn't yet?
  const iWaiting =
    (role === "buyer" && state === "requested_by_buyer") ||
    (role === "seller" && state === "requested_by_seller") ||
    state === "awaiting_counterparty" ||
    state === "renegotiation_submitted"

  const showActionButtons = (state === "none" || myTurn) && !isTerminal && !iWaiting && !showRenegotiateForm

  function handleRenegotiateClick() {
    if (used) return
    setShowWarning(true)
  }

  function handleWarningConfirm() {
    setShowWarning(false)
    setShowRenegotiateForm(true)
  }

  function handleRenegotiateSubmit() {
    const val = parseFloat(revisedValue.replace(/,/g, ""))
    if (isNaN(val) || val <= 0) return
    onRenegotiate(val)
    setShowRenegotiateForm(false)
  }

  return (
    <div className="rounded-2xl border border-[#d2d2d7] bg-white p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold text-[#1d1d1f]">Negotiation</p>
        <NegotiationBadge state={state} />
      </div>

      {/* Terminal states */}
      {state === "accepted" && (
        <div className="flex items-center gap-2 text-success text-sm">
          <Check weight="bold" className="size-4" /> Deal accepted. Settlement authorized.
        </div>
      )}
      {state === "rejected" && (
        <div className="flex items-center gap-2 text-red-500 text-sm">
          <X weight="bold" className="size-4" /> Deal rejected.
        </div>
      )}

      {/* Counterparty responded — this party needs to act */}
      {myTurn && !showRenegotiateForm && (
        <div className="rounded-xl bg-[#fff9ec] border border-[#ff9f0a]/20 px-4 py-3 mb-3 text-sm space-y-1">
          {role === "seller" ? (
            <>
              {negotiation.revised_budget != null && (
                <p className="text-[#1d1d1f]">
                  Buyer's revised offer:{" "}
                  <span className="font-semibold">${negotiation.revised_budget.toLocaleString()}</span>
                </p>
              )}
              {proposedPayment != null && (
                <p className="text-[#6e6e73]">
                  If you <span className="font-medium text-[#1d1d1f]">accept</span>, you receive the original evaluated amount:{" "}
                  <span className="font-semibold text-[#1d1d1f]">${proposedPayment.toLocaleString()}</span>
                </p>
              )}
              {negotiation.revised_budget != null && (
                <p className="text-[#6e6e73]">
                  If you <span className="font-medium text-[#1d1d1f]">renegotiate</span>, your revised reserve will be compared against the buyer's{" "}
                  <span className="font-semibold text-[#1d1d1f]">${negotiation.revised_budget.toLocaleString()}</span>.
                </p>
              )}
            </>
          ) : (
            <>
              {negotiation.revised_reserve != null && (
                <p className="text-[#1d1d1f]">
                  Seller's revised reserve:{" "}
                  <span className="font-semibold">${negotiation.revised_reserve.toLocaleString()}</span>
                </p>
              )}
              {proposedPayment != null && (
                <p className="text-[#6e6e73]">
                  If you <span className="font-medium text-[#1d1d1f]">accept</span>, you pay the original evaluated amount:{" "}
                  <span className="font-semibold text-[#1d1d1f]">${proposedPayment.toLocaleString()}</span>
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* Waiting for counterparty */}
      {iWaiting && (
        <p className="text-sm text-[#6e6e73]">
          Waiting for {role === "buyer" ? "seller" : "buyer"} to respond…
        </p>
      )}

      {/* Action buttons — initial response or counter-response */}
      {showActionButtons && (
        <div className="flex gap-2">
          <button
            onClick={onAccept}
            disabled={disabled}
            className="flex items-center gap-1.5 rounded-full bg-success px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <Check weight="bold" className="size-3.5" /> Accept
          </button>
          <button
            onClick={onReject}
            disabled={disabled}
            className="flex items-center gap-1.5 rounded-full border border-red-200 text-red-500 px-4 py-2 text-sm font-medium hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <X weight="bold" className="size-3.5" /> Reject
          </button>
          <button
            onClick={handleRenegotiateClick}
            disabled={disabled || used}
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-all",
              used
                ? "border-[#e8e8ed] text-[#aeaeb2] cursor-not-allowed"
                : "border-[#d2d2d7] text-[#1d1d1f] hover:border-[#aeaeb2]",
            )}
          >
            <ArrowCounterClockwise className="size-3.5" />
            {used ? "Renegotiation used" : "Renegotiate"}
          </button>
        </div>
      )}

      {/* Renegotiate input form */}
      {showRenegotiateForm && (
        <div className="space-y-3">
          <p className="text-sm text-[#6e6e73]">
            Enter your revised {role === "buyer" ? "budget" : "reserve price"}:
          </p>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6e6e73] text-sm">$</span>
              <input
                type="text"
                value={revisedValue}
                onChange={(e) => setRevisedValue(e.target.value.replace(/[^\d,.]/g, ""))}
                placeholder={role === "buyer" ? (maxBudget?.toLocaleString() ?? "0") : (reservePrice?.toLocaleString() ?? "0")}
                className="w-full rounded-xl border border-[#d2d2d7] bg-white pl-7 pr-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
              />
            </div>
            <button
              onClick={handleRenegotiateSubmit}
              disabled={!revisedValue}
              className="rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5a2fd4] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              Submit
            </button>
            <button
              onClick={() => setShowRenegotiateForm(false)}
              className="rounded-xl border border-[#d2d2d7] px-4 py-2.5 text-sm text-[#6e6e73] hover:border-[#aeaeb2] transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Warning modal */}
      {showWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-6">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center gap-2.5 mb-4">
              <Warning weight="fill" className="size-5 text-[#ff9f0a]" />
              <p className="font-semibold text-[#1d1d1f]">Renegotiation warning</p>
            </div>
            <ul className="text-sm text-[#6e6e73] space-y-2 mb-5 list-disc list-inside">
              <li>Only one renegotiation round is allowed</li>
              <li>The evaluation score will not change</li>
              <li>
                Only the {role === "buyer" ? "buyer budget" : "seller reserve"} can change
              </li>
              <li>If the revised numbers don't overlap, the deal will fail</li>
            </ul>
            <div className="flex gap-2">
              <button
                onClick={handleWarningConfirm}
                className="flex-1 rounded-full bg-[#ff9f0a] py-2.5 text-sm font-medium text-white hover:opacity-90 transition-all"
              >
                I understand, proceed
              </button>
              <button
                onClick={() => setShowWarning(false)}
                className="flex-1 rounded-full border border-[#d2d2d7] py-2.5 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function NegotiationBadge({ state }: { state: NegotiationStatus["state"] }) {
  const config: Record<string, { label: string; className: string }> = {
    none: { label: "Pending decision", className: "bg-[#f5f5f7] text-[#6e6e73]" },
    requested_by_buyer: { label: "Buyer renegotiating", className: "bg-[#ff9f0a]/10 text-[#ff9f0a]" },
    requested_by_seller: { label: "Seller renegotiating", className: "bg-[#ff9f0a]/10 text-[#ff9f0a]" },
    awaiting_counterparty: { label: "Awaiting response", className: "bg-[#ff9f0a]/10 text-[#ff9f0a]" },
    renegotiation_submitted: { label: "Renegotiation submitted", className: "bg-primary/10 text-primary" },
    accepted: { label: "Accepted", className: "bg-success/10 text-success" },
    rejected: { label: "Rejected", className: "bg-red-50 text-red-500" },
  }
  const { label, className } = config[state] ?? config["none"]!
  return (
    <span className={cn("text-xs font-medium px-2.5 py-1 rounded-full", className)}>{label}</span>
  )
}
