"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, getAnalysisHistory, AnalysisHistory, User, shortAnalysisId } from "@/lib/api";
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

      {/* Main Content: the analyzer is the single primary action on this page */}
      <main className="w-full px-6 py-8">
        <LogUploader />

        {/* Recent Analyses: secondary, kept short and below the fold of the primary action */}
        {analyses.length > 0 && (
          <div className="mt-10 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Recent analyses</h3>
              <Link href="/dashboard/history" className="text-sm text-blue-400 hover:text-blue-300">
                View all →
              </Link>
            </div>
            <div className="grid gap-2">
              {analyses.slice(0, 3).map((analysis) => (
                <Link
                  key={analysis.id}
                  href={`/dashboard/history/${analysis.id}`}
                  className="glass p-3.5 rounded-lg border border-slate-700 hover:border-blue-500 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-blue-400 shrink-0" />
                      <div>
                        <div className="font-medium text-slate-200 capitalize">
                          {analysis.domain} Analysis
                          <span className="ml-2 font-mono text-xs font-normal text-slate-500">#{shortAnalysisId(analysis.id)}</span>
                        </div>
                        <div className="text-sm text-slate-400">
                          {new Date(analysis.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </div>
                      </div>
                    </div>
                    <div className={`text-sm font-medium ${analysis.status === 'completed' ? 'text-emerald-400' : analysis.status === 'failed' ? 'text-red-400' : 'text-amber-400'}`}>
                      {analysis.status}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
