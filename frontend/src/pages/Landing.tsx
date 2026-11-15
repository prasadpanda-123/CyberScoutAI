import { Link } from "react-router-dom"
import {
  ArrowRight,
  CheckCircle2,
  Compass,
  LockKeyhole,
  Shield,
  Sparkles,
  Target,
} from "lucide-react"
import { Button } from "@/components/ui/button"

const reviewSteps = [
  {
    number: "01",
    title: "Discover",
    description: "Collect opportunities from cybersecurity programs and communities.",
  },
  {
    number: "02",
    title: "Review costs",
    description: "Check application requirements for fees and paid participation.",
  },
  {
    number: "03",
    title: "Surface clearly",
    description: "Show useful details and review status before you apply.",
  },
]

const capabilities = [
  {
    icon: Compass,
    title: "One focused place to explore",
    description:
      "Browse internships, CTFs, bug bounty programs, scholarships, and research opportunities.",
  },
  {
    icon: CheckCircle2,
    title: "Cost-aware verification",
    description:
      "Listings pass a free-only review pipeline designed to flag fees and unclear requirements.",
  },
  {
    icon: Target,
    title: "A better-fit shortlist",
    description:
      "Save relevant opportunities and keep application details close at hand.",
  },
]

export function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/80 bg-card/90 backdrop-blur-xl">
        <div className="mx-auto flex h-[72px] max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-3" aria-label="CyberScout AI home">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyber-blue to-cyan-600 text-white shadow-sm">
              <Shield className="h-5 w-5" />
            </span>
            <span className="text-base font-bold tracking-tight">
              CyberScout<span className="text-cyber-blue">.AI</span>
              <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                Opportunity intelligence
              </span>
            </span>
          </Link>

          <nav className="hidden items-center gap-8 text-sm font-medium text-muted-foreground md:flex">
            <a href="#how-it-works" className="transition-colors hover:text-foreground">
              How it works
            </a>
            <a href="#for-you" className="transition-colors hover:text-foreground">
              Explore
            </a>
          </nav>

          <div className="flex items-center gap-2 sm:gap-3">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">Sign in</Link>
            </Button>
            <Button asChild size="sm" className="shadow-sm">
              <Link to="/register">
                Create account <ArrowRight className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main>
        <section className="relative isolate overflow-hidden border-b border-border/70">
          <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_14%_20%,rgba(37,99,235,0.10),transparent_38%),radial-gradient(ellipse_at_90%_35%,rgba(6,182,212,0.08),transparent_35%)]" />
          <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:px-8 lg:py-28">
            <div className="max-w-2xl">
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                A clearer path into cybersecurity
              </div>
              <h1 className="text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                Find your next step.
                <span className="mt-2 block text-cyber-blue">Skip the paywall surprises.</span>
              </h1>
              <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
                Explore cybersecurity internships, CTFs, bug bounty programs, scholarships, and
                research opportunities in one focused place. Listings are screened for cost and
                requirements before they reach your feed.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button asChild size="lg" className="h-12 px-6 text-sm">
                  <Link to="/register">
                    Create your free account <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="h-12 px-6 text-sm">
                  <Link to="/login">Sign in to explore</Link>
                </Button>
              </div>
              <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-xs font-medium text-muted-foreground">
                <span className="inline-flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  Free-to-apply focus
                </span>
                <span className="inline-flex items-center gap-2">
                  <LockKeyhole className="h-4 w-4 text-cyber-blue" />
                  Private saved list
                </span>
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-xl">
              <div className="absolute -inset-5 -z-10 rounded-[2rem] bg-gradient-to-br from-blue-500/15 via-transparent to-cyan-400/10 blur-2xl" />
              <div className="rounded-2xl border border-border/80 bg-card/95 p-5 shadow-[0_24px_70px_rgba(0,0,0,0.35)] ring-1 ring-white/5 backdrop-blur sm:p-7">
                <div className="flex items-start justify-between gap-4 border-b border-border/80 pb-5">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      The review process
                    </p>
                    <h2 className="mt-2 text-xl font-semibold tracking-tight">
                      Opportunity, with context.
                    </h2>
                  </div>
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Shield className="h-5 w-5" />
                  </span>
                </div>

                <div className="space-y-1 py-4">
                  {reviewSteps.map((step, index) => (
                    <div key={step.number} className="relative flex gap-4 py-3">
                      {index < reviewSteps.length - 1 && (
                        <span className="absolute left-[17px] top-12 h-8 w-px bg-border" />
                      )}
                      <span className="z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-primary/15 bg-primary/5 text-[11px] font-bold text-primary">
                        {step.number}
                      </span>
                      <div className="min-w-0 pt-0.5">
                        <h3 className="text-sm font-semibold">{step.title}</h3>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-start gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-4">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                  <p className="text-xs leading-5 text-emerald-100">
                    Review status and application details stay visible, so you can make an informed
                    choice before leaving the platform.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="how-it-works" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-primary">
              Built around your search
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              Less noise. Better-informed next steps.
            </h2>
            <p className="mt-4 text-sm leading-6 text-muted-foreground sm:text-base">
              From finding an opening to deciding whether it fits, CyberScout keeps the important
              details together.
            </p>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {capabilities.map(({ icon: Icon, title, description }, index) => (
              <article
                key={title}
                className="rounded-2xl border border-border/80 bg-card p-6 shadow-[0_8px_24px_rgba(0,0,0,0.18)] transition-all hover:-translate-y-0.5 hover:shadow-md"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/8 text-primary">
                  <Icon className="h-5 w-5" />
                </span>
                <p className="mt-6 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  0{index + 1}
                </p>
                <h3 className="mt-2 text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="for-you" className="border-y border-border/70 bg-card/55">
          <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-8 px-4 py-12 sm:px-6 md:flex-row md:items-center lg:px-8">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 text-primary">
                <Compass className="h-4 w-4" />
                <p className="text-xs font-bold uppercase tracking-[0.14em]">Start exploring</p>
              </div>
              <h2 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
                Your next opportunity starts with a good search.
              </h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Create an account to browse the feed, save opportunities, and keep track of the
                listings you want to revisit.
              </p>
            </div>
            <Button asChild size="lg" className="shrink-0">
              <Link to="/register">
                Get started <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </section>
      </main>

      <footer className="bg-card">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-7 text-xs text-muted-foreground sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <Link to="/" className="flex items-center gap-2 font-semibold text-foreground">
            <Shield className="h-4 w-4 text-cyber-blue" />
            CyberScout AI
            <span className="font-normal text-muted-foreground">
              · Cybersecurity opportunity intelligence
            </span>
          </Link>
          <div className="flex items-center gap-5">
            <a href="#how-it-works" className="transition-colors hover:text-foreground">
              How it works
            </a>
            <Link to="/login" className="transition-colors hover:text-foreground">
              Sign in
            </Link>
            <Link to="/register" className="transition-colors hover:text-foreground">
              Create account
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
