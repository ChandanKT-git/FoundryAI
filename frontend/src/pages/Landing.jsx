import { Link } from "react-router-dom";
import { ArrowRight, Boxes, Code2, FileText, FlaskConical, ShieldCheck, MessageSquareCode, History, Download, MonitorPlay } from "lucide-react";
import { Logo } from "@/components/foundry/Logo";
import { MODELS, STAGES } from "@/lib/api";

const STAGE_ICONS = { plan: FileText, architecture: Boxes, code: Code2, tests: FlaskConical, review: ShieldCheck };
const FEATURES = [
  { icon: MonitorPlay, title: "Live preview", body: "Your app's interface runs in a sandboxed pane and refreshes after every change." },
  { icon: MessageSquareCode, title: "Chat to evolve", body: "Ask for changes in plain words. The agent explains, edits only what's needed, and shows the diff." },
  { icon: History, title: "Every change versioned", body: "Each agent edit is a snapshot. Inspect or restore any version in one click." },
  { icon: Download, title: "Own your code", body: "Browse the full file tree with syntax highlighting and download the project as a zip." },
];

const HeroTerminal = () => (
  <div className="rise relative rounded-xl border border-[#1F2937] bg-[#080C14] shadow-[0_0_80px_rgba(0,240,255,0.08)]" style={{ animationDelay: "200ms" }}>
    <div className="flex items-center gap-1.5 border-b border-[#1F2937] px-4 py-3">
      <span className="h-2.5 w-2.5 rounded-full bg-[#EF4444]/70" /><span className="h-2.5 w-2.5 rounded-full bg-[#F59E0B]/70" /><span className="h-2.5 w-2.5 rounded-full bg-[#10B981]/70" />
      <span className="ml-3 font-mono text-[11px] text-slate-500">foundry — studio-booking</span>
    </div>
    <div className="space-y-2 p-5 font-mono text-[12px] leading-6">
      <p className="text-slate-400"><span className="text-[#00F0FF]">❯</span> "A booking app for a small yoga studio"</p>
      {STAGES.map((s, i) => (
        <p key={s.id} className="rise flex items-center gap-3" style={{ animationDelay: `${500 + i * 280}ms` }}>
          <span style={{ color: s.color }}>{i < 4 ? "✓" : "●"}</span>
          <span className="w-24 text-slate-200">{s.label.toLowerCase()}</span>
          <span className="text-slate-500">{["prd.md · 6 user stories", "3 services · 5 entities", "13 files written", "4 suites · 31 cases", "score 88 · 2 fixes ready"][i]}</span>
        </p>
      ))}
      <p className="caret pt-2 text-slate-500">agent idle — awaiting your next request</p>
    </div>
  </div>
);

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100">
      <header className="sticky top-0 z-30 border-b border-[#1F2937]/70 bg-[#0B0F17]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <Logo />
          <div className="flex items-center gap-2">
            <Link to="/sign-in" data-testid="nav-sign-in" className="rounded-md px-3 py-2 text-sm text-slate-300 hover:text-white">Sign in</Link>
            <Link to="/sign-up" data-testid="nav-get-started" className="rounded-md bg-[#00F0FF] px-4 py-2 text-sm font-semibold text-[#0B0F17] transition-shadow hover:shadow-[0_0_20px_rgba(0,240,255,0.4)]">Start building</Link>
          </div>
        </div>
      </header>

      <section className="noise relative overflow-hidden">
        <div className="grid-bg absolute inset-0 opacity-40 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)]" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-5 py-20 sm:px-8 lg:grid-cols-[1.1fr_1fr] lg:py-28">
          <div className="rise">
            <p className="font-mono text-xs uppercase tracking-widest text-[#00F0FF]">// autonomous ai software engineer</p>
            <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
              From a sentence<br />to an <span className="text-[#00F0FF]">engineered</span> app.
            </h1>
            <p className="mt-6 max-w-xl text-base text-slate-400 md:text-lg">
              FoundryAI plans the product, designs the architecture, writes the code and tests, reviews its own work for bugs — then keeps evolving it as you chat.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link to="/sign-up" data-testid="hero-cta" className="group flex items-center gap-2 rounded-md bg-[#00F0FF] px-6 py-3 font-semibold text-[#0B0F17] transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-[0_0_28px_rgba(0,240,255,0.45)]">
                Build your first app <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <span className="font-mono text-xs text-slate-500">no code required</span>
            </div>
          </div>
          <HeroTerminal />
        </div>
      </section>

      <section className="border-t border-[#1F2937] py-20 lg:py-24">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <p className="font-mono text-xs uppercase tracking-widest text-slate-500">The pipeline</p>
          <h2 className="mt-3 max-w-2xl font-display text-2xl font-bold sm:text-3xl">Five engineering stages. Streaming live, every time.</h2>
          <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-[#1F2937] bg-[#1F2937] md:grid-cols-5">
            {STAGES.map((s, i) => {
              const I = STAGE_ICONS[s.id];
              return (
                <div key={s.id} data-testid={`landing-stage-${s.id}`} className="group bg-[#0D131F] p-6 transition-colors hover:bg-[#111827]">
                  <div className="flex items-center justify-between">
                    <I className="h-5 w-5 transition-transform group-hover:-translate-y-0.5" style={{ color: s.color }} />
                    <span className="font-mono text-[10px] text-slate-600">0{i + 1}</span>
                  </div>
                  <h3 className="mt-8 font-display text-lg font-bold">{s.label}</h3>
                  <p className="mt-1 text-sm text-slate-500">{s.sub}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="py-20 lg:py-24">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-8 lg:grid-cols-[1fr_1.4fr]">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-slate-500">Model choice</p>
            <h2 className="mt-3 font-display text-2xl font-bold sm:text-3xl">Pick the mind behind each build.</h2>
            <p className="mt-4 text-slate-400">Switch models per project, or per message in the agent chat.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {MODELS.map((m) => (
              <div key={m.id} data-testid={`landing-model-${m.id}`} className="rounded-lg border border-[#1F2937] bg-[#111827] p-5 transition-colors hover:border-[#00F0FF]/40">
                <p className="font-mono text-[10px] uppercase tracking-widest text-[#00F0FF]">{m.tag}</p>
                <p className="mt-2 font-display text-lg font-bold">{m.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-[#1F2937] py-20 lg:py-24">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 sm:grid-cols-2 sm:px-8 lg:grid-cols-4">
          {FEATURES.map(({ icon: I, title, body }) => (
            <div key={title}>
              <I className="h-5 w-5 text-[#00F0FF]" />
              <h3 className="mt-4 font-display font-bold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 pb-24 sm:px-8">
        <div className="noise relative mx-auto max-w-7xl overflow-hidden rounded-2xl border border-[#1F2937] bg-[#0D131F] px-8 py-14 sm:px-14">
          <div className="grid-bg absolute inset-0 opacity-50" />
          <div className="relative flex flex-wrap items-end justify-between gap-6">
            <h2 className="max-w-xl font-display text-3xl font-extrabold sm:text-4xl">Your idea is the spec. <span className="text-[#00F0FF]">Ship it.</span></h2>
            <Link to="/sign-up" data-testid="footer-cta" className="flex items-center gap-2 rounded-md bg-[#00F0FF] px-6 py-3 font-semibold text-[#0B0F17] hover:shadow-[0_0_28px_rgba(0,240,255,0.45)]">Create free account <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </div>
      </section>
      <footer className="border-t border-[#1F2937] py-8 text-center font-mono text-[11px] text-slate-600">FoundryAI — autonomous software engineering</footer>
    </div>
  );
}
