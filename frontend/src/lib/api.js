import { useMemo } from "react";
import axios from "axios";
import { useAuth } from "@clerk/react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useApi() {
  const { getToken } = useAuth();
  return useMemo(() => {
    const inst = axios.create({ baseURL: API });
    inst.interceptors.request.use(async (c) => {
      const t = await getToken();
      if (t) c.headers.Authorization = `Bearer ${t}`;
      return c;
    });
    return inst;
  }, [getToken]);
}

export const errMsg = (e) => e?.response?.data?.detail || e?.message || "Something went wrong";

export const MODELS = [
  { id: "claude-opus-5-5", label: "Claude Opus 5.5", tag: "Deepest reasoning" },
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5", tag: "Balanced · default" },
  { id: "gpt-6-luna", label: "GPT 6 Luna", tag: "Fast & sharp" },
  { id: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro", tag: "Long context" },
];
export const DEFAULT_MODEL = "claude-sonnet-5-5";
export const modelLabel = (id) => MODELS.find((m) => m.id === id)?.label || id;

export const STAGES = [
  { id: "plan", label: "Plan", sub: "Product requirements", color: "#8B5CF6" },
  { id: "architecture", label: "Architecture", sub: "System design", color: "#3B82F6" },
  { id: "code", label: "Code", sub: "Source files", color: "#00F0FF" },
  { id: "tests", label: "Tests", sub: "Test suites", color: "#F59E0B" },
  { id: "review", label: "Review", sub: "Bugs & quality", color: "#10B981" },
];

export const timeAgo = (iso) => {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};
