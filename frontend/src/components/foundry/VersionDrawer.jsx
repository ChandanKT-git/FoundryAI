import { useEffect, useState } from "react";
import { toast } from "sonner";
import { History, RotateCcw, Eye, Loader2, GitCompare } from "lucide-react";
import { DiffDialog } from "./DiffDialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { errMsg, timeAgo } from "@/lib/api";

export const VersionDrawer = ({ project, api, onRestored }) => {
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [viewing, setViewing] = useState(null);
  const [restoring, setRestoring] = useState(null);
  const [compare, setCompare] = useState(null);

  useEffect(() => {
    if (open) api.get(`/projects/${project.id}/versions`).then((r) => setVersions(r.data)).catch(() => {});
  }, [open, project.version_count, project.id, api]);

  const view = async (v) => {
    if (viewing?.id === v.id) return setViewing(null);
    const { data } = await api.get(`/projects/${project.id}/versions/${v.id}`);
    setViewing(data);
  };

  const restore = async (v) => {
    setRestoring(v.id);
    try {
      const { data } = await api.post(`/projects/${project.id}/versions/${v.id}/restore`);
      toast.success(`Restored v${v.number} as v${data.version}`);
      setCompare(null);
      onRestored();
    } catch (e) { toast.error(errMsg(e)); }
    setRestoring(null);
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button data-testid="version-history-button" className="flex h-8 items-center gap-1.5 rounded-md border border-[#1F2937] px-2.5 font-mono text-xs text-slate-300 hover:bg-[#1F293D] hover:text-white">
          <History className="h-3.5 w-3.5" /><span className="hidden sm:inline">v{project.version_count || 0}</span>
        </button>
      </SheetTrigger>
      <SheetContent data-testid="version-drawer" className="w-full overflow-y-auto border-[#1F2937] bg-[#0D131F] text-slate-100 sm:max-w-md scroll-thin">
        <SheetHeader><SheetTitle className="font-display text-white">Version history</SheetTitle></SheetHeader>
        <div className="mt-6 space-y-0 border-l border-[#1F2937] pl-5">
          {versions.length === 0 && <p className="font-mono text-xs text-slate-600">No versions yet.</p>}
          {versions.map((v, idx) => (
            <div key={v.id} data-testid={`version-${v.number}`} className="relative pb-5">
              <span className={`absolute -left-[26px] top-1 h-2.5 w-2.5 rounded-full ring-4 ring-[#0D131F] ${idx === 0 ? "bg-[#00F0FF]" : "bg-slate-600"}`} />
              <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">v{v.number} · {timeAgo(v.created_at)} · {v.file_count} files</p>
              <p className="mt-1 text-sm text-slate-200">{v.label}</p>
              <div className="mt-2 flex gap-2">
                <button data-testid={`version-view-${v.number}`} onClick={() => view(v)} className="flex items-center gap-1 rounded border border-[#1F2937] px-2 py-1 font-mono text-[11px] text-slate-400 hover:text-white">
                  <Eye className="h-3 w-3" /> {viewing?.id === v.id ? "Hide" : "Files"}
                </button>
                <button data-testid={`version-compare-${v.number}`} onClick={() => setCompare(v.id)} className="flex items-center gap-1 rounded border border-[#1F2937] px-2 py-1 font-mono text-[11px] text-slate-400 hover:text-white">
                  <GitCompare className="h-3 w-3" /> Compare
                </button>
                {idx > 0 && (
                  <button data-testid={`version-restore-${v.number}`} disabled={project.busy || restoring} onClick={() => restore(v)}
                    className="flex items-center gap-1 rounded border border-[#00F0FF]/40 px-2 py-1 font-mono text-[11px] text-[#00F0FF] hover:bg-[#00F0FF]/10 disabled:opacity-40">
                    {restoring === v.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />} Restore
                  </button>
                )}
              </div>
              {viewing?.id === v.id && (
                <div className="mt-2 max-h-48 overflow-y-auto rounded border border-[#1F2937] bg-[#080C14] p-2 scroll-thin">
                  {viewing.files.map((f) => <p key={f.path} className="truncate font-mono text-[11px] text-slate-400">{f.path} <span className="text-slate-600">· {f.content.split("\n").length} lines</span></p>)}
                </div>
              )}
            </div>
          ))}
        </div>
      </SheetContent>
      <DiffDialog open={!!compare} onOpenChange={(o) => !o && setCompare(null)} api={api} project={project} versions={versions}
        initialBase="current" initialTarget={compare} onRestore={restore} restoring={!!restoring} />
    </Sheet>
  );
};
