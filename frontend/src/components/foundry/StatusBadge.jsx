const STYLES = {
  planning: "text-violet-300 bg-violet-500/10 border-violet-500/30",
  building: "text-amber-300 bg-amber-500/10 border-amber-500/30",
  reviewing: "text-blue-300 bg-blue-500/10 border-blue-500/30",
  ready: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
  failed: "text-red-300 bg-red-500/10 border-red-500/30",
};

export const StatusBadge = ({ status, busy, testId }) => {
  if (busy && (status === "ready" || status === "failed")) status = "working";
  const s = STYLES[status] || STYLES.building;
  return (
    <span data-testid={testId || "status-badge"} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ${s}`}>
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${busy ? "animate-pulse" : ""}`} />
      {status}
    </span>
  );
};
