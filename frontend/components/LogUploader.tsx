"use client";
import { useMemo, useState, useRef, useEffect } from "react";
import { Upload, FileText, X, Loader2, Sparkles, Server, Boxes, Laptop } from "lucide-react";
import { analyzeIncident } from "@/lib/api";
import { AnalysisResult, ConnectorType } from "@/lib/types";
import AnalysisTabs from "./AnalysisTab";

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
type SourcePreset = "manual" | "linux" | "docker" | "linux-docker";

const presets: Array<{ id: SourcePreset; label: string; description: string; icon: any; sources: ConnectorType[] }> = [
  { id: "manual", label: "Manual Logs", description: "Paste or upload log text.", icon: FileText, sources: ["manual"] },
  { id: "linux", label: "Linux", description: "Collect local system logs and host signals.", icon: Server, sources: ["linux"] },
  { id: "docker", label: "Docker", description: "Collect local container status and logs.", icon: Boxes, sources: ["docker"] },
  { id: "linux-docker", label: "Linux + Docker", description: "Analyze host and container evidence together.", icon: Laptop, sources: ["linux", "docker"] },
];

export default function LogUploader({ onAnalysisComplete }: LogUploaderProps) {
  const [preset, setPreset] = useState<SourcePreset>("linux-docker");
  const [logs, setLogs] = useState("");
  const [domain, setDomain] = useState("kubernetes");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selected = useMemo(() => presets.find((item) => item.id === preset) || presets[0], [preset]);
  const manualRequired = selected.sources.includes("manual");
  
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
    if (manualRequired && !logs.trim()) {
      setError("Paste logs or upload a .log/.txt file for manual analysis.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeIncident({
        sources: selected.sources,
        logs: logs.trim() || undefined,
        domain: domain || "unknown domain",
      });
      setResult(data.result);
      onAnalysisComplete?.();
    } catch (err: any) {
      setError(err.message || "Analysis failed. Check backend, connector access, and API key.");
    } finally {
      setLoading(false);
    }
  };

  const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    if (file.size > 5 * 1024 * 1024) {
      setError("File too large. Max 5MB.");
      return;
    }
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
        <p className="text-slate-400">
          Pull local Linux and Docker evidence, structure it for AI analysis, and generate an explainable mitigation plan.
        </p>
      </header>
      <div>
        <div className="glass rounded-xl p-6 space-y-5 card-hover">
          <div>
            <div className="mb-3 text-sm font-medium text-slate-300">Evidence source</div>
            <div className="grid gap-3 md:grid-cols-4">
              {presets.map((item) => {
                const Icon = item.icon;
                const active = preset === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setPreset(item.id)}
                    className={`min-h-28 rounded-lg border p-4 text-left transition-colors ${
                      active ? "border-blue-500 bg-blue-950/30" : "border-slate-700 bg-slate-900/40 hover:border-slate-500"
                    }`}
                  >
                    <Icon className={`mb-3 h-5 w-5 ${active ? "text-blue-300" : "text-slate-500"}`} />
                    <div className="font-medium text-slate-200">{item.label}</div>
                    <div className="mt-1 text-xs leading-relaxed text-slate-500">{item.description}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {manualRequired && (
            <div className="space-y-4">
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
                  placeholder="Paste logs here..."
                  className="w-full h-48 bg-slate-900/50 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-y"
                />
                {logs && (
                  <button onClick={() => setLogs("")} className="absolute top-3 right-3 p-1 text-slate-500 hover:text-white">
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* {!manualRequired && (
            <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-4 text-sm text-slate-400">
              The backend will collect evidence from the local host. Docker analysis requires the backend process to have Docker CLI access.
            </div>
          )} */}

          {error && <div className="text-red-400 text-sm bg-red-900/20 border border-red-700 rounded p-3">{error}</div>}

          <button
            disabled={loading}
            onClick={handleSubmit}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium flex items-center justify-center gap-2 transition-all"
          >
            {loading ? <Loader2 className="animate-spin h-5 w-5" /> : <FileText className="h-5 w-5" />}
            {loading ? "Analyzing Incident..." : `Analyze ${selected.label}`}
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
    </div>
  );
}
