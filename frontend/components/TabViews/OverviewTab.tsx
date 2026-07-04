import { Activity, AlertTriangle, CheckCircle2, Gauge, Server, Wrench } from "lucide-react";
import { AnalysisResult, Severity } from "@/lib/types";

const severityStyles: Record<Severity, string> = {
  healthy: "border-emerald-700/50 bg-emerald-950/20 text-emerald-300",
  info: "border-blue-700/50 bg-blue-950/20 text-blue-300",
  warning: "border-amber-700/50 bg-amber-950/20 text-amber-300",
  critical: "border-red-700/50 bg-red-950/20 text-red-300",
};

export default function OverviewTab({ data }: { data: AnalysisResult }) {
  const sourceSummary = data.source_summary || [];
  const affected = data.affected_components || [];
  const visual = data.visual_summary || {
    headline: "Infrastructure analysis completed",
    likely_failure_path: [],
    plain_english_summary: data.root_cause?.investigation_summary || "",
    business_impact: data.root_cause?.impact || "",
    fix_summary: data.mitigation_plan?.summary || "",
  };

  return (
    <div className="space-y-5">
      <div className={`rounded-lg border p-5 ${severityStyles[data.severity || "info"]}`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide opacity-80">
              <Activity className="h-4 w-4" />
              Incident Overview
            </div>
            <h3 className="mt-2 text-xl font-semibold text-slate-100">{visual.headline}</h3>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
              {visual.plain_english_summary || "The analyzer collected evidence and prepared a mitigation plan."}
            </p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-3 text-right">
            <div className="text-xs text-slate-500">Confidence</div>
            <div className="text-2xl font-semibold text-slate-100">{Math.round((data.confidence || 0.5) * 100)}%</div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {sourceSummary.length === 0 ? (
          <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-sm text-slate-400">
            No connector summary was stored for this analysis.
          </div>
        ) : sourceSummary.map((source) => (
          <div key={source.source} className="rounded-lg border border-slate-700 bg-slate-900/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 font-medium capitalize text-slate-200">
                <Server className="h-4 w-4 text-blue-400" />
                {source.source}
              </div>
              <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${severityStyles[source.status]}`}>
                {source.status}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-400">{source.message}</p>
            <p className="mt-2 text-xs text-slate-500">{source.item_count} evidence items</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-700 bg-slate-900/40 p-4">
          <h4 className="mb-3 flex items-center gap-2 font-semibold text-slate-200">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            Affected Components
          </h4>
          {affected.length === 0 ? (
            <p className="text-sm text-slate-500">No affected components were identified.</p>
          ) : (
            <div className="space-y-3">
              {affected.slice(0, 8).map((component) => (
                <div key={`${component.source}-${component.name}`} className="rounded border border-slate-700 bg-slate-950/40 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium text-slate-200">{component.name}</div>
                    <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${severityStyles[component.status]}`}>
                      {component.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs uppercase text-slate-500">{component.source}</p>
                  <p className="mt-2 text-sm text-slate-400">{component.impact}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-lg border border-slate-700 bg-slate-900/40 p-4">
          <h4 className="mb-3 flex items-center gap-2 font-semibold text-slate-200">
            <Gauge className="h-4 w-4 text-cyan-400" />
            What Happened
          </h4>
          {visual.likely_failure_path?.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {visual.likely_failure_path.map((item, index) => (
                <span key={`${item}-${index}`} className="rounded border border-cyan-700/40 bg-cyan-950/20 px-2 py-1 text-xs text-cyan-200">
                  {item}
                </span>
              ))}
            </div>
          )}
          <div className="space-y-4 text-sm leading-relaxed text-slate-300">
            <div>
              <div className="mb-1 flex items-center gap-2 font-medium text-slate-200">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                Impact
              </div>
              <p>{visual.business_impact || data.root_cause?.impact}</p>
            </div>
            <div>
              <div className="mb-1 flex items-center gap-2 font-medium text-slate-200">
                <Wrench className="h-4 w-4 text-purple-400" />
                Fix Summary
              </div>
              <p>{visual.fix_summary || data.mitigation_plan?.summary}</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
