import { ChevronDown, ShieldAlert, FileWarning, Lightbulb, CheckCircle, Info } from "lucide-react";
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

// Issue #14: hypotheses and investigation gaps are secondary/exploratory
// detail - keep them available for deeper investigation but collapsed by
// default so they don't compete with the root cause / key findings above.
const CollapsibleList = ({ icon: Icon, title, items, tone = "slate" }: { icon: any; title: string; items: string[]; tone?: "slate" | "rose" }) => {
  const styles = tone === "rose"
    ? { container: "border-rose-800/50 bg-rose-950/20", title: "text-rose-300", item: "text-rose-200/80" }
    : { container: "border-slate-700 bg-slate-900/40", title: "text-slate-200", item: "text-slate-300" };

  return (
    <details className={`group rounded-lg border p-4 ${styles.container}`}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <span className={`inline-flex items-center gap-2 font-semibold ${styles.title}`}>
          <Icon className="h-4 w-4" />
          {title}
          <span className="rounded-full border border-slate-700 bg-slate-950/50 px-2 py-0.5 text-xs font-normal text-slate-400">
            {items.length}
          </span>
        </span>
        <ChevronDown className="h-4 w-4 text-slate-500 transition-transform group-open:rotate-180" />
      </summary>
      <ul className={`mt-3 space-y-1.5 pl-5 list-disc text-sm ${styles.item}`}>
        {items.map((t, i) => <li key={i}>{t}</li>)}
      </ul>
    </details>
  );
};

export default function RootCauseTab({ data, diagram }: { data: AnalysisResult["root_cause"]; diagram?: string }) {
  return (
    <DiagramLayout diagram={diagram} id="rootcause">
      <div className="space-y-4">
        <BadgeList icon={FileWarning} title="Root Causes" items={data.root_causes} type="danger" />
        <BadgeList icon={CheckCircle} title="Key Findings" items={data.key_findings} type="success" />
        <BadgeList icon={ShieldAlert} title="Impact" items={[data.impact]} type="warn" />

        <div className="p-4 bg-slate-900/50 border border-slate-700 rounded-lg">
          <h3 className="font-semibold text-slate-200 mb-1 flex items-center gap-2"><Info className="h-4 w-4 text-blue-400"/> Investigation Summary</h3>
          <p className="text-sm text-slate-300 leading-relaxed">{data.investigation_summary}</p>
        </div>

        <CollapsibleList icon={Lightbulb} title="Hypotheses" items={data.hypotheses} />
        <CollapsibleList icon={FileWarning} title="Investigation Gaps" items={data.investigation_gaps} tone="rose" />
      </div>
    </DiagramLayout>
  );
}
