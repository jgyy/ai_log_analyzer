<!-- ai_log_analyzer frontend/components/TabViews/, AGENTS.md. -->

# frontend/components/TabViews/

One view component per analysis result tab: investigation timeline, root cause, mitigation plan,
and overview. Each pairs its narrative content with a Mermaid flowchart rendered via
`../MermaidDiagram.tsx`.

## Conventions
- A new result tab is its own file here, composed into `AnalysisTab.tsx` — not a conditional
  branch added inside an existing tab view.
