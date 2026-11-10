import { Bug, CheckCircle2, Loader2, Wrench } from "lucide-react";

const SEV = {
  critical: "text-red-300 border-red-500/40 bg-red-500/10",
  high: "text-orange-300 border-orange-500/40 bg-orange-500/10",
  medium: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  low: "text-slate-300 border-slate-500/40 bg-slate-500/10",
};

export const ReviewPanel = ({ review, busy, onFix, fixing }) => {
  if (!review) return <p data-testid="review-empty" className="p-8 font-mono text-xs text-slate-600">The code review runs as the final pipeline stage.</p>;
  const open = review.issues.filter((i) => i.status !== "fixed").length;
  const scoreColor = review.score >= 80 ? "#10B981" : review.score >= 60 ? "#F59E0B" : "#EF4444";
  return (
    <div data-testid="review-panel" className="mx-auto max-w-3xl px-6 py-8">
      <div className="flex flex-wrap items-center gap-6 rounded-lg border border-[#1F2937] bg-[#111827] p-5">
        <div className="grid h-20 w-20 place-items-center rounded-full border-4" style={{ borderColor: scoreColor }}>
          <span data-testid="review-score" className="font-display text-2xl font-extrabold" style={{ color: scoreColor }}>{review.score}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">Quality score · {open} open issue{open === 1 ? "" : "s"}</p>
          <p data-testid="review-summary" className="mt-1 text-sm text-slate-300">{review.summary}</p>
        </div>
      </div>
      <div className="mt-6 space-y-3">
        {review.issues.map((i) => (
          <div key={i.id} data-testid={`issue-${i.id}`} className="rounded-lg border border-[#1F2937] bg-[#0D131F] p-4 transition-colors hover:border-[#374151]">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest ${SEV[i.severity] || SEV.low}`}>{i.severity}</span>
              <span className="font-mono text-[11px] text-slate-500">{i.file}</span>
            </div>
            <h4 className="mt-2 flex items-start gap-2 text-sm font-semibold text-white"><Bug className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />{i.title}</h4>
            <p className="mt-1.5 text-sm text-slate-400">{i.description}</p>
            <p className="mt-2 border-l-2 border-[#00F0FF]/40 pl-3 text-xs text-slate-400"><span className="text-[#00F0FF]">Suggested fix:</span> {i.suggested_fix}</p>
            <div className="mt-3 flex justify-end">
              {i.status === "fixed" ? (
                <span data-testid={`issue-fixed-${i.id}`} className="flex items-center gap-1.5 font-mono text-xs text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" /> Fixed</span>
              ) : (
                <button data-testid={`apply-fix-${i.id}`} disabled={busy} onClick={() => onFix(i)}
                  className="flex items-center gap-1.5 rounded-md border border-[#00F0FF]/40 px-3 py-1.5 font-mono text-xs text-[#00F0FF] transition-colors hover:bg-[#00F0FF]/10 disabled:opacity-40">
                  {fixing === i.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wrench className="h-3.5 w-3.5" />} Apply fix
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
