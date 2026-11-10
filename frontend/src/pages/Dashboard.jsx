import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { UserButton } from "@clerk/react";
import { toast } from "sonner";
import { Plus, Search, Trash2, FileCode2 } from "lucide-react";
import { Logo } from "@/components/foundry/Logo";
import { StatusBadge } from "@/components/foundry/StatusBadge";
import { NewProjectDialog } from "@/components/foundry/NewProjectDialog";
import { useApi, errMsg, modelLabel, timeAgo, STAGES } from "@/lib/api";

const ProjectCard = ({ p, onDelete }) => (
  <Link to={`/p/${p.id}`} data-testid={`project-card-${p.id}`} className="group relative flex flex-col rounded-lg border border-[#1F2937] bg-[#111827] p-5 transition-[border-color,transform] hover:-translate-y-0.5 hover:border-[#374151]">
    <div className="flex items-start justify-between gap-3">
      <h3 className="font-display text-base font-bold text-white">{p.name}</h3>
      <StatusBadge status={p.status} busy={p.busy} testId={`project-status-${p.id}`} />
    </div>
    <p className="mt-2 line-clamp-2 text-sm text-slate-400">{p.idea}</p>
    <div className="mt-5 flex gap-1">
      {STAGES.map((s) => {
        const st = p.stage_status[s.id];
        return <span key={s.id} className={`h-1 flex-1 rounded-full ${st === "running" ? "animate-pulse" : ""}`} style={{ background: st === "done" || st === "running" ? s.color : st === "failed" ? "#EF4444" : "#1F2937" }} />;
      })}
    </div>
    <div className="mt-4 flex items-center gap-3 pr-7 font-mono text-[11px] text-slate-500">
      <span className="rounded border border-[#1F2937] px-1.5 py-0.5 text-slate-400">{modelLabel(p.model)}</span>
      <span className="flex items-center gap-1"><FileCode2 className="h-3 w-3" />{p.file_count}</span>
      {p.score != null && <span className="text-emerald-400">score {p.score}</span>}
      {p.test_summary && <span data-testid={`project-tests-${p.id}`} className={p.test_summary.version < p.version_count ? "text-slate-500" : p.test_summary.status === "passed" ? "text-emerald-400" : "text-red-400"}>tests {p.test_summary.passed}/{p.test_summary.passed + p.test_summary.failed}{p.test_summary.version < p.version_count ? " · stale" : ""}</span>}
      <span className="ml-auto">{timeAgo(p.updated_at)}</span>
    </div>
    <button data-testid={`delete-project-${p.id}`} onClick={(e) => { e.preventDefault(); onDelete(p); }}
      className="absolute bottom-4 right-3 rounded p-1 text-slate-600 hover:bg-red-500/10 hover:text-red-400 lg:opacity-0 lg:group-hover:opacity-100">
      <Trash2 className="h-3.5 w-3.5" />
    </button>
  </Link>
);

export default function Dashboard() {
  const api = useApi();
  const [projects, setProjects] = useState(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  const load = useCallback(() => api.get("/projects").then((r) => setProjects(r.data)).catch((e) => toast.error(errMsg(e))), [api]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!projects?.some((p) => p.busy)) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [projects, load]);

  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.name}"? This cannot be undone.`)) return;
    try { await api.delete(`/projects/${p.id}`); toast.success("Project deleted"); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const list = (projects || []).filter((p) => `${p.name} ${p.idea}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="min-h-screen bg-[#0B0F17]">
      <header className="border-b border-[#1F2937] bg-[#0D131F]">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-5 sm:px-8">
          <Logo to="/dashboard" small />
          <div data-testid="user-menu"><UserButton /></div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 lg:py-14">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="font-mono text-xs uppercase tracking-widest text-slate-500">Workspace</p>
            <h1 className="mt-2 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">Your projects</h1>
          </div>
          <div className="flex w-full gap-3 sm:w-auto">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-600" />
              <input data-testid="project-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search projects"
                className="h-10 w-full rounded-md border border-[#1F2937] bg-[#111827] pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00F0FF]/50 focus:outline-none" />
            </div>
            <button data-testid="new-project-button" onClick={() => setOpen(true)}
              className="flex h-10 items-center gap-2 rounded-md bg-[#00F0FF] px-4 text-sm font-semibold text-[#0B0F17] transition-shadow hover:shadow-[0_0_20px_rgba(0,240,255,0.4)]">
              <Plus className="h-4 w-4" /> New project
            </button>
          </div>
        </div>

        {projects && projects.length === 0 ? (
          <button data-testid="empty-new-project" onClick={() => setOpen(true)}
            className="mt-12 flex w-full flex-col items-start rounded-xl border border-dashed border-[#374151] p-10 text-left transition-colors hover:border-[#00F0FF]/50">
            <span className="font-mono text-xs text-[#00F0FF]">❯ foundry new</span>
            <span className="mt-3 font-display text-xl font-bold text-white">Describe your first app idea</span>
            <span className="mt-1 text-sm text-slate-400">The agent will plan, architect, code, test and review it — live.</span>
          </button>
        ) : (
          <div data-testid="project-grid" className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {projects === null && [0, 1, 2].map((i) => <div key={i} className="h-44 animate-pulse rounded-lg border border-[#1F2937] bg-[#111827]" />)}
            {list.map((p) => <ProjectCard key={p.id} p={p} onDelete={remove} />)}
          </div>
        )}
      </main>
      <NewProjectDialog open={open} onOpenChange={setOpen} />
    </div>
  );
}
