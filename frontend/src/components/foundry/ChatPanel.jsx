import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowUp, Bot, FileDiff, Loader2, User } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { ModelSelect } from "./ModelSelect";
import { errMsg, modelLabel } from "@/lib/api";
import { streamingFiles } from "@/lib/files";

const Msg = ({ m }) => {
  const streaming = m.status === "streaming";
  const cut = m.content.search(/<<<(FILE|DELETE)/);
  const text = streaming && cut >= 0 ? m.content.slice(0, cut) : m.content;
  const writing = streaming ? streamingFiles(m.content) : [];
  const isUser = m.role === "user";
  return (
    <div data-testid={`chat-message-${m.role}`} className="rise flex gap-2.5">
      <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded ${isUser ? "bg-[#1F2937]" : "bg-[#00F0FF]/15"}`}>
        {isUser ? <User className="h-3.5 w-3.5 text-slate-300" /> : <Bot className="h-3.5 w-3.5 text-[#00F0FF]" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-600">{isUser ? "You" : `Foundry · ${modelLabel(m.model)}`}</p>
        <p className={`mt-1 whitespace-pre-wrap text-[13px] leading-relaxed ${m.status === "error" ? "text-red-300" : "text-slate-200"} ${streaming && cut < 0 ? "caret" : ""}`}>
          {text || (streaming ? "" : "…")}
        </p>
        {writing.length > 0 && (
          <div className="mt-2 space-y-1">
            {writing.map((f, i) => (
              <p key={f + i} className="flex items-center gap-1.5 font-mono text-[11px] text-amber-300">
                {i === writing.length - 1 ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileDiff className="h-3 w-3" />} writing {f}
              </p>
            ))}
          </div>
        )}
        {m.changed_files?.length > 0 && (
          <div data-testid="chat-changed-files" className="mt-2 rounded-md border border-[#1F2937] bg-[#0B0F17] p-2">
            <p className="mb-1 font-mono text-[10px] uppercase tracking-widest text-emerald-400">{m.changed_files.length} file(s) changed · v{m.version}</p>
            {m.changed_files.map((f) => <p key={f} className="truncate font-mono text-[11px] text-slate-400">{f}</p>)}
          </div>
        )}
      </div>
    </div>
  );
};

export const ChatPanel = ({ project, messages, api, onSent }) => {
  const [text, setText] = useState("");
  const [model, setModel] = useState(project.model);
  const [sending, setSending] = useState(false);
  const ref = useRef(null);
  const ready = project.files?.length > 0;

  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [messages]);
  useEffect(() => { setModel(project.model); }, [project.model]);

  const send = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      await api.post(`/projects/${project.id}/chat`, { message: text, model });
      setText("");
      onSent();
    } catch (e) { toast.error(errMsg(e)); }
    setSending(false);
  };

  return (
    <div data-testid="chat-panel" className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[#1F2937] px-4 py-2.5">
        <span className="font-mono text-[10px] uppercase tracking-widest text-slate-400">Agent</span>
        <ModelSelect compact value={model} onChange={setModel} testId="chat-model-select" />
      </div>
      <div ref={ref} className="flex-1 space-y-5 overflow-y-auto p-4 scroll-thin">
        {messages.length === 0 && (
          <div data-testid="chat-empty" className="rounded-lg border border-dashed border-[#1F2937] p-4 text-xs leading-relaxed text-slate-500">
            {ready ? "Ask for any change — \"add a dark mode\", \"add search to the list\", \"fix the login bug\". The agent edits only the affected files and saves a new version." : "The agent is building your app. Once code exists you can request changes here."}
          </div>
        )}
        {messages.map((m) => <Msg key={m.id} m={m} />)}
      </div>
      <div className="border-t border-[#1F2937] p-3">
        <div className="relative">
          <Textarea data-testid="chat-input" value={text} onChange={(e) => setText(e.target.value)} rows={3} disabled={!ready}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!project.busy) send(); } }}
            placeholder={ready ? "Describe a change…" : "Waiting for code…"}
            className="resize-none border-[#1F2937] bg-[#0B0F17] pr-12 text-[13px] text-slate-100 placeholder:text-slate-600 focus-visible:ring-[#00F0FF]/40" />
          <button data-testid="chat-send-button" onClick={send} disabled={!ready || sending || project.busy || !text.trim()}
            className="absolute bottom-2 right-2 grid h-8 w-8 place-items-center rounded-md bg-[#00F0FF] text-[#0B0F17] transition-transform hover:scale-105 disabled:opacity-30">
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
          </button>
        </div>
        {project.busy && ready && <p className="mt-1.5 font-mono text-[10px] text-amber-400">Agent is working…</p>}
      </div>
    </div>
  );
};
