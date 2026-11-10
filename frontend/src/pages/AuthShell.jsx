import { Logo } from "@/components/foundry/Logo";

export default function AuthShell({ children }) {
  return (
    <div className="relative grid min-h-screen bg-[#0B0F17] lg:grid-cols-2">
      <aside className="noise relative hidden flex-col justify-between overflow-hidden border-r border-[#1F2937] bg-[#0D131F] p-12 lg:flex">
        <div className="grid-bg absolute inset-0 opacity-60" />
        <div className="relative"><Logo /></div>
        <div className="relative">
          <p className="font-mono text-xs uppercase tracking-widest text-[#00F0FF]">// autonomous engineering</p>
          <h2 className="mt-4 font-display text-4xl font-extrabold leading-tight text-white">Describe it.<br />Foundry plans, builds,<br />tests and reviews it.</h2>
          <pre className="mt-8 rounded-lg border border-[#1F2937] bg-[#080C14] p-4 font-mono text-xs leading-6 text-slate-400">
{`> foundry new "habit tracker with streaks"
  ✓ plan          prd.md
  ✓ architecture  4 entities · 9 endpoints
  ✓ code          12 files
  ✓ tests         4 suites
  ● review        score 86 · 3 issues`}
          </pre>
        </div>
        <p className="relative font-mono text-[11px] text-slate-600">FoundryAI · build log v1</p>
      </aside>
      <main className="flex flex-col items-center justify-center gap-8 px-4 py-12">
        <div className="lg:hidden"><Logo /></div>
        {children}
      </main>
    </div>
  );
}
