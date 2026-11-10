import { useState } from "react";
import { ChevronRight, FileCode2, FileText, Folder, FolderOpen, FlaskConical, Globe } from "lucide-react";
import { buildTree } from "@/lib/files";

const fileIcon = (name) => {
  if (name === "preview.html") return <Globe className="h-3.5 w-3.5 text-[#10B981]" />;
  if (/test|spec/i.test(name)) return <FlaskConical className="h-3.5 w-3.5 text-amber-400" />;
  if (/\.(md|txt)$/.test(name)) return <FileText className="h-3.5 w-3.5 text-slate-400" />;
  return <FileCode2 className="h-3.5 w-3.5 text-[#00F0FF]" />;
};

const sortNodes = (nodes) => Object.values(nodes).sort((a, b) => (a.file === b.file ? a.name.localeCompare(b.name) : a.file ? 1 : -1));

const Node = ({ node, depth, selected, onSelect }) => {
  const [open, setOpen] = useState(depth < 2);
  const pad = { paddingLeft: 8 + depth * 12 };
  if (node.file) {
    return (
      <button data-testid={`file-${node.path}`} onClick={() => onSelect(node.path)} style={pad}
        className={`flex w-full items-center gap-2 py-1 pr-2 text-left font-mono text-xs transition-colors ${selected === node.path ? "bg-[#00F0FF]/10 text-white" : "text-slate-400 hover:bg-[#1F293D] hover:text-white"}`}>
        {fileIcon(node.name)}<span className="truncate">{node.name}</span>
      </button>
    );
  }
  return (
    <div>
      <button onClick={() => setOpen(!open)} style={pad} data-testid={`folder-${node.path}`}
        className="flex w-full items-center gap-1.5 py-1 pr-2 text-left font-mono text-xs text-slate-300 hover:bg-[#1F293D] hover:text-white">
        <ChevronRight className={`h-3 w-3 transition-transform ${open ? "rotate-90" : ""}`} />
        {open ? <FolderOpen className="h-3.5 w-3.5 text-slate-500" /> : <Folder className="h-3.5 w-3.5 text-slate-500" />}
        <span className="truncate">{node.name}</span>
      </button>
      {open && sortNodes(node.children).map((c) => <Node key={c.path} node={c} depth={depth + 1} selected={selected} onSelect={onSelect} />)}
    </div>
  );
};

export const FileTree = ({ files, selected, onSelect }) => {
  if (!files?.length) return <p data-testid="file-tree-empty" className="px-4 py-6 font-mono text-xs text-slate-600">Files appear once the code stage runs.</p>;
  return (
    <div data-testid="file-tree" className="py-2">
      {sortNodes(buildTree(files).children).map((n) => <Node key={n.path} node={n} depth={0} selected={selected} onSelect={onSelect} />)}
    </div>
  );
};
