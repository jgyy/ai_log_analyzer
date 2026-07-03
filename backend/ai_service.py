from google import genai
from google.genai import types as genai_types
from anthropic import AsyncAnthropic
from schemas import AnalysisResult
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"
CLAUDE_DEFAULT_MODEL = "claude-sonnet-5"

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

In addition to the written analysis, populate the "diagrams" object with three valid Mermaid diagrams (as plain Mermaid source text, no markdown code fences) that visualize the SAME content you wrote — the diagrams and text must tell the same story, just in different forms:
- timeline_flowchart: a Mermaid flowchart (flowchart TD) with one node per investigation stage (Start, Symptom, Observation, Finding, Root Cause), each node's label summarizing that stage in a few words, connected in sequence.
- root_cause_diagram: a Mermaid flowchart showing how the root cause(s) and hypotheses lead to the observed impact (e.g. root causes and hypotheses as nodes flowing into an "Impact" node).
- mitigation_flowchart: a Mermaid flowchart of the mitigation phases (Prepare → Pre-Validate → Apply → Post-Validate), with key step titles as short labels, including a rollback branch.

Keep node labels short (under 8 words) and always wrap node text in quotes if it contains special characters like parentheses or colons.

Logs:
{logs}
"""
        if self.provider == "gemini":
            return await self._analyze_with_gemini(prompt)
        return await self._analyze_with_claude(prompt)

    async def _analyze_with_gemini(self, prompt: str) -> AnalysisResult:
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=AnalysisResult,  # Pass the Pydantic class directly
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
