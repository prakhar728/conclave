import { cn } from "@workspace/ui/lib/utils"
import { ShieldCheck } from "@phosphor-icons/react/dist/ssr"

export type TemplateStatus = "live" | "coming_soon"

export interface Template {
  name: string
  skill_name: string
  icon: string
  status: TemplateStatus
  goesIn: string[]
  comesOut: string[]
  neverLeaves: string[]
}

export const TEMPLATE_CATALOG: Template[] = [
  {
    name: "Hackathon Judge",
    skill_name: "hackathon_novelty",
    icon: "⚡",
    status: "live",
    goesIn: ["Idea text", "Pitch deck (PDF)", "GitHub repo"],
    comesOut: ["Novelty score", "Criteria scores", "Cluster label"],
    neverLeaves: ["Raw idea content", "Deck text"],
  },
  {
    name: "Investor Memo Scorer",
    skill_name: "investor_memo",
    icon: "📊",
    status: "coming_soon",
    goesIn: ["Investment memo", "Market thesis"],
    comesOut: ["Strength score", "Risk assessment"],
    neverLeaves: ["Memo content", "Financial data"],
  },
  {
    name: "Team Fit Analyzer",
    skill_name: "team_fit",
    icon: "🤝",
    status: "coming_soon",
    goesIn: ["Role description", "Candidate profiles"],
    comesOut: ["Fit score", "Skills overlap"],
    neverLeaves: ["Candidate details", "Salary data"],
  },
]

interface TemplateCardProps {
  template: Template
  selectable?: boolean
  selected?: boolean
  onSelect?: () => void
}

export function TemplateCard({ template, selectable, selected, onSelect }: TemplateCardProps) {
  const isLive = template.status === "live"

  return (
    <div
      onClick={selectable ? onSelect : undefined}
      className={cn(
        "rounded-2xl border bg-white p-6 transition-all",
        selectable && "cursor-pointer",
        selected
          ? "border-primary ring-1 ring-primary/20"
          : "border-[#d2d2d7] hover:shadow-[0_4px_16px_rgba(0,0,0,0.08)]",
        selectable && !selected && "hover:border-[#aeaeb2]",
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">{template.icon}</span>
          <h3 className="text-base font-semibold text-[#1d1d1f] tracking-apple">{template.name}</h3>
        </div>
        <span
          className={cn(
            "text-xs font-medium px-2.5 py-1 rounded-full",
            isLive
              ? "bg-success/10 text-success"
              : "bg-[#f5f5f7] text-[#aeaeb2]",
          )}
        >
          {isLive ? "Live" : "Coming Soon"}
        </span>
      </div>

      {/* Goes in */}
      <div className="mb-4">
        <p className="text-xs font-medium text-[#6e6e73] uppercase tracking-wider mb-2">Goes in</p>
        <ul className="space-y-1">
          {template.goesIn.map((item) => (
            <li key={item} className="flex items-center gap-2 text-sm text-[#1d1d1f]">
              <span className="size-1 rounded-full bg-[#d2d2d7] shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </div>

      {/* Comes out */}
      <div className="mb-4">
        <p className="text-xs font-medium text-[#6e6e73] uppercase tracking-wider mb-2">Comes out</p>
        <ul className="space-y-1">
          {template.comesOut.map((item) => (
            <li key={item} className="flex items-center gap-2 text-sm text-[#1d1d1f]">
              <span className="size-1 rounded-full bg-[#d2d2d7] shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </div>

      {/* Never leaves */}
      <div>
        <p className="text-xs font-medium text-success uppercase tracking-wider mb-2">
          Never leaves the enclave
        </p>
        <ul className="space-y-1">
          {template.neverLeaves.map((item) => (
            <li key={item} className="flex items-center gap-2 text-sm text-success">
              <ShieldCheck weight="fill" className="size-3.5 shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </div>

      {/* CTA */}
      {!selectable && isLive && (
        <div className="mt-5 pt-4 border-t border-[#e8e8ed]">
          <span className="text-sm font-medium text-primary hover:text-[#5a2fd4] transition-colors cursor-pointer">
            Use This Template →
          </span>
        </div>
      )}
    </div>
  )
}
