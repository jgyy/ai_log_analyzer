"use client";
import { useState, useRef, useEffect } from "react";
import { Upload, FileText, X, Loader2, Sparkles } from "lucide-react";
import { analyzeLogs } from "@/lib/api";
import { AnalysisResult } from "@/lib/types";
import AnalysisTabs from "./AnalysisTab";
import { getToken } from "@/lib/api";

interface LogUploaderProps {
  onAnalysisComplete?: () => void;
}

const STATUS_STAGES = [
  { atSeconds: 0, message: "Parsing and deduplicating logs..." },
  { atSeconds: 4, message: "Identifying error patterns & timeline..." },
  { atSeconds: 10, message: "Consulting AI model for root cause..." },
  { atSeconds: 20, message: "Drafting mitigation & rollback plan..." },
  { atSeconds: 35, message: "Still working — larger logs can take longer..." },
];

const SAMPLE_LOGS = [
  { label: "Kubernetes: OOM crash loop", domain: "kubernetes", file: "/sample-logs/kubernetes-oom-crash.log" },
  { label: "Nginx: 502 upstream outage", domain: "nginx", file: "/sample-logs/nginx-502-upstream.log" },
  { label: "System: disk full incident", domain: "system", file: "/sample-logs/system-disk-full.log" },
];

export default function LogUploader({ onAnalysisComplete }: LogUploaderProps) {
  const [logs, setLogs] = useState("");
  const [domain, setDomain] = useState("kubernetes");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleLoadSample = async (sample: typeof SAMPLE_LOGS[number]) => {
    setLoadingSample(sample.file);
    setError(null);
    try {
      const res = await fetch(sample.file);
      const text = await res.text();
      setLogs(text);
      setDomain(sample.domain);
    } catch {
      setError("Couldn't load the sample log. Try again.");
    } finally {
      setLoadingSample(null);
    }
  };

  useEffect(() => {
    if (!loading) return;
    setElapsedSeconds(0);
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [loading]);

  const statusMessage = [...STATUS_STAGES].reverse().find((s) => elapsedSeconds >= s.atSeconds)?.message
    ?? STATUS_STAGES[0].message;

const handleSubmit = async () => {
  if (!logs.trim()) return;
  setLoading(true);
  setError(null);
  try {
    const token = getToken();
    const res = await fetch("http://localhost:8000/api/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ logs, domain }),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "Analysis failed");
    }

    const data = await res.json();
    setResult(data.result);
  } catch (err: any) {
    setError(err.message || "Analysis failed. Check backend & API key.");
  } finally {
    setLoading(false);
  }
};

  const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      if (file.size > MAX_UPLOAD_BYTES) {
        setLogs(text.slice(0, MAX_UPLOAD_BYTES));
        setError(`File is ${(file.size / (1024 * 1024)).toFixed(1)}MB; truncated to the first 5MB.`);
      } else {
        setLogs(text);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="w-full px-6 py-6 space-y-8">
      <header className="text-center space-y-2">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
          DevOps AI Log Analyzer
        </h1>
        <p className="text-slate-400">Paste logs or upload files. AI will identify root cause & generate mitigation runbook.</p>
      </header>

      <div className="glass rounded-xl p-6 space-y-4 card-hover">
        <div>
          <p className="text-sm text-slate-400 mb-2 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-blue-400" /> New here? Try a sample incident:
          </p>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_LOGS.map((sample) => (
              <button
                key={sample.file}
                disabled={loading || !!loadingSample}
                onClick={() => handleLoadSample(sample)}
                className="px-3 py-1.5 text-xs rounded-lg border border-slate-700 bg-slate-800/60 text-slate-300 hover:border-blue-500 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
              >
                {loadingSample === sample.file && <Loader2 className="h-3 w-3 animate-spin" />}
                {sample.label}
              </button>
            ))}
          </div>
        </div>

        <div
          className={`border-2 border-dashed border-slate-600 rounded-lg p-8 text-center transition-colors ${
            loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:border-blue-500"
          }`}
          onClick={() => !loading && fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); if (!loading) handleFileUpload({ target: { files: e.dataTransfer.files } } as any); }}
        >
          <Upload className="mx-auto h-8 w-8 text-slate-500 mb-3" />
          <p className="text-slate-300 font-medium">Drag & drop .log / .txt file</p>
          <p className="text-slate-500 text-sm mt-1">or click to browse</p>
          <input ref={fileInputRef} type="file" accept=".log,.txt" className="hidden" onChange={handleFileUpload} disabled={loading} />
        </div>

        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-400">Log domain:</span>
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="bg-slate-900/50 border border-slate-700 rounded-lg px-2 py-1 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value="kubernetes">Kubernetes</option>
            <option value="nginx">Nginx</option>
            <option value="system">System</option>
          </select>
        </div>

        <div className="relative">
          <textarea
            value={logs}
            onChange={(e) => setLogs(e.target.value)}
            placeholder="Paste logs here... (JSON, syslog, kubectl logs, etc.)"
            className="w-full h-48 bg-slate-900/50 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-y"
          />
          {logs && (
            <button onClick={() => setLogs("")} className="absolute top-3 right-3 p-1 text-slate-500 hover:text-white">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {error && <div className="text-red-400 text-sm bg-red-900/20 border border-red-700 rounded p-3">{error}</div>}

        <button
          disabled={loading || !logs.trim()}
          onClick={handleSubmit}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium flex items-center justify-center gap-2 transition-all"
        >
          {loading ? <Loader2 className="animate-spin h-5 w-5" /> : <FileText className="h-5 w-5" />}
          {loading ? `Analyzing Logs... ${elapsedSeconds}s` : "Run AI Analysis"}
        </button>
      </div>

      {loading && (
        <div className="space-y-4">
          <p className="text-center text-sm text-slate-400 transition-opacity duration-300">
            {statusMessage}
          </p>
          <div className="animate-pulse space-y-4">
            {[1,2,3].map(i => <div key={i} className="h-12 bg-slate-800/50 rounded-lg" />)}
            <div className="h-64 bg-slate-800/50 rounded-lg" />
          </div>
        </div>
      )}

      {result && !loading && <AnalysisTabs data={result} />}
    </div>
  );
}