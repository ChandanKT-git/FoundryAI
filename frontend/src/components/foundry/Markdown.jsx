import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const Markdown = ({ text, testId, empty = "Nothing here yet." }) => (
  <div data-testid={testId} className="md mx-auto max-w-3xl px-6 py-8">
    {text ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown> : <p className="font-mono text-xs text-slate-600">{empty}</p>}
  </div>
);
