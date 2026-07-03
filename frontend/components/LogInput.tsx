"use client";
import { useState } from "react";
import { analyzeLogs } from "@/lib/api";
import { AnalysisResult } from "@/lib/types";
import AnalysisTabs from "./AnalysisTab";

export default function LogInput() {
  const [logs, setLogs] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!logs.trim()) return;
    setLoading(true);
    try {
      const res = await analyzeLogs(logs, "admin");
      setResult(res);
    } catch (err) {
      alert("Analysis failed. Check backend & API key.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setLogs(ev.target?.result as string);
    reader.readAsText(file);
  };

  return (
    <div className="w-full px-4">
      <h1 className="text-2xl font-bold mb-4">🔍 DevOps AI Log Analyzer</h1>
      <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-lg p-4 space-y-3">
        <div className="flex gap-2 items-center">
          <textarea value={logs} onChange={(e) => setLogs(e.target.value)} className="w-full h-40 bg-black/40 border border-border rounded p-2 text-sm font-mono text-slate-300" placeholder="Paste logs here..." />
          <label className="cursor-pointer px-3 py-2 bg-primary rounded text-sm hover:bg-sky-500">Upload .log</label>
          <input type="file" accept=".log,.txt" onChange={handleFileUpload} className="hidden" />
        </div>
        <button disabled={loading || !logs} className="w-full py-2 bg-primary disabled:opacity-50 rounded font-medium hover:bg-sky-500">
          {loading ? "Analyzing..." : "Run Analysis"}
        </button>
      </form>
      {result && <AnalysisTabs data={result} />}
    </div>
  );
}