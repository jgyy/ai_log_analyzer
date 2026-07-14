from google import genai
from anthropic import AsyncAnthropic
from google.genai import types as genai_types
from schemas import (
    AffectedComponent,
    AnalysisResult,
    BusinessSummary,
    CollectedEvidence,
    Severity,
    VisualSummary,
)
import os
import json
import re
from dotenv import load_dotenv
import logging

load_dotenv()

logger  = logging.getLogger(__name__)

GEMINI_DEFAULT_MODEL    = "gemini-2.5-flash-lite"
GEMINI_BACKUP_MODEL     = "gemini-2.5-flash"
CLAUDE_DEFAULT_MODEL    = "claude-sonnet-5"
MAX_DIAGRAM_ATTEMPTS = 3
MAX_AI_API_ATTEMPTS = 3

DIAGRAM_INSTRUCTIONS = """
In addition to the written analysis, populate the "diagrams" object with three valid Mermaid flowcharts (plain Mermaid source only, no markdown code fences) that visualize the SAME content as the written analysis.

Rules:
- Every diagram MUST start with: flowchart TD
- Every node MUST have an identifier using Mermaid syntax: NodeId["Label"] (e.g. Start["Start"], RC["Root Cause"]).
- Never use quoted strings as standalone nodes (e.g. "Root Cause" --> "Impact" is invalid).
- Keep labels under 8 words.
- Never use Mermaid reserved keywords (end, class, click, style, subgraph, direction) as node identifiers.

- timeline_flowchart: one node each for Start → Symptom → Observation → Finding → Root Cause, connected in sequence.
- root_cause_diagram: root cause(s) and hypotheses flowing into an Impact node.
- mitigation_flowchart: Prepare → Pre-Validate → Apply → Post-Validate, including a rollback branch.
"""

BUSINESS_SUMMARY_INSTRUCTIONS = """
Populate the "business_summary" object for non-technical stakeholders. Use simple, business-facing language and keep each field concise.
- incident_title: short title for the incident.
- what_happened: explain the incident without logs, stack traces, Kubernetes terms, container ids, exception names, or commands unless unavoidable.
- business_impact: describe likely customer or operational impact only when supported by evidence; use "may" when impact is inferred.
- risk_level: exactly one of Low, Medium, High, Critical.
- affected_service: name the affected service or "Unknown" if it is not clearly identified.
- recommended_next_step: one practical next step in plain language.
Do not invent financial loss, customer counts, or outage duration unless the evidence explicitly supports it.
"""

BREVITY_INSTRUCTIONS = """
Keep the response concise and avoid repeating the same fact across sections.
- investigation_timeline fields: 1 sentence each.
- root_causes: maximum 3 items.
- hypotheses: maximum 3 items.
- key_findings: maximum 4 items.
- investigation_gaps: maximum 3 items.
- mitigation steps: maximum 3 steps in each phase.
- mitigation step descriptions: maximum 140 characters.
- rollback_steps: maximum 3 items.
- agent_spec_ready: maximum 3 short items.
Put secondary details in evidence and investigation_gaps instead of long paragraphs.
"""

# Issue #14: the analysis text was too verbose to scan during an incident.
# These rules push the model toward a short, structured, actionable response
# (summary -> evidence -> root cause -> mitigation) instead of long paragraphs,
# while keeping the underlying technical detail available in the
# evidence/key_findings/investigation_gaps fields for deeper investigation.
BREVITY_INSTRUCTIONS = """
Write for incident triage, not a report. Be concise and avoid repeating the same fact in multiple sections:
- Lead with the conclusion, then supporting evidence, then the recommended action - never the other way around.
- Prefer short, direct statements over explanatory paragraphs. No generic DevOps background or definitions.
- investigation_timeline fields (start, symptom, observation, finding, root_cause): 1 sentence each, stating only what happened.
- root_cause.investigation_summary: maximum 2 sentences - the short summary of the issue.
- root_cause.impact: 1 sentence.
- root_cause.root_causes: maximum 3 items, 1 sentence each, ordered most-likely first.
- root_cause.hypotheses: maximum 3 items, 1 sentence each.
- root_cause.key_findings: maximum 4 items - this is where supporting evidence/technical detail belongs.
- root_cause.investigation_gaps: maximum 3 items.
- mitigation_plan.summary: maximum 2 sentences.
- mitigation_plan immediate_mitigation steps: maximum 3 steps per phase (prepare/pre_validate/apply/post_validate).
- mitigation step "description": maximum 140 characters; put commands/details in command_or_action, not description.
- mitigation_plan.rollback_steps: maximum 3 items.
- mitigation_plan.agent_spec_ready: maximum 3 short items.
Do not drop useful technical detail - put secondary/raw details in key_findings, investigation_gaps, or evidence instead of long prose.
"""

# Mirrors the checks the frontend's sanitizer (frontend/components/MermaidDiagram.tsx)
# runs defensively before rendering — used here to catch bad diagrams *before*
# they leave the backend and ask the model to regenerate them instead.
_RESERVED_NODE_IDS = {"end", "class", "click", "style", "subgraph", "direction"}
_NODE_DEF_RE = re.compile(r'\b([A-Za-z0-9_-]+)(\[|\(|\{)"?(.*?)"?(\]|\)|\})(?=\s|-->|$)')


_HEADER_RE = re.compile(
    r'^\s*(flowchart|graph)\s+(TB|TD|BT|LR|RL)\b',
    re.IGNORECASE,
)

def _diagram_issues(chart: str) -> list[str]:
    issues = []
    text = (chart or "").strip()

    if not text:
        return issues

    if text.startswith("```"):
        issues.append(
            "diagram is wrapped in a markdown code fence (```) — return plain Mermaid source only"
        )

    if not _HEADER_RE.match(text):
        issues.append(
            'diagram must begin with "flowchart TD" (or another valid flowchart direction)'
        )

    for node_id, _open, label, _close in _NODE_DEF_RE.findall(text):
        if node_id.lower() in _RESERVED_NODE_IDS:
            issues.append(
                f'node id "{node_id}" is a reserved Mermaid keyword and cannot be used as a node id'
            )
        if re.search(r'["():{}|;]', label) and not (
            label.startswith('"') and label.endswith('"')
        ):
            issues.append(
                f'label {label!r} contains special characters and must be wrapped in double quotes'
            )

    return issues


def _all_diagram_issues(result: AnalysisResult) -> list[str]:
    if not result.diagrams:
        return []
    issues = []
    for name, chart in (
        ("timeline_flowchart", result.diagrams.timeline_flowchart),
        ("root_cause_diagram", result.diagrams.root_cause_diagram),
        ("mitigation_flowchart", result.diagrams.mitigation_flowchart),
    ):
        issues += [f"{name}: {issue}" for issue in _diagram_issues(chart)]
    return issues

class AIService:
    def __init__(self, provider: str = None, model_name: str = None):
        self.provider = provider or os.getenv("AI_PROVIDER", "gemini")

        if self.provider == "gemini":
            self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            self.model_name = model_name or GEMINI_DEFAULT_MODEL
        elif self.provider == "claude":
            self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.model_name = model_name or CLAUDE_DEFAULT_MODEL
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    async def analyze_logs(self, logs: str, domain: str) -> AnalysisResult:
        prompt = f"""
You are an expert DevOps SRE. Analyze the following {domain} logs and return a STRICT JSON response matching the exact schema provided.
Focus on evidence-based reasoning. If logs are insufficient, clearly state it in investigation_gaps.
Do NOT include markdown formatting in text fields. Return ONLY raw JSON.

{DIAGRAM_INSTRUCTIONS}
{BUSINESS_SUMMARY_INSTRUCTIONS}
{BREVITY_INSTRUCTIONS}
Keep executable actions empty unless the backend provides them. Mitigation commands are advisory text only.

Logs:
{logs}
"""
        return await self._run_analysis(prompt)

    async def _analyze_with_gemini(self, prompt: str) -> AnalysisResult:
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=AnalysisResult,
            ),
        )
        return AnalysisResult.model_validate_json(response.text)

    async def _analyze_with_claude(self, prompt: str) -> AnalysisResult:
        response = await self.client.messages.create(
            model=self.model_name,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "submit_analysis",
                "description": "Submit the structured DevOps log analysis result.",
                "input_schema": AnalysisResult.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": "submit_analysis"},
        )
        tool_use = next(block for block in response.content if block.type == "tool_use")
        data = tool_use.input

        # Claude occasionally wraps the payload in an extra top-level key
        # (e.g. {"analysis": {...}}) instead of matching the schema directly.
        required_keys = {"investigation_timeline", "root_cause", "mitigation_plan"}
        if not required_keys.issubset(data.keys()) and len(data) == 1:
            inner = next(iter(data.values()))
            if isinstance(inner, dict) and required_keys.issubset(inner.keys()):
                data = inner

        return AnalysisResult.model_validate(data)

    async def analyze_incident(
        self,
        collected: dict,
        domain: str,
    ) -> AnalysisResult:
        payload = {
            "source_summary": [item.model_dump() for item in collected["source_summary"]],
            "evidence": [item.model_dump() for item in collected["evidence"]],
            "backend_allowlisted_actions": [item.model_dump() for item in collected["actions"]],
        }
        prompt = f"""
You are an expert DevOps SRE incident analyst.
Analyze this local {domain} evidence and return STRICT JSON matching the schema.
Focus on evidence-based reasoning. If logs are insufficient, clearly state it in investigation_gaps.
Do NOT include markdown formatting in text fields. Return ONLY raw JSON.

{DIAGRAM_INSTRUCTIONS}
{BUSINESS_SUMMARY_INSTRUCTIONS}
{BREVITY_INSTRUCTIONS}
Keep executable actions empty unless the backend provides them. Mitigation commands are advisory text only.

Rules:
- Base root cause, hypotheses, impact, and mitigation on the evidence ids provided.
- If evidence is partial or connector collection failed, say so in investigation_gaps.
- Explain the incident in plain language for non-technical users in visual_summary.
- recommended_actions must only include actions from backend_allowlisted_actions. Do not invent executable action ids or shell commands.
- command_or_action fields in mitigation_plan are advisory runbook text unless they exactly refer to a backend allowlisted action.
- Return ONLY raw JSON, no markdown.

Structured incident evidence:
{json.dumps(payload, default=str)[:50000]}
"""
        result = await self._run_analysis(prompt)
        logger.info(f"Model: {self.model_name} | response: {result}")
        return self.with_connector_context(result, collected)

    async def _run_analysis(self, prompt: str) -> AnalysisResult:
        result = None
        current_prompt = prompt
        for attempt in range(MAX_DIAGRAM_ATTEMPTS):
            result = await self._call_model_with_retries(current_prompt)
            self._ensure_business_summary(result)
            issues = _all_diagram_issues(result)
            if not issues:
                return result
            if attempt < MAX_DIAGRAM_ATTEMPTS - 1:
                current_prompt += (
                    "\n\nYour previous attempt's Mermaid diagrams had syntax problems. Regenerate ALL THREE "
                    "diagrams from scratch, fixing every issue below:\n- " + "\n- ".join(issues)
                )

        return result

    def _ensure_business_summary(self, result: AnalysisResult) -> None:
        summary = result.business_summary or BusinessSummary()
        default = BusinessSummary()

        if not summary.incident_title or summary.incident_title == default.incident_title:
            summary.incident_title = self._plain_text(result.visual_summary.headline) or "Infrastructure incident detected"
        if not summary.what_happened or summary.what_happened == default.what_happened:
            summary.what_happened = self._plain_text(result.visual_summary.plain_english_summary) or self._plain_text(result.root_cause.investigation_summary) or default.what_happened
        if not summary.business_impact or summary.business_impact == default.business_impact:
            summary.business_impact = self._plain_text(result.visual_summary.business_impact) or self._plain_text(result.root_cause.impact) or default.business_impact
        if not summary.affected_service or summary.affected_service == default.affected_service:
            summary.affected_service = self._infer_affected_service(result)
        if not summary.recommended_next_step or summary.recommended_next_step == default.recommended_next_step:
            summary.recommended_next_step = self._plain_text(result.visual_summary.fix_summary) or self._plain_text(result.mitigation_plan.summary) or default.recommended_next_step

        if summary.risk_level not in ["Low", "Medium", "High", "Critical"]:
            summary.risk_level = self._business_risk_from_severity(result.severity)
        elif summary.risk_level == default.risk_level and result.severity in [Severity.CRITICAL, Severity.WARNING, Severity.HEALTHY]:
            summary.risk_level = self._business_risk_from_severity(result.severity)

        result.business_summary = summary

    def _business_risk_from_severity(self, severity: Severity) -> str:
        if severity == Severity.CRITICAL:
            return "Critical"
        if severity == Severity.WARNING:
            return "High"
        if severity == Severity.HEALTHY:
            return "Low"
        return "Medium"

    def _infer_affected_service(self, result: AnalysisResult) -> str:
        if result.affected_components:
            return result.affected_components[0].name
        if result.visual_summary.likely_failure_path:
            return result.visual_summary.likely_failure_path[0]
        return "Unknown"

    def _plain_text(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    async def _call_model_with_retries(self, prompt: str) -> AnalysisResult:
        for attempt in range(MAX_AI_API_ATTEMPTS):
            try:
                return (
                    await self._analyze_with_gemini(prompt)
                    if self.provider == "gemini"
                    else await self._analyze_with_claude(prompt)
                )
            except Exception as e:
                self._log_ai_error(attempt, e)
                if attempt == MAX_AI_API_ATTEMPTS - 1 or not self._should_retry_ai_error(e):
                    raise
                if self.provider == "gemini":
                    logger.info("Switching to backup Gemini model")
                    self.model_name = GEMINI_BACKUP_MODEL

        raise RuntimeError("AI analysis failed after all retry attempts")

    def _log_ai_error(self, attempt: int, error: Exception) -> None:
        logger.error(
            "AI API error | attempt=%s | provider=%s | model=%s | code=%s | status=%s | response=%s | error=%s",
            attempt,
            self.provider,
            self.model_name,
            getattr(error, "code", None),
            getattr(error, "status", None),
            getattr(error, "response", None),
            error,
        )

    def _should_retry_ai_error(self, error: Exception) -> bool:
        error_code = getattr(error, "code", None)
        error_status = getattr(error, "status", None)
        return error_code == 503 or (error_code == 429 and error_status == "RESOURCE_EXHAUSTED")

    def with_connector_context(self, result: AnalysisResult, collected: dict) -> AnalysisResult:
        result.source_summary = collected["source_summary"]
        result.evidence = collected["evidence"]
        result.recommended_actions = collected["actions"]

        if not result.affected_components:
            result.affected_components = self._affected_components_from_evidence(collected["evidence"])

        if not result.visual_summary.plain_english_summary:
            critical = [item for item in collected["evidence"] if item.severity == Severity.CRITICAL]
            warning = [item for item in collected["evidence"] if item.severity == Severity.WARNING]
            headline = "Critical infrastructure issue detected" if critical else "Infrastructure evidence collected"
            result.visual_summary = VisualSummary(
                headline=headline,
                likely_failure_path=[item.component for item in (critical or warning)[:4]],
                plain_english_summary=result.root_cause.investigation_summary,
                business_impact=result.root_cause.impact,
                fix_summary=result.mitigation_plan.summary,
            )

        if any(item.severity == Severity.CRITICAL for item in collected["evidence"]):
            result.severity = Severity.CRITICAL
        elif any(item.severity == Severity.WARNING for item in collected["evidence"]):
            result.severity = Severity.WARNING

        self._ensure_business_summary(result)
        return result

    def _affected_components_from_evidence(self, evidence: list[CollectedEvidence]) -> list[AffectedComponent]:
        components: dict[str, AffectedComponent] = {}
        for item in evidence:
            if item.severity not in [Severity.CRITICAL, Severity.WARNING]:
                continue
            key = f"{item.source}:{item.component}"
            if key not in components:
                components[key] = AffectedComponent(
                    name=item.component,
                    source=item.source,
                    status=item.severity,
                    impact=item.message[:240],
                    evidence_refs=[item.id],
                )
            else:
                components[key].evidence_refs.append(item.id)
                if item.severity == Severity.CRITICAL:
                    components[key].status = Severity.CRITICAL
        return list(components.values())[:12]
