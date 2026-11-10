import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Loader2, Monitor, MonitorSmartphone, Play, PlugZap, RotateCw, Square, Terminal } from "lucide-react";
import { errMsg } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const PILL = {
  running: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10", starting: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  crashed: "text-red-300 border-red-500/40 bg-red-500/10", failed: "text-red-300 border-red-500/40 bg-red-500/10",
  stopped: "text-slate-400 border-slate-600 bg-slate-500/10", idle: "text-slate-400 border-slate-600 bg-slate-500/10",
};
const LABEL = { running: "API live", starting: "starting", crashed: "crashed", failed: "failed", stopped: "API off", idle: "API off" };

const injectBase = (html, base) => {
  const tag = `<script>window.FOUNDRY_API_BASE=window.FORGE_API_BASE=${JSON.stringify(base)};</script>`;
  return /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + tag) : tag + html;
};

const IconBtn = ({ testId, onClick, children, title, disabled }) => (
  <button data-testid={testId} title={title} onClick={onClick} disabled={disabled} className="rounded p-1.5 text-slate-400 hover:bg-[#1F293D] hover:text-white disabled:opacity-30">{children}</button>
);

export const LivePreview = ({ project, api, onWire }) => {
  const [rt, setRt] = useState({ status: "idle" });
  const [mode, setMode] = useState("live");
  const [logs, setLogs] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [acting, setActing] = useState(false);
  const html = project.files.find((f) => f.path === "preview.html")?.content;

  const load = useCallback(() => api.get(`/projects/${project.id}/runtime`).then((r) => setRt(r.data)).catch(() => {}), [api, project.id]);
  useEffect(() => { load(); }, [load, project.version_count]);
  useEffect(() => { if (rt.status === "crashed" || rt.status === "failed") setLogs(true); }, [rt.status]);
  useEffect(() => {
    if (!(rt.status === "starting" || rt.stale || (rt.status === "running" && logs))) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [rt.status, rt.stale, logs, load]);

  const act = async (what) => {
    setActing(true);
    if (what === "start") setRt((r) => ({ ...r, status: "starting" }));
    try {
      const { data } = await api.post(`/projects/${project.id}/runtime/${what}`);
      setRt(data);
      if (what === "start") data.status === "running" ? toast.success("Live backend is running") : toast.error(data.error || "Backend failed to start");
    } catch (e) { toast.error(errMsg(e)); load(); }
    setActing(false);
  };

  if (!html) return <p data-testid="preview-empty" className="p-8 font-mono text-xs text-slate-600">The live preview appears once the code stage finishes.</p>;
  const running = rt.status === "running";
  const base = running ? `${BACKEND_URL}${rt.base_path}` : null;
  const live = running && mode === "live";
  const wired = html.includes("FOUNDRY_API_BASE") || html.includes("FORGE_API_BASE");
  const doc = live ? injectBase(html, base) : html;

  return (
    <div data-testid="preview-pane" className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#1F2937] px-3 py-2">
        <span data-testid="runtime-status" className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ${PILL[rt.status] || PILL.idle}`}>
          {rt.status === "starting" ? <Loader2 className="h-3 w-3 animate-spin" /> : <span className={`h-1.5 w-1.5 rounded-full bg-current ${running ? "animate-pulse" : ""}`} />}
          {LABEL[rt.status] || rt.status}{rt.stale ? " · restarting" : ""}
        </span>
        {running ? (
          <>
            <button data-testid="runtime-stop-button" onClick={() => act("stop")} disabled={acting} className="flex items-center gap-1 rounded border border-[#1F2937] px-2 py-1 font-mono text-[11px] text-slate-300 hover:text-white disabled:opacity-40"><Square className="h-3 w-3" /> Stop</button>
            <div className="flex overflow-hidden rounded border border-[#1F2937] font-mono text-[10px] uppercase tracking-widest">
              {["live", "mock"].map((m) => (
                <button key={m} data-testid={`preview-mode-${m}`} onClick={() => setMode(m)} className={`px-2 py-1 ${mode === m ? "bg-[#00F0FF]/15 text-[#00F0FF]" : "text-slate-500 hover:text-white"}`}>{m === "live" ? "Live API" : "Mock"}</button>
              ))}
            </div>
            <button data-testid="copy-api-base" onClick={() => { navigator.clipboard.writeText(base); toast.success("API base URL copied"); }} className="hidden max-w-[260px] items-center gap-1 truncate font-mono text-[10px] text-slate-500 hover:text-white xl:flex"><Copy className="h-3 w-3 shrink-0" />{rt.entry}</button>
          </>
        ) : (
          <button data-testid="runtime-start-button" onClick={() => act("start")} disabled={acting || rt.status === "starting"}
            className="flex items-center gap-1.5 rounded-md bg-[#10B981] px-2.5 py-1 text-[11px] font-semibold text-[#0B0F17] disabled:opacity-50">
            {acting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} {rt.status === "crashed" || rt.status === "failed" ? "Retry backend" : "Start live backend"}
          </button>
        )}
        <span className="flex-1" />
        <IconBtn testId="runtime-logs-toggle" title="Backend logs" onClick={() => { setLogs(!logs); load(); }}><Terminal className={`h-3.5 w-3.5 ${logs ? "text-[#00F0FF]" : ""}`} /></IconBtn>
        <IconBtn testId="preview-device-toggle" title="Device size" onClick={() => setMobile(!mobile)}>{mobile ? <Monitor className="h-3.5 w-3.5" /> : <MonitorSmartphone className="h-3.5 w-3.5" />}</IconBtn>
        <IconBtn testId="preview-reload-button" title="Reload" onClick={() => setNonce(nonce + 1)}><RotateCw className="h-3.5 w-3.5" /></IconBtn>
      </div>
      {rt.error && <p data-testid="runtime-error" className="border-b border-red-500/30 bg-red-500/10 px-4 py-1.5 text-xs text-red-300">{rt.error}</p>}
      {running && !wired && (
        <div data-testid="preview-mock-banner" className="flex flex-wrap items-center gap-3 border-b border-amber-500/30 bg-amber-500/5 px-4 py-1.5 text-xs text-amber-200">
          <span className="flex-1">The backend is live, but this preview still uses mock data.</span>
          <button data-testid="wire-preview-button" onClick={onWire} disabled={project.busy}
            className="flex items-center gap-1 rounded border border-amber-400/40 px-2 py-0.5 font-mono text-[11px] hover:bg-amber-500/10 disabled:opacity-40"><PlugZap className="h-3 w-3" /> Wire preview to live API</button>
        </div>
      )}
      <div className="flex min-h-0 flex-1 justify-center overflow-auto bg-[#080C14] p-3">
        <iframe key={`${project.version_count}-${nonce}-${live ? rt.started_at : "mock"}`} title="Live preview" data-testid="preview-iframe" srcDoc={doc}
          sandbox="allow-scripts allow-forms allow-modals allow-popups"
          className={`h-full rounded-md border border-[#1F2937] bg-white transition-[width] duration-300 ${mobile ? "w-[390px]" : "w-full"}`} />
      </div>
      {logs && (
        <pre data-testid="runtime-logs" className="h-44 shrink-0 overflow-auto whitespace-pre-wrap border-t border-[#1F2937] bg-[#05080E] p-3 font-mono text-[11px] text-slate-400 scroll-thin">
          {rt.logs || "No backend logs yet. Start the live backend to see its output."}
        </pre>
      )}
    </div>
  );
};
