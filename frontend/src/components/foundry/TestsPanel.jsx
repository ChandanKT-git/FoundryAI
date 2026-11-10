import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { CheckCircle2, ChevronDown, CircleSlash, FlaskConical, Loader2, Play, ShieldCheck, Wrench, XCircle } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { errMsg, timeAgo } from "@/lib/api";

const CASE = {
  passed: [CheckCircle2, "text-emerald-400"], failed: [XCircle, "text-red-400"],
  error: [XCircle, "text-orange-400"], skipped: [CircleSlash, "text-slate-500"],
};
const RUN = { passed: "text-emerald-300 border-emerald-500/30 bg-emerald-500/10", failed: "text-red-300 border-red-500/30 bg-red-500/10",
  error: "text-orange-300 border-orange-500/30 bg-orange-500/10", running: "text-amber-300 border-amber-500/30 bg-amber-500/10",
  no_tests: "text-slate-300 border-slate-500/30 bg-slate-500/10" };

const Case = ({ c }) => {
  const [open, setOpen] = useState(false);
  const [Icon, color] = CASE[c.status] || CASE.error;
  return (
    <div data-testid={`test-case-${c.status}`} className="border-b border-[#1F2937] last:border-0">
      <button onClick={() => c.message && setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-[#111827]">
        <Icon className={`h-3.5 w-3.5 shrink-0 ${color}`} />
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-slate-200">{c.name}</span>
        <span className="hidden truncate font-mono text-[10px] text-slate-600 sm:block sm:max-w-[40%]">{c.file}</span>
        {c.message && <ChevronDown className={`h-3 w-3 text-slate-600 transition-transform ${open ? "rotate-180" : ""}`} />}
      </button>
      {open && <pre className="max-h-64 overflow-auto whitespace-pre-wrap bg-[#080C14] px-4 py-2 font-mono text-[11px] text-slate-400 scroll-thin">{c.message}</pre>}
    </div>
  );
};

const order = { failed: 0, error: 1, passed: 2, skipped: 3 };

const Attempt = ({ a }) => {
  const [showOut, setShowOut] = useState(false);
  const cases = [...a.cases].sort((x, y) => order[x.status] - order[y.status]);
  return (
    <div data-testid={`test-attempt-${a.n}`} className="relative border-l border-[#1F2937] pb-6 pl-5">
      <span className={`absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full ${a.failed + a.errors ? "bg-red-400" : "bg-emerald-400"}`} />
      <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
        <span className="uppercase tracking-widest text-slate-500">Attempt {a.n}</span>
        <span className="text-emerald-400">{a.passed} passed</span>
        <span className="text-red-400">{a.failed + a.errors} failed</span>
        <span className="text-slate-500">{a.skipped} skipped</span>
        <span className="text-slate-600">{a.duration}s</span>
        <button data-testid={`toggle-output-${a.n}`} onClick={() => setShowOut(!showOut)} className="ml-auto text-slate-500 hover:text-white">{showOut ? "hide" : "raw"} output</button>
      </div>
      <div className="mt-2 overflow-hidden rounded-md border border-[#1F2937] bg-[#0D131F]">
        {cases.length ? cases.map((c, i) => <Case key={i} c={c} />) : <p className="px-3 py-2 font-mono text-xs text-slate-500">No test cases found.</p>}
      </div>
      {showOut && <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-[#1F2937] bg-[#080C14] p-3 font-mono text-[11px] text-slate-400 scroll-thin">{a.output}</pre>}
      {a.fix && (
        <div data-testid={`test-fix-${a.n}`} className="mt-3 rounded-md border border-[#00F0FF]/30 bg-[#00F0FF]/5 p-3">
          <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[#00F0FF]"><Wrench className="h-3 w-3" /> Agent fix · saved as v{a.fix.version}</p>
          <div className="md mt-1.5 text-[13px]"><ReactMarkdown>{a.fix.explanation}</ReactMarkdown></div>
          <p className="mt-1.5 font-mono text-[11px] text-slate-500">{a.fix.changed_files.join(" · ")}</p>
        </div>
      )}
    </div>
  );
};

export const TestsPanel = ({ project, api, onStarted }) => {
  const [runs, setRuns] = useState([]);
  const [autoFix, setAutoFix] = useState(true);
  const [starting, setStarting] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => api.get(`/projects/${project.id}/tests/runs`).then((r) => setRuns(r.data)).catch(() => {}), [api, project.id]);
  useEffect(() => { load(); }, [load, project.busy, project.version_count]);
  const running = runs[0]?.status === "running";
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [running, load]);

  const start = async () => {
    setStarting(true);
    try { await api.post(`/projects/${project.id}/tests/run`, { auto_fix: autoFix, max_attempts: 3 }); setSelected(null); await load(); onStarted(); toast.success("Tests started in the sandbox"); }
    catch (e) { toast.error(errMsg(e)); }
    setStarting(false);
  };

  const run = runs.find((r) => r.id === selected) || runs[0];

  return (
    <div data-testid="tests-panel" className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-[#1F2937] bg-[#111827] p-4">
        <FlaskConical className="h-5 w-5 text-amber-400" />
        <div className="min-w-0 flex-1">
          <p className="font-display text-sm font-bold text-white">Sandboxed test runner</p>
          <p className="text-xs text-slate-400">Runs pytest and plain Node tests in an isolated, network-less sandbox. Jest / React Testing Library files are listed as skipped.</p>
        </div>
        <label className="flex items-center gap-2 font-mono text-[11px] text-slate-300">
          <Switch data-testid="auto-fix-switch" checked={autoFix} onCheckedChange={setAutoFix} /> Auto-fix (up to 3 attempts)
        </label>
        <button data-testid="run-tests-button" onClick={start} disabled={starting || project.busy || !project.files.length}
          className="flex h-9 items-center gap-2 rounded-md bg-[#00F0FF] px-4 text-sm font-semibold text-[#0B0F17] transition-shadow hover:shadow-[0_0_20px_rgba(0,240,255,0.35)] disabled:opacity-40">
          {starting || running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Run tests
        </button>
      </div>

      {runs.length > 1 && (
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1 scroll-thin">
          {runs.map((r, i) => (
            <button key={r.id} data-testid={`test-run-tab-${i}`} onClick={() => setSelected(r.id)}
              className={`shrink-0 rounded border px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest ${run?.id === r.id ? RUN[r.status] : "border-[#1F2937] text-slate-500 hover:text-white"}`}>
              {r.status} · {timeAgo(r.created_at)}
            </button>
          ))}
        </div>
      )}

      {!run && <p data-testid="tests-empty" className="mt-8 font-mono text-xs text-slate-600">No test runs yet. Press “Run tests” to execute this project's tests.</p>}
      {run && (
        <div className="mt-6">
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <span data-testid="test-run-status" className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-widest ${RUN[run.status]}`}>
              {run.status === "running" ? <Loader2 className="h-3 w-3 animate-spin" /> : run.status === "passed" ? <ShieldCheck className="h-3 w-3" /> : null}
              {run.status === "no_tests" ? "no runnable tests" : run.status}
            </span>
            {run.phase && <span data-testid="test-run-phase" className="font-mono text-xs text-amber-300">{run.phase}</span>}
            {run.note && <span className="text-xs text-orange-300">{run.note}</span>}
          </div>
          {run.status !== "running" && project.test_summary?.run_id === run.id && project.test_summary.version < project.version_count && (
            <p data-testid="tests-stale-note" className="mb-4 font-mono text-[11px] text-slate-500">Code changed since this run (now v{project.version_count}). Run the tests again to check the latest version.</p>
          )}
          {run.live_fix != null && (
            <pre data-testid="test-live-fix" className="caret mb-5 max-h-60 overflow-auto whitespace-pre-wrap rounded-md border border-[#1F2937] bg-[#080C14] p-3 font-mono text-[11px] text-slate-300 scroll-thin">{run.live_fix.split("<<<FILE")[0]}</pre>
          )}
          {[...run.attempts].reverse().map((a) => <Attempt key={a.n} a={a} />)}
        </div>
      )}
    </div>
  );
};
