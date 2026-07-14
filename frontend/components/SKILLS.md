<!-- ai_log_analyzer frontend/components/, SKILLS.md. -->

# Skills: frontend/components/

| Task | Where |
|---|---|
| Change source selection / the Analyze trigger | `LogUploader.tsx` |
| Change how a result tab is contained/switched | `AnalysisTab.tsx` |
| Change Mermaid rendering or its sanitizer | `MermaidDiagram.tsx` — this is the last line of defense before AI-generated diagram source is rendered; don't bypass it |
| Add a new result view (timeline, root cause, mitigation, overview) | `TabViews/` — see `TabViews/SKILLS.md` |
