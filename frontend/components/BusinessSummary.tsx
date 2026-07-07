import { AlertTriangle, ArrowRightCircle, Briefcase, Gauge, Server } from "lucide-react";
import { AnalysisResult, BusinessRiskLevel } from "@/lib/types";

const riskStyles: Record<BusinessRiskLevel, string> = {
  Low: "border-emerald-700/50 bg-emerald-950/30 text-emerald-300",
  Medium: "border-blue-700/50 bg-blue-950/30 text-blue-300",
  High: "border-amber-700/50 bg-amber-950/30 text-amber-300",
  Critical: "border-red-700/50 bg-red-950/30 text-red-300",
};

function riskFromSeverity(severity: AnalysisResult["severity"]): BusinessRiskLevel {
  if (severity === "critical") return "Critical";
  if (severity === "warning") return "High";
  if (severity === "healthy") return "Low";
  return "Medium";
}

export default function BusinessSummary({ data }: { data: AnalysisResult }) {
  const summary = data.business_summary || {
    incident_title: data.visual_summary?.headline || "Infrastructure incident detected",
    what_happened: data.visual_summary?.plain_english_summary || data.root_cause?.investigation_summary || "The analyzer reviewed the available evidence.",
    business_impact: data.visual_summary?.business_impact || data.root_cause?.impact || "Business impact was not clearly identified.",
    risk_level: riskFromSeverity(data.severity),
    affected_service: data.affected_components?.[0]?.name || data.visual_summary?.likely_failure_path?.[0] || "Unknown",
    recommended_next_step: data.visual_summary?.fix_summary || data.mitigation_plan?.summary || "Review the technical analysis and confirm the next action.",
  };

  const riskLevel = summary.risk_level || riskFromSeverity(data.severity);

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-medium uppercase text-slate-400">
            <Briefcase className="h-4 w-4 text-cyan-300" />
            Business Summary
          </div>
          <h3 className="mt-2 text-xl font-semibold text-slate-100">{summary.incident_title}</h3>
        </div>
        <span className={`rounded-full border px-3 py-1 text-sm font-medium ${riskStyles[riskLevel]}`}>
          {riskLevel} Risk
        </span>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
            What Happened
          </div>
          <p className="text-sm leading-relaxed text-slate-300">{summary.what_happened}</p>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
            <Gauge className="h-4 w-4 text-blue-300" />
            Business Impact
          </div>
          <p className="text-sm leading-relaxed text-slate-300">{summary.business_impact}</p>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
            <Server className="h-4 w-4 text-cyan-300" />
            Affected Service
          </div>
          <p className="text-sm leading-relaxed text-slate-300">{summary.affected_service}</p>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
            <ArrowRightCircle className="h-4 w-4 text-emerald-300" />
            Recommended Next Step
          </div>
          <p className="text-sm leading-relaxed text-slate-300">{summary.recommended_next_step}</p>
        </div>
      </div>
    </section>
  );
}
