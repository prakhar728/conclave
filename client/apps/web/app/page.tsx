import Link from "next/link"
import { ArrowRight, Lock, Shield, ChartBar, ShieldCheck } from "@phosphor-icons/react/dist/ssr"
import { AttestationWidget } from "@/components/attestation-widget"
import { TemplateCard, TEMPLATE_CATALOG } from "@/components/template-card"
import { FeaturesSectionWithHoverEffects } from "@/components/ui/feature-section-with-hover-effects"

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-[#1d1d1f]">
      <Nav />
      <Hero />
      <Explainer />
      <Pathways />
      <AttestationSection />
      <TemplatePreview />
      <HowItWorks />
      <FeaturesSection />
      <WhatWeStore />
      <Footer />
    </div>
  )
}

// ---------------------------------------------------------------------------

function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-[#d2d2d7]/60 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto max-w-[980px] px-6 h-12 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div className="size-7 rounded-lg bg-primary/10 flex items-center justify-center">
            <Lock weight="fill" className="size-3.5 text-primary" />
          </div>
          <span className="font-semibold text-sm tracking-tight text-[#1d1d1f]">NDAI</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-sm text-[#6e6e73]">
          <Link href="/templates" className="hover:text-[#1d1d1f] transition-colors">Templates</Link>
          <a href="#how-it-works" className="hover:text-[#1d1d1f] transition-colors">How It Works</a>
          <a href="#for-operators" className="hover:text-[#1d1d1f] transition-colors">For Operators</a>
        </nav>

        <div className="flex items-center gap-3">
          <a href="#attestation" className="hidden sm:inline-flex text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors">
            Verify Enclave
          </a>
          <Link
            href="/setup"
            className="rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-white hover:bg-[#5a2fd4] transition-colors"
          >
            Create Instance
          </Link>
        </div>
      </div>
    </header>
  )
}

// ---------------------------------------------------------------------------

function Hero() {
  return (
    <section className="relative overflow-hidden min-h-[90vh] flex items-center bg-white">
      {/* Cipher particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {Array.from({ length: 16 }).map((_, i) => (
          <div
            key={i}
            className="absolute text-[#d2d2d7] font-mono text-xs select-none animate-float"
            style={{
              left: `${(i * 6.7) % 100}%`,
              top: `${(i * 8.3) % 100}%`,
              animationDelay: `${i * 0.5}s`,
              animationDuration: `${10 + (i % 4) * 2}s`,
            }}
          >
            {["0x4f2a", "TEE", "0xd3fb", "TDX", "0xa1c9", "SHA256", "0x7e3d", "MRENCLAVE"][i % 8]}
          </div>
        ))}
      </div>

      <div className="relative mx-auto max-w-[980px] px-6 py-32 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-[#d2d2d7] bg-[#f5f5f7] px-4 py-1.5 text-xs text-[#6e6e73] mb-8">
          <Lock weight="fill" className="size-3 text-primary" />
          Powered by Trusted Execution Environments
        </div>

        <h1 className="text-5xl md:text-[80px] font-bold tracking-apple-tight leading-[1.05] mb-6">
          The NDA you{" "}
          <span className="text-primary">don&apos;t have</span>
          <br />
          to sign
        </h1>

        <p className="text-lg md:text-xl text-[#6e6e73] max-w-2xl mx-auto mb-10 leading-relaxed">
          Submit your most sensitive data. Get AI-generated insights. Nothing ever leaves
          the enclave — not to other participants, not to the organizer, not to us.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-12">
          <Link
            href="/setup"
            className="flex items-center gap-2 rounded-full bg-primary px-7 py-3 text-sm font-medium text-white hover:bg-[#5a2fd4] transition-all hover:shadow-[0_4px_16px_rgba(110,63,243,0.3)]"
          >
            Create an Instance <ArrowRight className="size-4" />
          </Link>
          <Link
            href="/templates"
            className="flex items-center gap-2 rounded-full border border-[#d2d2d7] px-7 py-3 text-sm font-medium text-[#1d1d1f] hover:border-[#aeaeb2] transition-all"
          >
            See Templates
          </Link>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-sm text-[#6e6e73]">
          <span className="flex items-center gap-2">
            <ShieldCheck weight="fill" className="size-4 text-success" />
            Cryptographically verifiable
          </span>
          <span className="flex items-center gap-2">
            <ShieldCheck weight="fill" className="size-4 text-success" />
            Enclave-enforced privacy
          </span>
          <span className="flex items-center gap-2">
            <ShieldCheck weight="fill" className="size-4 text-success" />
            Open attestation
          </span>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function Explainer() {
  return (
    <section className="bg-[#f5f5f7]">
      <div className="mx-auto max-w-[980px] px-6 py-24 text-center">
        <p className="text-lg md:text-xl text-[#6e6e73] max-w-3xl mx-auto leading-relaxed mb-16">
          We built a platform where your data enters a hardware-enforced secure enclave, an AI runs
          on it, and only the results come back. The enclave&apos;s behavior is publicly verifiable —
          anyone can confirm what code ran on their data.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              icon: <Lock weight="fill" className="size-6" />,
              title: "Sent to the enclave over TLS",
              desc: "The connection terminates inside the hardware TEE. No one in between can read it.",
            },
            {
              icon: <Shield weight="fill" className="size-6" />,
              title: "Processed inside the TEE only",
              desc: "Hardware-isolated at the CPU level. Not us, not the operator, not anyone outside.",
            },
            {
              icon: <ChartBar weight="fill" className="size-6" />,
              title: "Only scores and metrics exit",
              desc: "Novelty scores, percentiles, cluster labels. The raw content never leaves.",
            },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="rounded-2xl bg-white p-6 text-left hover-lift">
              <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                {icon}
              </div>
              <h3 className="text-base font-semibold text-[#1d1d1f] tracking-apple mb-2">{title}</h3>
              <p className="text-sm text-[#6e6e73] leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function Pathways() {
  return (
    <section id="for-operators" className="bg-white">
      <div className="mx-auto max-w-[980px] px-6 py-24">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-[#d2d2d7] bg-white p-8 hover-lift transition-all group">
            <div className="text-3xl mb-5">⚙️</div>
            <p className="text-xs font-semibold text-primary mb-2 uppercase tracking-widest">For Operators</p>
            <h3 className="text-xl font-bold text-[#1d1d1f] tracking-apple mb-3">
              I&apos;m running an event or program
            </h3>
            <p className="text-sm text-[#6e6e73] leading-relaxed mb-6">
              Pick a template, configure your criteria, deploy. Get a shareable link. Receive
              aggregate results — never raw submissions.
            </p>
            <Link
              href="/setup"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-[#5a2fd4] transition-colors"
            >
              Create an Instance <ArrowRight className="size-4" />
            </Link>
          </div>

          <div className="rounded-2xl border border-[#d2d2d7] bg-white p-8 hover-lift transition-all group">
            <div className="text-3xl mb-5">🧑‍💻</div>
            <p className="text-xs font-semibold text-[#6e6e73] mb-2 uppercase tracking-widest">For Participants</p>
            <h3 className="text-xl font-bold text-[#1d1d1f] tracking-apple mb-3">
              I was sent a link to submit
            </h3>
            <p className="text-sm text-[#6e6e73] leading-relaxed mb-6">
              Verify the enclave, submit your work. Your idea, pitch deck, and repo are processed
              only inside the TEE. You get your scores — no one else sees your submission.
            </p>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
            >
              Learn how submissions work <ArrowRight className="size-4" />
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function AttestationSection() {
  return (
    <section id="attestation" className="bg-[#f5f5f7]">
      <div className="mx-auto max-w-[980px] px-6 py-24 text-center">
        <h2 className="text-3xl md:text-[40px] font-bold tracking-apple-tight mb-4">
          Don&apos;t take our word for it.
          <br />
          Verify it yourself.
        </h2>
        <p className="text-base text-[#6e6e73] mb-12 max-w-xl mx-auto">
          This is the live enclave running right now. Anyone can check that the code matches what
          we published.
        </p>
        <div className="text-left max-w-lg mx-auto">
          <AttestationWidget compact />
        </div>
        <p className="text-sm text-[#aeaeb2] mt-8">
          Participants verify this same widget before submitting. That&apos;s the guarantee.
        </p>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function TemplatePreview() {
  return (
    <section className="bg-white">
      <div className="mx-auto max-w-[980px] px-6 py-24">
        <div className="text-center mb-14">
          <h2 className="text-3xl md:text-[40px] font-bold tracking-apple-tight mb-4">
            Sensitive data, safe insights
          </h2>
          <p className="text-base text-[#6e6e73]">
            Each template is a self-contained skill running inside the enclave.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {TEMPLATE_CATALOG.map((t) => (
            <TemplateCard key={t.name} template={t} />
          ))}
        </div>

        <div className="text-center mt-12">
          <Link
            href="/templates"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-[#5a2fd4] transition-colors"
          >
            See all templates <ArrowRight className="size-4" />
          </Link>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function HowItWorks() {
  const steps = [
    {
      n: "01",
      title: "Your data travels to the enclave over TLS",
      desc: "The connection terminates inside the hardware-enforced TEE. No one in between can read it.",
    },
    {
      n: "02",
      title: "Only the enclave can process it",
      desc: "The TEE is isolated at the hardware level. Not us. Not the operator. Not anyone outside.",
    },
    {
      n: "03",
      title: "Skill runs on your data",
      desc: "An AI skill processes all submissions together. No submission content touches another participant.",
    },
    {
      n: "04",
      title: "Only outputs exit",
      desc: "Scores, percentiles, cluster labels. The raw content never leaves the enclave.",
    },
    {
      n: "05",
      title: "Output is signed",
      desc: "The enclave signs every result with its hardware-bound private key. Verifiable by anyone.",
    },
  ]

  return (
    <section id="how-it-works" className="bg-[#f5f5f7]">
      <div className="mx-auto max-w-[980px] px-6 py-24">
        <h2 className="text-3xl md:text-[40px] font-bold tracking-apple-tight mb-16 text-center">
          How the enclave works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-0">
          {steps.map((step, i) => (
            <div key={step.n} className="relative flex flex-col items-center text-center px-4 py-6 md:py-0">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-6 left-1/2 w-full h-px bg-[#d2d2d7]" />
              )}
              {/* Number */}
              <div className="relative z-10 size-12 rounded-full bg-white border border-[#d2d2d7] flex items-center justify-center text-sm font-mono font-semibold text-primary mb-4 shrink-0 shadow-sm">
                {step.n}
              </div>
              <h3 className="text-sm font-semibold text-[#1d1d1f] mb-2 leading-tight tracking-apple">
                {step.title}
              </h3>
              <p className="text-xs text-[#6e6e73] leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function FeaturesSection() {
  return (
    <section className="bg-white">
      <div className="mx-auto max-w-[980px] px-6 pt-24 pb-8">
        <div className="text-center mb-4">
          <h2 className="text-3xl md:text-[40px] font-bold tracking-apple-tight mb-4">
            Built on trust, not promises
          </h2>
          <p className="text-base text-[#6e6e73]">
            Every layer of NDAI is designed so you never have to take our word for it.
          </p>
        </div>
      </div>
      <FeaturesSectionWithHoverEffects />
    </section>
  )
}

// ---------------------------------------------------------------------------

function WhatWeStore() {
  return (
    <section className="bg-white">
      <div className="mx-auto max-w-[980px] px-6 py-24">
        <div className="rounded-2xl bg-[#f5f5f7] p-8 md:p-14">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-apple-tight mb-4">What we never store</h2>
            <p className="text-sm text-[#6e6e73] max-w-xl mx-auto">
              This is not a policy promise. It&apos;s a cryptographic constraint — the enclave has
              no write path to anything outside.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
            <div>
              <p className="text-xs font-semibold text-[#6e6e73] uppercase tracking-widest mb-4">
                We store
              </p>
              <ul className="space-y-3">
                {["Submission receipts (ID + timestamp)", "GitHub installation IDs", "Signed output scores", "Enclave attestation quotes"].map((item) => (
                  <li key={item} className="flex items-center gap-3 text-sm text-[#1d1d1f]">
                    <span className="size-1.5 rounded-full bg-[#d2d2d7] shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-success uppercase tracking-widest mb-4">
                We never store
              </p>
              <ul className="space-y-3">
                {["Your idea text", "Pitch deck content", "GitHub repo code", "Cross-submission similarity data"].map((item) => (
                  <li key={item} className="flex items-center gap-3 text-sm text-success">
                    <ShieldCheck weight="fill" className="size-4 shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="border-t border-[#d2d2d7]/60 bg-[#f5f5f7]">
      <div className="mx-auto max-w-[980px] px-6 py-14">
        <div className="flex flex-col md:flex-row justify-between gap-10">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="size-6 rounded-lg bg-primary/10 flex items-center justify-center">
                <Lock weight="fill" className="size-3 text-primary" />
              </div>
              <span className="font-semibold text-sm text-[#1d1d1f]">NDAI</span>
            </div>
            <p className="text-sm text-[#6e6e73] max-w-xs leading-relaxed">
              The NDA you don&apos;t have to sign. Multi-party AI insights from sensitive data,
              enclave-enforced.
            </p>
          </div>

          <div className="flex gap-16">
            <div>
              <p className="text-xs font-semibold text-[#1d1d1f] uppercase tracking-widest mb-4">Product</p>
              <ul className="space-y-2.5">
                {([["Templates", "/templates"], ["How It Works", "#how-it-works"]] as const).map(([label, href]) => (
                  <li key={label}>
                    <Link href={href} className="text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors">
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-[#1d1d1f] uppercase tracking-widest mb-4">Dev</p>
              <ul className="space-y-2.5">
                {([["GitHub", "#"]] as const).map(([label, href]) => (
                  <li key={label}>
                    <a href={href} className="text-sm text-[#6e6e73] hover:text-[#1d1d1f] transition-colors">
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
        <div className="mt-12 pt-6 border-t border-[#d2d2d7]/60 text-sm text-[#aeaeb2] text-center">
          © 2025 NDAI. Built on Phala Cloud · Intel TDX.
        </div>
      </div>
    </footer>
  )
}
