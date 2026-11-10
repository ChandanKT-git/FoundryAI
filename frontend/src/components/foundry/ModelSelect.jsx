import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MODELS } from "@/lib/api";

export const ModelSelect = ({ value, onChange, testId = "model-select", compact, disabled }) => (
  <Select value={value} onValueChange={onChange} disabled={disabled}>
    <SelectTrigger data-testid={testId} className={`border-[#1F2937] bg-[#0B0F17] font-mono text-xs text-slate-200 focus:ring-[#00F0FF]/40 ${compact ? "h-8 w-[150px]" : "h-10 w-full"}`}>
      <SelectValue />
    </SelectTrigger>
    <SelectContent className="border-[#1F2937] bg-[#111827] text-slate-200">
      {MODELS.map((m) => (
        <SelectItem key={m.id} value={m.id} data-testid={`${testId}-option-${m.id}`} className="font-mono text-xs focus:bg-[#1F293D] focus:text-white">
          {m.label}{!compact && <span className="ml-2 text-slate-500">· {m.tag}</span>}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);
