import { Play, AlertCircle, Eye, Search, Target } from "lucide-react";
import { AnalysisResult } from "@/lib/types";
import DiagramLayout from "@/components/DiagramLayout";
import Evidence from "@/components/Evidence"

export default function TimelineTab({ data, diagram }: { data: AnalysisResult["investigation_timeline"]; diagram?: string }) {
  const steps = [
    { key: "start" as const, label: "Start", icon: Play, color: "text-blue-400" },
    { key: "symptom" as const, label: "Symptom", icon: AlertCircle, color: "text-amber-400" },
    { key: "observation" as const, label: "Observation", icon: Eye, color: "text-cyan-400" },
    { key: "finding" as const, label: "Finding", icon: Search, color: "text-purple-400" },
    { key: "root_cause" as const, label: "Root Cause", icon: Target, color: "text-red-400" },
  ];

  return (
    <DiagramLayout diagram={diagram} id="timeline">
      <div className="space-y-0">
      {(steps ?? []).map((s, i) => {
        const item = data?.[s.key] ?? {};
        const Icon = s.icon;

        console.log(`items: ${JSON.stringify(item)}`)

        return (
          <div
            key = {s.key ?? i}
            className = "relative pl-10 pb-8 last:pb-0"
          >
            <div className="absolute left-0 top-0 w-8 h-8 rounded-full bg-slate-800 border border-slate-600 flex items-center justify-center">
              {Icon && (
                <Icon
                  className={`h-4 w-4 ${s.color ?? "text-slate-400"}`}
                />
              )}
            </div>
            {i < steps.length - 1 && (
              <div className="timeline-connector"/>
            )}
            <h3 className="font-semibold text-slate-200 mb-1">
              {i + 1}. {s.label ?? "Unknown step"}
            </h3>
            <div className="text-slate-400 text-sm leading-relaxed whitespace-pre-wrap bg-slate-900/40 p-3 rounded-lg border border-slate-700/50">
              {item.message ?? "Sorry, no message available"}
            </div>
            {/* <Evidence ids={item.evidence_ids}/> */}
          </div>
        );
      })}
      </div>
    </DiagramLayout>
  );
}
