import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Download, RotateCw, AlertTriangle } from "lucide-react";
import { StatusBadge } from "@/components/foundry/StatusBadge";
import { ModelSelect } from "@/components/foundry/ModelSelect";
import { StageRail } from "@/components/foundry/StageRail";
import { FileTree } from "@/components/foundry/FileTree";
import { CodeViewer } from "@/components/foundry/CodeViewer";
import { Markdown } from "@/components/foundry/Markdown";
import { LivePreview } from "@/components/foundry/LivePreview";
import { ReviewPanel } from "@/components/foundry/ReviewPanel";
import { PipelineStream } from "@/components/foundry/PipelineStream";
import { ChatPanel } from "@/components/foundry/ChatPanel";
import { VersionDrawer } from "@/components/foundry/VersionDrawer";
import { TestsPanel } from "@/components/foundry/TestsPanel";
import { useApi, errMsg } from "@/lib/api";
import { downloadZip } from "@/lib/files";

const TABS = ["pipeline", "plan", "architecture", "code", "preview", "tests", "review"];
const MOBILE = ["files", "main", "chat"];

export default function Workspace() {
  const { id } = useParams();
  const api = useApi();
  const [p, setP] = useState(null);
  const [messages, setMessages] = useState([]);
  const [tab, setTab] = useState(null);
  const [stage, setStage] = useState("plan");
  const [file, setFile] = useState(null);
  const [pane, setPane] = useState("main");
  const [fixing, setFixing] = useState(null);
  const [missing, setMissing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [{ data }, m] = await Promise.all([api.get(`/projects/${id}`), api.get(`/projects/${id}/messages`)]);
      setP(data);
      setMessages(m.data);
      return data;
    } catch (e) {
      if (e?.response?.status === 404) setMissing(true);
      else toast.error(errMsg(e));
    }
  }, [api, id]);

  useEffect(() => { load().then((d) => d && setTab((cur) => cur || (d.busy && !d.files.length ? "pipeline" : d.files.some((f) => f.path === "preview.html") ? "preview" : "pipeline"))); }, [load]);
  useEffect(() => {
    if (!p?.busy) return;
    const t = setInterval(load, 1200);
    return () => clearInterval(t);
  }, [p?.busy, load]);
  useEffect(() => { if (p?.live?.stage) setStage(p.live.stage); }, [p?.live?.stage]);
  useEffect(() => { if (!p?.busy) setFixing(null); }, [p?.busy]);

  if (missing) return <div className="grid min-h-screen place-items-center bg-[#0B0F17] text-slate-400"><Link to="/dashboard" className="font-mono text-sm text-[#00F0FF]">Project not found — back to dashboard</Link></div>;
  if (!p) return <div className="grid min-h-screen place-items-center bg-[#0B0F17] font-mono text-xs text-slate-500">Loading workspace…</div>;

  const current = p.files.find((f) => f.path === file) || null;
  const openFile = (path) => { setFile(path); setTab("code"); setPane("main"); };
  const changeModel = async (model) => {
    try { await api.patch(`/projects/${id}/model`, { model }); setP({ ...p, model }); toast.success("Project model updated"); } catch (e) { toast.error(errMsg(e)); }
  };
  const resume = async () => { try { await api.post(`/projects/${id}/resume`); setTab("pipeline"); load(); } catch (e) { toast.error(errMsg(e)); } };
  const fix = async (issue) => {
    setFixing(issue.id);
    try { await api.post(`/projects/${id}/issues/${issue.id}/fix`, {}); toast.success("Agent is applying the fix"); setPane("chat"); load(); }
    catch (e) { toast.error(errMsg(e)); setFixing(null); }
  };
  const download = async () => { await downloadZip(p.name, p.files); toast.success("Project downloaded"); };
  const wire = async () => {
    try {
      await api.post(`/projects/${id}/chat`, { message: "Wire preview.html to the live backend: when window.FOUNDRY_API_BASE is defined, load and save all data through the backend's real /api routes with fetch (with loading and error states); keep the in-memory mock data as the fallback when it is undefined." });
      toast.success("Agent is wiring the preview to your live API");
      setPane("chat");
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const main = {
    pipeline: <PipelineStream project={p} stage={stage} api={api} />,
    plan: <Markdown text={p.plan} testId="plan-view" empty="The plan is being written…" />,
    architecture: <Markdown text={p.architecture} testId="architecture-view" empty="Architecture comes after the plan." />,
    code: <CodeViewer file={current || p.files[0]} />,
    preview: <LivePreview project={p} api={api} onWire={wire} />,
    tests: <TestsPanel project={p} api={api} onStarted={load} />,
    review: <ReviewPanel review={p.review} busy={p.busy} onFix={fix} fixing={fixing} />,
  }[tab || "pipeline"];

  return (
    <div className="flex h-screen flex-col bg-[#0B0F17]">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[#1F2937] bg-[#0D131F] px-3 sm:px-4">
        <Link to="/dashboard" data-testid="back-to-dashboard" className="rounded p-1.5 text-slate-400 hover:bg-[#1F293D] hover:text-white"><ArrowLeft className="h-4 w-4" /></Link>
        <h1 data-testid="project-name" className="min-w-0 truncate font-display text-sm font-bold text-white sm:text-base">{p.name}</h1>
        <StatusBadge status={p.status} busy={p.busy} testId="project-status" />
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden md:block"><ModelSelect compact value={p.model} onChange={changeModel} testId="project-model-select" /></div>
          <VersionDrawer project={p} api={api} onRestored={load} />
          <button data-testid="download-zip-button" onClick={download} disabled={!p.files.length}
            className="flex h-8 items-center gap-1.5 rounded-md bg-[#00F0FF] px-3 text-xs font-semibold text-[#0B0F17] disabled:opacity-30">
            <Download className="h-3.5 w-3.5" /><span className="hidden sm:inline">Download</span>
          </button>
        </div>
      </header>

      <div className="shrink-0 border-b border-[#1F2937] px-2 py-1.5">
        <StageRail stageStatus={p.stage_status} selected={tab === "pipeline" ? stage : null} onSelect={(s) => { setStage(s); setTab("pipeline"); setPane("main"); }} />
      </div>
      {p.error && (
        <div data-testid="pipeline-error" className="flex shrink-0 items-center gap-3 border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-300">
          <AlertTriangle className="h-4 w-4 shrink-0" /><span className="flex-1 truncate">{p.error}</span>
          {!p.busy && <button data-testid="retry-pipeline-button" onClick={resume} className="flex items-center gap-1 rounded border border-red-400/40 px-2 py-1 font-mono hover:bg-red-500/20"><RotateCw className="h-3 w-3" /> Retry</button>}
        </div>
      )}

      <div className="flex shrink-0 border-b border-[#1F2937] lg:hidden">
        {MOBILE.map((m) => (
          <button key={m} data-testid={`mobile-pane-${m}`} onClick={() => setPane(m)}
            className={`flex-1 py-2 font-mono text-[11px] uppercase tracking-widest ${pane === m ? "border-b-2 border-[#00F0FF] text-white" : "text-slate-500"}`}>{m === "main" ? "Workspace" : m}</button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1">
        <aside className={`${pane === "files" ? "flex" : "hidden"} w-full shrink-0 flex-col border-r border-[#1F2937] bg-[#0D131F] lg:flex lg:w-[260px]`}>
          <p className="border-b border-[#1F2937] px-4 py-2.5 font-mono text-[10px] uppercase tracking-widest text-slate-400">Explorer · {p.files.length}</p>
          <div className="flex-1 overflow-y-auto scroll-thin"><FileTree files={p.files} selected={current?.path} onSelect={openFile} /></div>
        </aside>
        <section className={`${pane === "main" ? "flex" : "hidden"} min-w-0 flex-1 flex-col lg:flex`}>
          <nav className="flex shrink-0 overflow-x-auto border-b border-[#1F2937] bg-[#0D131F] scroll-thin">
            {TABS.map((t) => (
              <button key={t} data-testid={`workspace-tab-${t}`} onClick={() => setTab(t)}
                className={`shrink-0 border-r border-[#1F2937] px-4 py-2.5 font-mono text-[11px] uppercase tracking-widest transition-colors ${tab === t ? "bg-[#0B0F17] text-white shadow-[inset_0_2px_0_#00F0FF]" : "text-slate-500 hover:text-slate-200"}`}>
                {t}{t === "review" && p.review ? ` · ${p.review.issues.filter((i) => i.status !== "fixed").length}` : ""}
                {t === "tests" && p.test_summary ? <span className={p.test_summary.version < p.version_count ? "text-slate-500" : p.test_summary.status === "passed" ? "text-emerald-400" : "text-red-400"} title={p.test_summary.version < p.version_count ? "Code changed since the last run" : ""}>{` · ${p.test_summary.passed}/${p.test_summary.passed + p.test_summary.failed}${p.test_summary.version < p.version_count ? " stale" : ""}`}</span> : ""}
              </button>
            ))}
          </nav>
          <div className="min-h-0 flex-1 overflow-y-auto scroll-thin">{main}</div>
        </section>
        <aside className={`${pane === "chat" ? "flex" : "hidden"} w-full shrink-0 flex-col border-l border-[#1F2937] bg-[#0D131F] lg:flex lg:w-[360px]`}>
          <ChatPanel project={p} messages={messages} api={api} onSent={load} />
        </aside>
      </div>
    </div>
  );
}
