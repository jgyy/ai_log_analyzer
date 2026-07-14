<!-- ai_log_analyzer frontend/components/, AGENTS.md. -->

# frontend/components/

| Path | What it is |
|---|---|
| `LogUploader.tsx` | Main source selection + Analyze workflow entry point. |
| `AnalysisTab.tsx` | Result tab container. |
| `MermaidDiagram.tsx` | Mermaid rendering with a defensive sanitizer as the final safety net before rendering AI-generated diagram source. |
| `TabViews/` | Timeline, root cause, mitigation, and overview result views (see `TabViews/AGENTS.md`). |

## Conventions
- Any AI-generated content rendered here (Mermaid source, free-text summaries) is treated as
  untrusted: keep using `MermaidDiagram.tsx`'s sanitizer rather than injecting raw diagram source
  elsewhere.
