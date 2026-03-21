import Link from "next/link"
import { ArrowLeft } from "@phosphor-icons/react/dist/ssr"
import { TemplateCard, TEMPLATE_CATALOG } from "@/components/template-card"

export default function TemplatesPage() {
  const live = TEMPLATE_CATALOG.filter((t) => t.status === "live")
  const coming = TEMPLATE_CATALOG.filter((t) => t.status === "coming_soon")

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="bg-[#f5f5f7]">
        <div className="mx-auto max-w-[980px] px-6 py-16">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-[#6e6e73] hover:text-[#1d1d1f] mb-6 transition-colors"
          >
            <ArrowLeft className="size-3.5" /> Back
          </Link>
          <h1 className="text-4xl md:text-[48px] font-bold tracking-apple-tight text-[#1d1d1f] mb-4">
            Templates
          </h1>
          <p className="text-[#6e6e73] text-lg max-w-xl leading-relaxed">
            Each template is a self-contained use case — sensitive input, enclave skill, safe
            structured output.
          </p>
        </div>
      </div>

      <div className="mx-auto max-w-[980px] px-6 py-16 space-y-16">
        {/* Live */}
        <section>
          <div className="flex items-center gap-2.5 mb-6">
            <span className="size-2 rounded-full bg-success" />
            <h2 className="text-sm font-semibold text-[#1d1d1f] uppercase tracking-widest">Live</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {live.map((t) => (
              <TemplateCard key={t.name} template={t} />
            ))}
          </div>
        </section>

        {/* Coming soon */}
        <section>
          <div className="flex items-center gap-2.5 mb-6">
            <span className="size-2 rounded-full bg-[#aeaeb2]" />
            <h2 className="text-sm font-semibold text-[#6e6e73] uppercase tracking-widest">Coming Soon</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {coming.map((t) => (
              <TemplateCard key={t.name} template={t} />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
