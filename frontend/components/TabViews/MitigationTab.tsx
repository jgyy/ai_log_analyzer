import { Clipboard, ArrowRight, RotateCcw, Bot } from "lucide-react";
import { AnalysisResult } from "@/lib/types";
import DiagramLayout from "@/components/DiagramLayout";

const StepCard = ({ title, steps, color = "blue" }: { title: string, steps: {title:string, description:string, command_or_action:string}[], color?: "blue"|"emerald"|"amber"|"purple" }) => {
  const colors = {
    blue: "border-blue-700/50 bg-blue-950/20",
    emerald: "border-emerald-700/50 bg-emerald-950/20",
    amber: "border-amber-700/50 bg-amber-950/20",
    purple: "border-purple-700/50 bg-purple-950/20"
  };
  return (
    <div className={`p-4 rounded-lg border mb-3 ${colors[color]}`}>
      <h4 className="font-semibold text-slate-200 mb-3 flex items-center gap-2">
        <ArrowRight className="h-4 w-4" /> {title}
      </h4>
      <div className="space-y-3">
        {steps.map((s, i) => (
          <div key={i} className="bg-slate-900/40 p-3 rounded border border-slate-700/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-slate-200">{i+1}. {s.title}</span>
              <button className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-400 flex items-center gap-1">
                <Clipboard className="h-3 w-3" /> Copy
              </button>
            </div>
            <p className="text-xs text-slate-400 mb-2">{s.description}</p>
            <code className="block bg-black/40 text-green-400 p-2 rounded text-xs font-mono whitespace-pre-wrap">{s.command_or_action}</code>
          </div>
        ))}
      </div>
    </div>
  );
};

export default function MitigationTab({ data, diagram }: { data: AnalysisResult["mitigation_plan"]; diagram?: string }) {
  return (
    <DiagramLayout diagram={diagram} id="mitigation">
      <div className="space-y-4">
        <div className="p-4 bg-slate-900/50 border border-slate-700 rounded-lg">
          <h3 className="font-semibold text-slate-200 mb-1">Summary</h3>
          <p className="text-sm text-slate-300">{data.summary}</p>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-4">
          <StepCard title="Prepare" steps={data.immediate_mitigation.prepare} color="blue" />
          <StepCard title="Pre-Validate" steps={data.immediate_mitigation.pre_validate} color="amber" />
        </div>
        <div className="space-y-4">
          <StepCard title="Apply" steps={data.immediate_mitigation.apply} color="emerald" />
          <StepCard title="Post-Validate" steps={data.immediate_mitigation.post_validate} color="purple" />

          <div className="p-4 border border-yellow-700/50 rounded-lg bg-yellow-950/30">
            <h3 className="font-semibold text-yellow-300 mb-2 flex items-center gap-2"><RotateCcw className="h-4 w-4"/> Rollback Steps</h3>
            <ol className="list-decimal list-inside text-sm text-yellow-200/80 space-y-1">
              {data.rollback_steps.map((s,i) => <li key={i}>{s}</li>)}
            </ol>
          </div>

          <div className="p-4 border border-cyan-700/50 rounded-lg bg-cyan-950/30">
            <h3 className="font-semibold text-cyan-300 mb-2 flex items-center gap-2"><Bot className="h-4 w-4"/> Agent Spec Ready</h3>
            <pre className="text-xs text-cyan-200/80 whitespace-pre-wrap font-mono bg-black/30 p-3 rounded">
              {data.agent_spec_ready.join("\n\n")}
            </pre>
          </div>
        </div>
        </div>
      </div>
    </DiagramLayout>
  );
}
