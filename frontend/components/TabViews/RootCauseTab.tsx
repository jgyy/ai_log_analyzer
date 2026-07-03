import { ShieldAlert, FileWarning, Lightbulb, CheckCircle, Info } from "lucide-react";
import { AnalysisResult } from "@/lib/types";
import DiagramLayout from "@/components/DiagramLayout";

const BadgeList = ({ icon: Icon, title, items, type = "info" }: { icon: any, title: string, items: string[], type?: "info"|"warn"|"danger"|"success" }) => {
  const colors = {
    info: "border-slate-600 text-slate-300 bg-slate-800/50",
    warn: "border-amber-700/50 text-amber-300 bg-amber-900/20",
    danger: "border-red-700/50 text-red-300 bg-red-900/20",
    success: "border-emerald-700/50 text-emerald-300 bg-emerald-900/20"
  };
  return (
    <div className={`p-4 rounded-lg border ${colors[type]} mb-4`}>
      <div className="flex items-center gap-2 mb-2 font-medium">
        <Icon className="h-4 w-4" /> {title}
      </div>
      <ul className="space-y-1.5 pl-5 list-disc text-sm opacity-90">
        {items.map((t, i) => <li key={i}>{t}</li>)}
      </ul>
    </div>
  );
};

export default function RootCauseTab({ data, diagram }: { data: AnalysisResult["root_cause"]; diagram?: string }) {
  return (
    <DiagramLayout diagram={diagram} id="rootcause">
      <div className="space-y-4">
        <div className="p-4 bg-slate-900/50 border border-slate-700 rounded-lg">
          <h3 className="font-semibold text-slate-200 mb-1 flex items-center gap-2"><Info className="h-4 w-4 text-blue-400"/> Investigation Summary</h3>
          <p className="text-sm text-slate-300 leading-relaxed">{data.investigation_summary}</p>
        </div>
        <BadgeList icon={ShieldAlert} title="Impact" items={[data.impact]} type="danger" />
        <BadgeList icon={FileWarning} title="Root Causes" items={data.root_causes} type="warn" />
        <BadgeList icon={Lightbulb} title="Hypotheses" items={data.hypotheses} />
        <BadgeList icon={CheckCircle} title="Key Findings" items={data.key_findings} type="success" />
        <div className="p-4 border border-rose-800/50 rounded-lg bg-rose-950/30">
          <h3 className="font-semibold text-rose-300 mb-2 flex items-center gap-2"><FileWarning className="h-4 w-4"/> Investigation Gaps</h3>
          <ul className="space-y-1.5 pl-5 list-disc text-sm text-rose-200/80">
            {data.investigation_gaps.map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </div>
      </div>
    </DiagramLayout>
  );
}
