export interface MitigationStep { title: string; description: string; command_or_action: string }
export interface ImmediateMitigation { prepare: MitigationStep[], pre_validate: MitigationStep[], apply: MitigationStep[], post_validate: MitigationStep[] }

export interface AnalysisDiagrams {
  timeline_flowchart: string;
  root_cause_diagram: string;
  mitigation_flowchart: string;
}

export interface AnalysisResult {
  investigation_timeline: { start: string; symptom: string; observation: string; finding: string; root_cause: string }
  root_cause: { investigation_summary: string; impact: string; root_causes: string[]; hypotheses: string[]; key_findings: string[]; investigation_gaps: string[] }
  mitigation_plan: { summary: string; immediate_mitigation: ImmediateMitigation; rollback_steps: string[]; agent_spec_ready: string[] }
  diagrams?: AnalysisDiagrams
}