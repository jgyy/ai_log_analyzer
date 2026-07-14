"use client";
import { useMemo, useState, useRef, useEffect } from "react";
import { Upload, FileText, X, Loader2, Sparkles, Server, Boxes, Laptop, MonitorSmartphone, Globe, Plus } from "lucide-react";
import { analyzeIncident, listVMs, listRemoteTargets, upsertRemoteTarget, shortAnalysisId } from "@/lib/api";
import { AnalysisResult, ConnectorType, RemoteAuthMethod, RemoteTargetInfo, VMInfo } from "@/lib/types";
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
type SourcePreset = "manual" | "linux" | "docker" | "linux-docker" | "vm" | "remote";

const presets: Array<{ id: SourcePreset; label: string; description: string; icon: any; sources: ConnectorType[] }> = [
  { id: "manual", label: "Manual Logs", description: "Paste or upload log text.", icon: FileText, sources: ["manual"] },
  { id: "linux", label: "Linux", description: "Collect local system logs and host signals.", icon: Server, sources: ["linux"] },
  { id: "docker", label: "Docker", description: "Collect local container status and logs.", icon: Boxes, sources: ["docker"] },
  { id: "linux-docker", label: "Linux + Docker", description: "Analyze host and container evidence together.", icon: Laptop, sources: ["linux", "docker"] },
  { id: "vm", label: "VirtualBox VMs", description: "Inspect VM power state, snapshots, and guest diagnostics.", icon: MonitorSmartphone, sources: ["virtualbox"] },
  { id: "remote", label: "Remote / VM (SSH)", description: "Connect to any remote host, cloud VM, or external system over SSH.", icon: Globe, sources: ["remote"] },
];

const DEFAULT_REMOTE_FORM = { name: "", host: "", port: "22", username: "", auth_method: "password" as RemoteAuthMethod, secret: "" };

export default function LogUploader({ onAnalysisComplete }: LogUploaderProps) {
  const [preset, setPreset] = useState<SourcePreset>("linux-docker");
  const [logs, setLogs] = useState("");
  const [domain, setDomain] = useState("kubernetes");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [loadingSample, setLoadingSample] = useState<string | null>(null);
  const [vms, setVms] = useState<VMInfo[]>([]);
  const [selectedVmNames, setSelectedVmNames] = useState<string[]>([]);
  const [vmLoadError, setVmLoadError] = useState<string | null>(null);
  const [loadingVms, setLoadingVms] = useState(false);
  const [vmsFetched, setVmsFetched] = useState(false);
  const [remoteTargets, setRemoteTargets] = useState<RemoteTargetInfo[]>([]);
  const [selectedRemoteNames, setSelectedRemoteNames] = useState<string[]>([]);
  const [remoteLoadError, setRemoteLoadError] = useState<string | null>(null);
  const [loadingRemote, setLoadingRemote] = useState(false);
  const [remoteFetched, setRemoteFetched] = useState(false);
  const [showAddRemote, setShowAddRemote] = useState(false);
  const [remoteForm, setRemoteForm] = useState(DEFAULT_REMOTE_FORM);
  const [savingRemote, setSavingRemote] = useState(false);
  const [remoteFormError, setRemoteFormError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selected = useMemo(() => presets.find((item) => item.id === preset) || presets[0], [preset]);
  const manualRequired = selected.sources.includes("manual");
  const vmRequired = selected.sources.includes("virtualbox");
  const remoteRequired = selected.sources.includes("remote");

  useEffect(() => {
    if (!vmRequired || vmsFetched || loadingVms) return;
    setLoadingVms(true);
    setVmLoadError(null);
    listVMs()
      .then((list) => {
        setVms(list);
        setSelectedVmNames(list.map((vm) => vm.name));
      })
      .catch((err) => setVmLoadError(err.message || "Couldn't load VMs. Is VBoxManage available on the backend host?"))
      .finally(() => {
        setLoadingVms(false);
        setVmsFetched(true);
      });
  }, [vmRequired, vmsFetched, loadingVms]);
 
  const toggleVm = (name: string) => {
    setSelectedVmNames((prev) => prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]);
  };

  const loadRemoteTargets = () => {
    setLoadingRemote(true);
    setRemoteLoadError(null);
    listRemoteTargets()
      .then((list) => {
        setRemoteTargets(list);
        setSelectedRemoteNames(list.map((t) => t.name));
      })
      .catch((err) => setRemoteLoadError(err.message || "Couldn't load remote targets."))
      .finally(() => {
        setLoadingRemote(false);
        setRemoteFetched(true);
      });
  };

  useEffect(() => {
    if (!remoteRequired || remoteFetched || loadingRemote) return;
    loadRemoteTargets();
  }, [remoteRequired, remoteFetched, loadingRemote]);

  const toggleRemote = (name: string) => {
    setSelectedRemoteNames((prev) => prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]);
  };

  const handleAddRemoteTarget = async () => {
    setRemoteFormError(null);
    if (!remoteForm.name.trim() || !remoteForm.host.trim() || !remoteForm.username.trim() || !remoteForm.secret.trim()) {
      setRemoteFormError("Name, host, username, and password/key are required.");
      return;
    }
    setSavingRemote(true);
    try {
      await upsertRemoteTarget({
        name: remoteForm.name.trim(),
        host: remoteForm.host.trim(),
        port: Number(remoteForm.port) || 22,
        username: remoteForm.username.trim(),
        auth_method: remoteForm.auth_method,
        secret: remoteForm.secret,
      });
      setRemoteForm(DEFAULT_REMOTE_FORM);
      setShowAddRemote(false);
      loadRemoteTargets();
    } catch (err: any) {
      setRemoteFormError(err.message || "Couldn't save remote target.");
    } finally {
      setSavingRemote(false);
    }
  };

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
    setResultId(null);
    try {
      const data = await analyzeIncident({
        sources: selected.sources,
        logs: logs.trim() || undefined,
        domain: domain || "unknown domain",
        vm_targets: vmRequired ? selectedVmNames : undefined,
        remote_targets: remoteRequired ? selectedRemoteNames : undefined,
      });
      setResult(data.result);
      setResultId(data.id ?? null);
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
    <div className="w-full max-w-5xl mx-auto space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-100">New incident analysis</h1>
        <p className="text-sm text-slate-400">Choose a source, add logs, and analyze.</p>
      </header>
      <div>
        <div className="glass rounded-xl p-6 space-y-5 card-hover border border-slate-800">
          <div>
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-300">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs font-semibold text-blue-300">1</span>
              Choose evidence source
            </div>
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
            <div className="space-y-4 border-t border-slate-800 pt-5">
              <div className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-300">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/20 text-xs font-semibold text-blue-300">2</span>
                Add logs
              </div>
              <div>
              <p className="text-xs text-slate-500 mb-2 flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-blue-400" /> Or try a sample:
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


          {vmRequired && (
            <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-300 font-medium">Select VMs to analyze</p>
                {loadingVms && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
              </div>
              {vmLoadError && (
                <div className="text-amber-400 text-sm bg-amber-900/20 border border-amber-700 rounded p-3">
                  {vmLoadError}
                </div>
              )}
              {!loadingVms && !vmLoadError && vms.length === 0 && (
                <p className="text-sm text-slate-500">No VirtualBox VMs found on the backend host.</p>
              )}
              {vms.length > 0 && (
                <div className="space-y-2">
                  {vms.map((vm) => (
                    <label
                      key={vm.name}
                      className="flex items-center justify-between gap-3 rounded border border-slate-700/60 bg-slate-950/40 px-3 py-2 cursor-pointer hover:border-slate-500"
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={selectedVmNames.includes(vm.name)}
                          onChange={() => toggleVm(vm.name)}
                          className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500"
                        />
                        <div>
                          <div className="text-sm font-medium text-slate-200">{vm.name}</div>
                          <div className="text-xs text-slate-500">
                            {vm.state}{vm.state === "running" && !vm.guest_additions_running ? " · Guest Additions not running" : ""}
                            {!vm.has_credentials ? " · no diagnostic credentials configured" : ""}
                          </div>
                        </div>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${vm.state === "running" ? "bg-emerald-900/30 text-emerald-400" : "bg-slate-800 text-slate-400"}`}>
                        {vm.state}
                      </span>
                    </label>
                  ))}
                </div>
              )}
              <p className="text-xs text-slate-500">
                Guest diagnostics only run for VMs with diagnostic credentials configured (under the "VMs" page)
              </p>
            </div>
          )}


          {remoteRequired && (
            <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-300 font-medium">Select remote targets to analyze</p>
                {loadingRemote && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
              </div>
              {remoteLoadError && (
                <div className="text-amber-400 text-sm bg-amber-900/20 border border-amber-700 rounded p-3">
                  {remoteLoadError}
                </div>
              )}
              {!loadingRemote && !remoteLoadError && remoteTargets.length === 0 && (
                <p className="text-sm text-slate-500">No remote targets configured yet. Add one below.</p>
              )}
              {remoteTargets.length > 0 && (
                <div className="space-y-2">
                  {remoteTargets.map((target) => (
                    <label
                      key={target.name}
                      className="flex items-center justify-between gap-3 rounded border border-slate-700/60 bg-slate-950/40 px-3 py-2 cursor-pointer hover:border-slate-500"
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={selectedRemoteNames.includes(target.name)}
                          onChange={() => toggleRemote(target.name)}
                          className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500"
                        />
                        <div>
                          <div className="text-sm font-medium text-slate-200">{target.name}</div>
                          <div className="text-xs text-slate-500">
                            {target.username}@{target.host}:{target.port} · {target.auth_method === "ssh_key" ? "SSH key" : "password"}
                          </div>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {!showAddRemote ? (
                <button
                  onClick={() => setShowAddRemote(true)}
                  className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300"
                >
                  <Plus className="h-3.5 w-3.5" /> Add remote target
                </button>
              ) : (
                <div className="rounded border border-slate-700/60 bg-slate-950/40 p-3 space-y-2">
                  <div className="grid gap-2 md:grid-cols-2">
                    <input
                      placeholder="Name (e.g. prod-web-1)"
                      value={remoteForm.name}
                      onChange={(e) => setRemoteForm({ ...remoteForm, name: e.target.value })}
                      className="bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                      placeholder="Host or IP"
                      value={remoteForm.host}
                      onChange={(e) => setRemoteForm({ ...remoteForm, host: e.target.value })}
                      className="bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                      placeholder="Port"
                      value={remoteForm.port}
                      onChange={(e) => setRemoteForm({ ...remoteForm, port: e.target.value })}
                      className="bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                      placeholder="Username"
                      value={remoteForm.username}
                      onChange={(e) => setRemoteForm({ ...remoteForm, username: e.target.value })}
                      className="bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <select
                      value={remoteForm.auth_method}
                      onChange={(e) => setRemoteForm({ ...remoteForm, auth_method: e.target.value as RemoteAuthMethod })}
                      className="bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="password">Password</option>
                      <option value="ssh_key">SSH private key</option>
                    </select>
                    {remoteForm.auth_method === "password" ? (
                      <input
                        type="password"
                        placeholder="Password"
                        value={remoteForm.secret}
                        onChange={(e) => setRemoteForm({ ...remoteForm, secret: e.target.value })}
                        className="bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    ) : (
                      <textarea
                        placeholder="-----BEGIN OPENSSH PRIVATE KEY-----..."
                        value={remoteForm.secret}
                        onChange={(e) => setRemoteForm({ ...remoteForm, secret: e.target.value })}
                        className="md:col-span-2 h-20 bg-slate-900/50 border border-slate-700 rounded px-2 py-1.5 font-mono text-xs text-slate-200 outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    )}
                  </div>
                  {remoteFormError && <div className="text-red-400 text-xs">{remoteFormError}</div>}
                  <div className="flex gap-2">
                    <button
                      disabled={savingRemote}
                      onClick={handleAddRemoteTarget}
                      className="px-3 py-1.5 text-xs rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white flex items-center gap-1.5"
                    >
                      {savingRemote && <Loader2 className="h-3 w-3 animate-spin" />}
                      Save target
                    </button>
                    <button
                      onClick={() => { setShowAddRemote(false); setRemoteFormError(null); }}
                      className="px-3 py-1.5 text-xs rounded border border-slate-700 text-slate-300 hover:border-slate-500"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              <p className="text-xs text-slate-500">
                Credentials are encrypted at rest and never displayed again. Diagnostics run over SSH
                and require standard Linux tooling (systemctl/journalctl/df/free) on the target.
              </p>
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
            className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-semibold text-base flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-950/40"
          >
            {loading ? <Loader2 className="animate-spin h-5 w-5" /> : <FileText className="h-5 w-5" />}
            {loading ? "Analyzing incident..." : `Analyze ${selected.label}`}
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

        {result && !loading && (
          <div className="space-y-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-200 capitalize">
              {domain} Analysis
              {resultId && (
                <span className="font-mono text-xs font-normal text-slate-500">#{shortAnalysisId(resultId)}</span>
              )}
            </h2>
            <AnalysisTabs data={result} />
          </div>
        )}
      </div>
    </div>
  );
}
