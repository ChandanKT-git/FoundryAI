import JSZip from "jszip";

export async function downloadZip(name, files) {
  const zip = new JSZip();
  files.forEach((f) => zip.file(f.path, f.content));
  const blob = await zip.generateAsync({ type: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${(name || "project").replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function buildTree(files) {
  const root = { name: "", children: {}, path: "" };
  files.forEach((f) => {
    const parts = f.path.split("/");
    let node = root;
    parts.forEach((part, i) => {
      const path = parts.slice(0, i + 1).join("/");
      if (!node.children[part]) node.children[part] = { name: part, path, children: {}, file: i === parts.length - 1 };
      node = node.children[part];
    });
  });
  return root;
}

export const streamingFiles = (text) => [...(text || "").matchAll(/<<<FILE\s+(.+?)>>>/g)].map((m) => m[1].trim());
