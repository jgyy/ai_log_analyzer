export type ConnectorType = "manual" | "linux" | "docker";
export type Severity = "healthy" | "info" | "warning" | "critical";
export type ActionType = "restart_docker_container" | "start_docker_container" | "stop_docker_container" | "restart_systemd_service";

export interface MitigationStep { title: string; description: string; command_or_action: string }
export interface ImmediateMitigation { prepare: MitigationStep[], pre_validate: MitigationStep[], apply: MitigationStep[], post_validate: MitigationStep[] }

export interface AnalysisDiagrams {
  timeline_flowchart: string;
  root_cause_diagram: string;
  mitigation_flowchart: string;
}

export interface SourceSummary {
  source: ConnectorType;
  status: Severity;
  collected: boolean;
  message: string;
  item_count: number;
}

export interface AffectedComponent {
  name: string;
  source: ConnectorType;
  status: Severity;
  impact: string;
  evidence_refs: string[];
}

export interface CollectedEvidence {
  id: string;
  source: ConnectorType;
  component: string;
  severity: Severity;
  timestamp?: string | null;
  message: string;
  metadata: Array<{ key: string; value: string }>;
}

export interface VisualSummary {
  headline: string;
  likely_failure_path: string[];
  plain_english_summary: string;
  business_impact: string;
  fix_summary: string;
}

export interface ExecutableAction {
  id: string;
  label: string;
  action_type: ActionType;
  target: string;
  risk_level: string;
  preconditions: string[];
  source: ConnectorType;
}

export interface AnalysisResult {
  investigation_timeline: { start: string; symptom: string; observation: string; finding: string; root_cause: string }
  root_cause: { investigation_summary: string; impact: string; root_causes: string[]; hypotheses: string[]; key_findings: string[]; investigation_gaps: string[] }
  mitigation_plan: { summary: string; immediate_mitigation: ImmediateMitigation; rollback_steps: string[]; agent_spec_ready: string[] }
  diagrams?: AnalysisDiagrams
  source_summary: SourceSummary[];
  affected_components: AffectedComponent[];
  severity: Severity;
  confidence: number;
  evidence: CollectedEvidence[];
  visual_summary: VisualSummary;
  recommended_actions: ExecutableAction[];
}
