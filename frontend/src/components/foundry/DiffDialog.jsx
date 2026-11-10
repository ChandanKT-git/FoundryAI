import { useEffect, useState } from "react";
import { GitCompare, Loader2, RotateCcw } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { errMsg } from "@/lib/api";

const STATUS = { added: ["A", "text-emerald-400"], removed: ["D", "text-red-400"], modified: ["M", "text-amber-300"] };
const LINE = { "+": "bg-emerald-500/10 text-emerald-200", "-": "bg-red-500/10 text-red-200", " ": "text-slate-400" };

const RefSelect = ({ value, onChange, versions, testId }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger data-testid={testId} className="h-8 w-[170px] border-[#1F2937] bg-[#0B0F17] font-mono text-xs text-slate-200"><SelectValue /></SelectTrigger>
    <SelectContent className="border-[#1F2937] bg-[#111827] text-slate-200">
      <SelectItem value="current" className="font-mono text-xs focus:bg-[#1F293D] focus:text-white">Current files</SelectItem>
      {versions.map((v) => <SelectItem key={v.id} value={v.id} className="font-mono text-xs focus:bg-[#1F293D] focus:text-white">v{v.number} · {v.label.slice(0, 22)}</SelectItem>)}
    </SelectContent>
  </Select>
);

const FileDiff = ({ f }) => (
  <div data-testid={`diff-file-${f.path}`} className="overflow-hidden rounded-md border border-[#1F2937]">
    <div className="flex items-center gap-2 border-b border-[#1F2937] bg-[#111827] px-3 py-2 font-mono text-xs">
      <span className={STATUS[f.status][1]}>{STATUS[f.status][0]}</span>
      <span className="flex-1 truncate text-slate-200">{f.path}</span>
      <span className="text-emerald-400">+{f.additions}</span><span className="text-red-400">−{f.deletions}</span>
    </div>
    <div className="overflow-x-auto bg-[#080C14] scroll-thin">
      {f.hunks.map((h, i) => (
        <div key={i}>
          <p className="bg-[#00F0FF]/5 px-3 py-1 font-mono text-[11px] text-[#00F0FF]/70">{h.header}</p>
          {h.lines.map((l, k) => (
            <div key={k} className={`flex font-mono text-[12px] leading-5 ${LINE[l.t]}`}>
              <span className="w-10 shrink-0 select-none pr-2 text-right text-slate-700">{l.o ?? ""}</span>
              <span className="w-10 shrink-0 select-none pr-2 text-right text-slate-700">{l.n ?? ""}</span>
              <span className="w-4 shrink-0 select-none">{l.t}</span>
              <span className="whitespace-pre pr-6">{l.s}</span>
            </div>
          ))}
        </div>
      ))}
      {f.truncated && <p className="px-3 py-2 font-mono text-[11px] text-slate-500">Diff truncated — file too large to show fully.</p>}
      {!f.hunks.length && <p className="px-3 py-2 font-mono text-[11px] text-slate-500">{f.status === "modified" ? "Only whitespace or the trailing newline changed." : "Empty file."}</p>}
    </div>
  </div>
);

export const DiffDialog = ({ open, onOpenChange, api, project, versions, initialBase, initialTarget, onRestore, restoring }) => {
  const [base, setBase] = useState(initialBase);
  const [target, setTarget] = useState(initialTarget);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { setBase(initialBase); setTarget(initialTarget); }, [initialBase, initialTarget]);
  useEffect(() => {
    if (!open || !base || !target) return;
    setData(null); setError(null);
    api.get(`/projects/${project.id}/diff`, { params: { base, target } }).then((r) => setData(r.data)).catch((e) => setError(errMsg(e)));
  }, [open, base, target, api, project.id]);

  const restoreTarget = base === "current" && target !== "current" ? versions.find((v) => v.id === target) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="diff-dialog" className="flex h-[88vh] max-w-6xl flex-col gap-3 border-[#1F2937] bg-[#0D131F] p-4 text-slate-100 sm:p-6">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-white"><GitCompare className="h-4 w-4 text-[#00F0FF]" /> Compare versions</DialogTitle>
          <DialogDescription className="text-xs text-slate-400">Green lines appear in “To”, red lines exist only in “From”.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">From</span>
          <RefSelect value={base} onChange={setBase} versions={versions} testId="diff-base-select" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">To</span>
          <RefSelect value={target} onChange={setTarget} versions={versions} testId="diff-target-select" />
          {data && <span data-testid="diff-summary" className="font-mono text-xs text-slate-400">{data.files.length} file(s) · <span className="text-emerald-400">+{data.additions}</span> <span className="text-red-400">−{data.deletions}</span></span>}
          {restoreTarget && (
            <button data-testid="diff-restore-button" disabled={project.busy || restoring} onClick={() => onRestore(restoreTarget)}
              className="ml-auto flex h-8 items-center gap-1.5 rounded-md bg-[#00F0FF] px-3 text-xs font-semibold text-[#0B0F17] disabled:opacity-40">
              {restoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />} Restore v{restoreTarget.number}
            </button>
          )}
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1 scroll-thin">
          {error && <p className="font-mono text-xs text-red-400">{error}</p>}
          {!data && !error && <p className="flex items-center gap-2 font-mono text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Computing diff…</p>}
          {data && data.files.length === 0 && <p data-testid="diff-identical" className="font-mono text-xs text-slate-500">No differences — these versions are identical.</p>}
          {data?.files.map((f) => <FileDiff key={f.path} f={f} />)}
        </div>
      </DialogContent>
    </Dialog>
  );
};
