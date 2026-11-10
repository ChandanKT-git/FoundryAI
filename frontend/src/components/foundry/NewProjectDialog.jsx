import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ModelSelect } from "./ModelSelect";
import { useApi, errMsg, DEFAULT_MODEL } from "@/lib/api";

const IDEAS = [
  "A habit tracker with streaks, daily check-ins and a weekly progress chart",
  "A recipe manager where I save recipes, tag them and build a shopping list",
  "A kanban board for a small team with drag-and-drop cards and due dates",
];

export const NewProjectDialog = ({ open, onOpenChange }) => {
  const api = useApi();
  const navigate = useNavigate();
  const [idea, setIdea] = useState("");
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (idea.trim().length < 5) return toast.error("Describe your idea in a few more words");
    setBusy(true);
    try {
      const { data } = await api.post("/projects", { idea, model });
      toast.success("Agent started — planning your app");
      navigate(`/p/${data.id}`);
    } catch (e) {
      toast.error(errMsg(e));
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="new-project-dialog" className="max-w-xl border-[#1F2937] bg-[#111827] text-slate-100">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">What should we build?</DialogTitle>
          <DialogDescription className="text-slate-400">Describe it in plain words. The agent will plan, design, code, test and review it.</DialogDescription>
        </DialogHeader>
        <Textarea data-testid="idea-input" value={idea} onChange={(e) => setIdea(e.target.value)} rows={5}
          placeholder="e.g. A booking app for a small yoga studio with class schedules and member sign-ups"
          className="resize-none border-[#1F2937] bg-[#0B0F17] text-sm text-slate-100 placeholder:text-slate-600 focus-visible:ring-[#00F0FF]/40" />
        <div className="flex flex-wrap gap-2">
          {IDEAS.map((i, n) => (
            <button key={n} data-testid={`idea-suggestion-${n}`} onClick={() => setIdea(i)}
              className="rounded-full border border-[#1F2937] px-3 py-1 text-xs text-slate-400 transition-colors hover:border-[#00F0FF]/40 hover:text-white">
              <Sparkles className="mr-1 inline h-3 w-3 text-[#00F0FF]" />{i.split(" ").slice(0, 4).join(" ")}…
            </button>
          ))}
        </div>
        <div>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-slate-500">Engineering model</p>
          <ModelSelect value={model} onChange={setModel} testId="new-project-model-select" />
        </div>
        <button data-testid="start-build-button" onClick={submit} disabled={busy}
          className="mt-2 flex h-11 items-center justify-center gap-2 rounded-md bg-[#00F0FF] font-semibold text-[#0B0F17] transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-[0_0_24px_rgba(0,240,255,0.35)] disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Start building <ArrowRight className="h-4 w-4" /></>}
        </button>
      </DialogContent>
    </Dialog>
  );
};
