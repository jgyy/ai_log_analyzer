"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, getAnalysisHistory, AnalysisHistory, User } from "@/lib/api";
import Link from "next/link";
import { FileText } from "lucide-react";
import LogUploader from "@/components/LogUploader";
import AppHeader from "@/components/AppHeader";

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const init = async () => {
      try {
        const userData = await getCurrentUser();
        setUser(userData);
        
        const history = await getAnalysisHistory();
        setAnalyses(history);
      } catch (err) {
        console.error("Failed to load dashboard:", err);
        router.push("/login");
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-950">
      <AppHeader user={user} />

      {/* Main Content */}
      <main className="w-full px-6 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-slate-100 mb-2">Incident Analysis</h2>
          <p className="text-slate-400">Collect local Linux and Docker evidence or analyze uploaded logs</p>
        </div>
        
        {/* Recent Analyses Preview */}
        {analyses.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-200">Recent Analyses</h3>
              <Link href="/dashboard/history" className="text-sm text-blue-400 hover:text-blue-300">
                View all →
              </Link>
            </div>
            <div className="grid gap-3">
              {analyses.slice(0, 3).map((analysis) => (
                <Link
                  key={analysis.id}
                  href={`/dashboard/history/${analysis.id}`}
                  className="glass p-4 rounded-lg border border-slate-700 hover:border-blue-500 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-blue-400" />
                      <div>
                        <div className="font-medium text-slate-200 capitalize">{analysis.domain} Analysis</div>
                        <div className="text-sm text-slate-400">
                          {new Date(analysis.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-sm font-medium ${analysis.status === 'completed' ? 'text-emerald-400' : analysis.status === 'failed' ? 'text-red-400' : 'text-amber-400'}`}>
                        {analysis.status}
                      </div>
                      <div className="text-xs text-slate-500">
                        {new Date(analysis.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
        
        {/* Log Uploader Component */}
        <LogUploader />
      </main>
    </div>
  );
}
