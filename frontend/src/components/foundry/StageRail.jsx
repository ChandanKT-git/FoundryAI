import { Check, Loader2, X } from "lucide-react";
import { STAGES } from "@/lib/api";

const Icon = ({ s, color }) => {
  if (s === "done") return <Check className="h-3.5 w-3.5" style={{ color }} />;
  if (s === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color }} />;
  if (s === "failed") return <X className="h-3.5 w-3.5 text-red-400" />;
  return <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />;
};

export const StageRail = ({ stageStatus = {}, selected, onSelect }) => (
  <div data-testid="stage-rail" className="flex gap-1 overflow-x-auto scroll-thin">
    {STAGES.map((st, i) => {
      const s = stageStatus[st.id] || "pending";
      const active = selected === st.id;
      return (
        <button key={st.id} data-testid={`stage-${st.id}`} data-status={s} onClick={() => onSelect?.(st.id)}
          className={`group flex min-w-[118px] flex-1 items-center gap-2.5 rounded-md border px-3 py-2 text-left transition-colors ${active ? "border-[#374151] bg-[#1F293D]" : "border-transparent hover:bg-[#111827]"}`}>
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded border border-[#1F2937] bg-[#0B0F17]"
            style={s === "running" ? { boxShadow: `0 0 12px ${st.color}55`, borderColor: `${st.color}88` } : undefined}>
            <Icon s={s} color={st.color} />
          </span>
          <span className="min-w-0">
            <span className="block font-mono text-[10px] text-slate-500">0{i + 1}</span>
            <span className={`block truncate text-xs font-semibold ${s === "pending" ? "text-slate-500" : "text-slate-100"}`}>{st.label}</span>
          </span>
        </button>
      );
    })}
  </div>
);
