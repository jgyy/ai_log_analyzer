"use client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { getCurrentUser, User, apiRequest, shortAnalysisId } from "@/lib/api";
import Link from "next/link";
import { Clock } from "lucide-react";
import AnalysisTabs from "@/components/AnalysisTab";
import AppHeader from "@/components/AppHeader";

export default function AnalysisDetail() {
  const params = useParams();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      try {
        const userData = await getCurrentUser();
        setUser(userData);
        
        const data = await apiRequest(`/api/analyses/${params.id}`);
        setAnalysis(data);
      } catch (err) {
        console.error("Failed to load analysis:", err);
        router.push("/dashboard/history");
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [params.id, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!analysis || !analysis.result) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="text-center">
          <h2 className="text-xl font-bold text-slate-200 mb-2">Analysis not found</h2>
          <Link href="/dashboard/history" className="text-blue-400 hover:text-blue-300">
            ← Back to history
          </Link>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-950">
      <AppHeader user={user} />

      <main className="w-full px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <Link href="/dashboard/history" className="text-sm text-slate-400 hover:text-slate-200 mb-1 inline-block">
                ← Back to History
              </Link>
              <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-100 capitalize mb-1">
                {analysis.domain} Analysis
                <span className="font-mono text-sm font-normal text-slate-500">#{shortAnalysisId(analysis.id)}</span>
              </h1>
              <div className="flex items-center gap-4 text-sm text-slate-400">
                <span className="flex items-center gap-1">
                  <Clock className="h-4 w-4" />
                  {new Date(analysis.created_at).toLocaleString()}
                </span>
              </div>
            </div>
            <div className={`px-4 py-2 rounded-lg font-medium ${
              analysis.status === 'completed' ? 'bg-emerald-900/30 text-emerald-400' :
              analysis.status === 'failed' ? 'bg-red-900/30 text-red-400' :
              'bg-amber-900/30 text-amber-400'
            }`}>
              {analysis.status}
            </div>
          </div>
        </div>

        {/* Analysis Result */}
        <AnalysisTabs data={analysis.result} />
      </main>
    </div>
  );
}