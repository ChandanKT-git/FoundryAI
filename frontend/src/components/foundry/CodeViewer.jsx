import { Highlight, themes } from "prism-react-renderer";
import { Copy } from "lucide-react";
import { toast } from "sonner";

const LANG = { js: "jsx", jsx: "jsx", ts: "tsx", tsx: "tsx", py: "python", json: "json", md: "markdown", html: "markup",
  css: "css", yml: "yaml", yaml: "yaml", go: "go", rs: "rust", sql: "sql", sh: "bash" };

export const CodeViewer = ({ file }) => {
  if (!file) return <p data-testid="code-empty" className="p-8 font-mono text-xs text-slate-600">Select a file from the explorer.</p>;
  const lang = LANG[file.path.split(".").pop()] || "markup";
  const copy = () => { navigator.clipboard.writeText(file.content); toast.success("Copied to clipboard"); };
  return (
    <div data-testid="code-viewer" className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[#1F2937] px-4 py-2">
        <span data-testid="code-viewer-path" className="truncate font-mono text-xs text-slate-300">{file.path}</span>
        <button data-testid="copy-file-button" onClick={copy} className="flex items-center gap-1.5 rounded px-2 py-1 font-mono text-[11px] text-slate-400 hover:bg-[#1F293D] hover:text-white">
          <Copy className="h-3 w-3" /> Copy
        </button>
      </div>
      <div className="flex-1 overflow-auto bg-[#080C14] scroll-thin">
        <Highlight theme={themes.nightOwl} code={file.content} language={lang}>
          {({ tokens, getLineProps, getTokenProps }) => (
            <pre className="py-3 font-mono text-[12.5px] leading-6">
              {tokens.map((line, i) => (
                <div key={i} {...getLineProps({ line })} className="flex hover:bg-white/[0.02]">
                  <span className="w-12 shrink-0 select-none pr-4 text-right text-slate-700">{i + 1}</span>
                  <span className="whitespace-pre pr-6">{line.map((t, k) => <span key={k} {...getTokenProps({ token: t })} />)}</span>
                </div>
              ))}
            </pre>
          )}
        </Highlight>
      </div>
    </div>
  );
};
