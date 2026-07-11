"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listVMs, setVMCredentials, deleteVMCredentials, getCurrentUser, User } from "@/lib/api";
import { VMInfo } from "@/lib/types";
import { KeyRound, Trash2, X, AlertCircle, MonitorSmartphone, ShieldCheck } from "lucide-react";
import AppHeader from "@/components/AppHeader";

export default function VMManagement() {
  const [vms, setVms] = useState<VMInfo[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [credentialModalVm, setCredentialModalVm] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const router = useRouter();

  const isAdmin = currentUser?.role === "admin";

  const loadVms = async () => {
    try {
      const list = await listVMs();
      setVms(list);
    } catch (err: any) {
      setError(err.message || "Failed to load VMs. Check backend and VBoxManage access.");
    }
  };

  useEffect(() => {
    const init = async () => {
      try {
        const user = await getCurrentUser();
        setCurrentUser(user);
        if (user.role !== "admin" && user.role !== "sre") {
          router.push("/dashboard");
          return;
        }
        await loadVms();
      } catch (err: any) {
        if (err.message?.includes("Unauthorized") || err.message?.includes("401")) {
          router.push("/login");
        } else {
          setError("Failed to load VM data. Please refresh.");
        }
      } finally {
        setLoading(false);
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  const openCredentialModal = (vmName: string) => {
    setCredentialModalVm(vmName);
    setUsername("");
    setPassword("");
  };

  const handleSaveCredentials = async () => {
    if (!credentialModalVm || !username || !password) {
      alert("Please fill in both fields.");
      return;
    }
    setSaving(true);
    try {
      await setVMCredentials(credentialModalVm, username, password);
      setCredentialModalVm(null);
      await loadVms();
    } catch (err: any) {
      alert(`Failed to save credentials: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCredentials = async (vmName: string) => {
    if (!confirm(`Remove diagnostic credentials for '${vmName}'? Guest-level checks will be skipped until new credentials are added.`)) return;
    try {
      await deleteVMCredentials(vmName);
      await loadVms();
    } catch (err: any) {
      alert(`Failed to remove credentials: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!currentUser) return null;

  return (
    <div className="min-h-screen bg-slate-950">
      <AppHeader user={currentUser} />

      <main className="w-full px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <MonitorSmartphone className="h-6 w-6 text-blue-400" />
            VirtualBox VMs
          </h1>
          <p className="text-slate-400 mt-1">
            VMs registered on the backend host. Diagnostic credentials are used only for
            read-only guest checks (failed systemd units, journal errors, disk, memory, load)
            — use a dedicated low-privilege guest account, not a full admin/root login. That
            account must belong to the <code className="text-slate-300">systemd-journal</code> group
            (or otherwise have read access to the systemd journal), or the journal-based checks
            will silently return no results.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-700 rounded-lg flex items-center gap-3 text-red-300">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
            <button onClick={() => window.location.reload()} className="ml-auto text-sm underline hover:text-red-200">
              Retry
            </button>
          </div>
        )}

        <div className="glass rounded-lg border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50 border-b border-slate-700">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">VM</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">State</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">Guest Additions</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">Snapshots</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase">Diagnostic Access</th>
                  {isAdmin && <th className="text-right px-6 py-3 text-xs font-medium text-slate-400 uppercase">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {vms.length === 0 ? (
                  <tr>
                    <td colSpan={isAdmin ? 6 : 5} className="px-6 py-12 text-center text-slate-500">
                      No VirtualBox VMs found on the backend host.
                    </td>
                  </tr>
                ) : (
                  vms.map((vm) => (
                    <tr key={vm.name} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-200">{vm.name}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          vm.state === "running" ? "bg-emerald-900/30 text-emerald-400" : "bg-slate-800 text-slate-400"
                        }`}>
                          {vm.state}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">
                        {vm.guest_additions_running ? "Running" : "Not running"}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">{vm.snapshot_count}</td>
                      <td className="px-6 py-4">
                        {vm.has_credentials ? (
                          <span className="inline-flex items-center gap-1.5 text-emerald-400 text-sm">
                            <ShieldCheck className="h-4 w-4" /> Configured
                          </span>
                        ) : (
                          <span className="text-slate-500 text-sm">Not configured</span>
                        )}
                      </td>
                      {isAdmin && (
                        <td className="px-6 py-4 text-right">
                          <div className="flex justify-end gap-1">
                            <button
                              onClick={() => openCredentialModal(vm.name)}
                              className="text-blue-400 hover:text-blue-300 p-2 hover:bg-blue-900/20 rounded transition-colors"
                              title={vm.has_credentials ? "Replace credentials" : "Add credentials"}
                            >
                              <KeyRound className="h-4 w-4" />
                            </button>
                            {vm.has_credentials && (
                              <button
                                onClick={() => handleDeleteCredentials(vm.name)}
                                className="text-red-400 hover:text-red-300 p-2 hover:bg-red-900/20 rounded transition-colors"
                                title="Remove credentials"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {credentialModalVm && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm p-4">
            <div className="glass bg-slate-900 p-6 rounded-xl w-full max-w-md border border-slate-700 shadow-2xl">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-slate-100">Diagnostic Credentials — {credentialModalVm}</h2>
                <button onClick={() => setCredentialModalVm(null)} className="text-slate-400 hover:text-white transition-colors">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="mb-4 p-3 rounded border border-amber-700/50 bg-amber-950/20 text-xs text-amber-200/90">
                Use a dedicated, low-privilege guest account for this. It only needs
                permission to run read-only commands (systemctl status, journalctl, df, free, uptime) —
                not an admin or root login. It must also be a member of the{" "}
                <code className="text-amber-100">systemd-journal</code> group so
                journalctl-based checks can actually read the journal; without that
                membership those checks will run successfully but return no log data.
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Guest username</label>
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                    placeholder="vm-diagnostics"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Guest password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                    placeholder="••••••••"
                  />
                </div>

                <button
                  onClick={handleSaveCredentials}
                  disabled={saving}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg font-medium text-white mt-2 transition-colors shadow-lg shadow-blue-900/20"
                >
                  {saving ? "Saving..." : "Save Credentials"}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
