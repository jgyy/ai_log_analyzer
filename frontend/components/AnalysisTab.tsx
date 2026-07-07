"use client";
import { useState } from "react";
import { Clock, AlertTriangle, Wrench } from "lucide-react";
import { AnalysisResult } from "@/lib/types";
import TimelineTab from "./TabViews/TimelineTab";
import RootCauseTab from "./TabViews/RootCauseTab";
import MitigationTab from "./TabViews/MitigationTab";
import BusinessSummary from "./BusinessSummary";

export default function AnalysisTabs({ data }: { data: AnalysisResult }) {
  const [active, setActive] = useState(0);
  const tabs = [
    { id: 0, label: "Investigation Timeline", icon: Clock },
    { id: 1, label: "Root Cause", icon: AlertTriangle },
    { id: 2, label: "Mitigation Plan", icon: Wrench },
  ];

  return (
    <div className="space-y-6">
      <BusinessSummary data={data} />

      <div className="glass rounded-xl overflow-hidden">
        <div className="flex border-b border-slate-700/50 bg-slate-900/30">
          {tabs.map(t => {
            const Icon = t.icon;
            const isActive = active === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActive(t.id)}
                className={`flex-1 py-4 px-4 flex items-center justify-center gap-2 text-sm font-medium transition-all ${isActive ? "tab-active border-b-2 border-blue-400" : "tab-inactive hover:bg-slate-800/50"}`}
              >
                <Icon className="h-4 w-4" /> {t.label}
              </button>
            );
          })}
        </div>
        <div className="p-6 min-h-[400px]">
          {active === 0 && <TimelineTab data={data.investigation_timeline} diagram={data.diagrams?.timeline_flowchart} />}
          {active === 1 && <RootCauseTab data={data.root_cause} diagram={data.diagrams?.root_cause_diagram} />}
          {active === 2 && <MitigationTab data={data.mitigation_plan} diagram={data.diagrams?.mitigation_flowchart} actions={data.recommended_actions || []} />}
        </div>
      </div>
    </div>
  );
}
