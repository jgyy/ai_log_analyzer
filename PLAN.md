# MVP Plan: Local Infrastructure Incident Analyzer

## Summary
Extend the current paste/upload AI log analyzer into a local DevOps incident assistant. The MVP will collect Linux and Docker evidence from the machine running the FastAPI backend, structure it for Gemini, return improved hypothesis/root-cause/mitigation output, show a non-technical incident overview, and support explicitly approved allowlisted remediation actions.

## Key Changes
- Add a connector layer in the backend with two local connectors:
  - Linux: collect recent system logs, service status, disk/memory/load signals, and failed service indicators.
  - Docker: collect container list, health/status, recent logs for unhealthy/exited containers, restart counts, image/name metadata.
- Add an incident acquisition flow:
  - New API request can analyze pasted logs, local Linux evidence, local Docker evidence, or a combined Linux + Docker snapshot.
  - Keep existing `/api/analyze` behavior working for manual logs.
  - Add a new endpoint such as `/api/incidents/analyze` for connector-backed analysis.
- Expand the analysis schema while preserving the current structure:
  - Keep `investigation_timeline`, `root_cause`, and `mitigation_plan`.
  - Add `source_summary`, `affected_components`, `severity`, `confidence`, `evidence`, `visual_summary`, and `recommended_actions`.
  - Each evidence item should include source type, component name, timestamp if available, severity, and extracted message.
- Improve the AI prompt:
  - Send structured connector output instead of raw unbounded logs.
  - Require evidence-backed findings and explicit uncertainty.
  - Require mitigation steps to distinguish advisory commands from executable allowlisted actions.
- Add allowlisted execution only:
  - Backend exposes remediation actions as typed operations, not arbitrary shell.
  - Initial actions: restart Docker container, stop/start Docker container, and restart local systemd service only if the service name came from connector evidence.
  - Every action requires authenticated user approval and creates an audit log.
  - Viewers cannot execute; SRE/admin can execute.
- Add frontend incident workflow:
  - Replace the dashboard’s primary input area with source selection: Manual Logs, Linux, Docker, Linux + Docker.
  - Keep upload/paste as a manual option.
  - Add an incident overview tab before the existing tabs, showing health tiles, affected components, severity, confidence, likely failure path, and plain-English fix summary.
  - Keep Investigation Timeline, Root Cause, and Mitigation Plan tabs, but update them to consume the richer schema.
  - Add approved action buttons only for backend-provided allowlisted actions.

## Public Interfaces
- Backend models:
  - `ConnectorType`: `manual`, `linux`, `docker`.
  - `CollectedEvidence`: source, component, severity, timestamp, message, metadata.
  - `IncidentAnalysisRequest`: selected sources, optional manual logs, domain defaulting to `infrastructure`.
  - `IncidentAnalysisResponse`: existing analysis metadata plus expanded `AnalysisResult`.
  - `ExecutableAction`: id, label, action_type, target, risk_level, preconditions.
- Backend endpoints:
  - `POST /api/incidents/analyze`
  - `POST /api/actions/{action_id}/execute`
  - Existing `/api/analyze`, `/api/analyses`, and `/api/analyses/{id}` remain compatible.
- Database:
  - Extend stored analysis JSON to include connector metadata and richer result fields.
  - Add action audit records either in existing `AuditLog` or a small dedicated remediation action table if execution status/history needs to be shown.

## Test Plan
- Backend:
  - Unit test Linux connector parsing with sample `journalctl`/syslog-like output.
  - Unit test Docker connector parsing with mocked Docker CLI output.
  - Test connector failures return partial evidence and investigation gaps instead of failing the whole analysis.
  - Test viewers cannot run analysis execution actions.
  - Test SRE/admin execution requires an allowlisted action id and rejects arbitrary commands.
  - Test existing manual `/api/analyze` remains usable.
- Frontend:
  - Type-check updated `AnalysisResult` types.
  - Verify source selection sends the expected request shape.
  - Verify overview tab renders severity, component health, confidence, and plain-English summary.
  - Verify action buttons appear only for executable actions and require confirmation.
- Manual acceptance:
  - Run local Linux + Docker analysis with at least one stopped/unhealthy container.
  - Confirm the UI identifies the affected component, shows evidence, proposes mitigation, and can execute only the approved allowlisted action.

## Assumptions
- MVP connectors run only on the same host as the backend.
- Visualization uses native React/Tailwind/Lucide components with no charting dependency.
- Execution is allowlisted only; Gemini never directly controls shell commands.
- Kubernetes, cloud providers, SSH hosts, and topology graphs are deferred until after the local MVP.
