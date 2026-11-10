import { useEffect, useRef, useState } from "react";
import { STAGES } from "@/lib/api";
import { streamingFiles } from "@/lib/files";
import { FileCode2, RefreshCw } from "lucide-react";

export const PipelineStream = ({ project, stage, api }) => {
  const [log, setLog] = useState("");
  const ref = useRef(null);
  const live = project.live?.stage === stage ? project.live.text : null;
  const status = project.stage_status[stage];
  const meta = STAGES.find((s) => s.id === stage);

  useEffect(() => {
    if (live === null && status === "done") api.get(`/projects/${project.id}/logs/${stage}`).then((r) => setLog(r.data.text)).catch(() => {});
    else setLog("");
  }, [stage, status, live === null, project.id, api]); // eslint-disable-line react-hooks/exhaustive-deps

  const text = live ?? log;
  useEffect(() => { if (live !== null && ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [live]);
  const files = ["code", "tests"].includes(stage) ? streamingFiles(text) : [];

  return (
    <div data-testid="pipeline-stream" className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-[#1F2937] px-4 py-2.5">
        <span className="h-2 w-2 rounded-full" style={{ background: meta.color, boxShadow: live !== null ? `0 0 10px ${meta.color}` : "none" }} />
        <span className="font-mono text-xs text-slate-300">{meta.label} · {meta.sub}</span>
        <span data-testid="pipeline-stream-status" className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{live !== null ? "streaming" : status}</span>
        <span className="ml-auto font-mono text-[10px] text-slate-600">{text.length.toLocaleString()} chars</span>
      </div>
      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-[#1F2937] px-4 py-2">
          {files.map((f, i) => (
            <span key={f + i} className={`flex items-center gap-1 rounded border border-[#1F2937] px-2 py-0.5 font-mono text-[10px] ${live !== null && i === files.length - 1 ? "border-[#00F0FF]/50 text-[#00F0FF]" : "text-slate-400"}`}>
              <FileCode2 className="h-3 w-3" />{f}
            </span>
          ))}
        </div>
      )}
      <div ref={ref} className="flex-1 overflow-auto bg-[#080C14] p-5 scroll-thin">
        {text ? (
          <pre data-testid="pipeline-stream-text" className={`whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-slate-300 ${live !== null ? "caret" : ""}`}>{text}</pre>
        ) : (
          <p className="flex items-center gap-2 font-mono text-xs text-slate-600">
            {status === "pending" ? "Waiting for earlier stages…" : status === "running" ? <><RefreshCw className="h-3 w-3 animate-spin" /> Agent is thinking…</> : status === "failed" ? "This stage failed. Use Retry above." : "Loading log…"}
          </p>
        )}
      </div>
    </div>
  );
};
