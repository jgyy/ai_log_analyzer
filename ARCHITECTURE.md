# DevOps AI Log Analyzer Architecture

## Overview

DevOps AI Log Analyzer is an incident analysis MVP for DevOps, SRE, and platform teams. It accepts manually supplied logs or collects local Linux and Docker evidence, structures the evidence, sends it to an AI provider, and returns an investigation timeline, root cause analysis, mitigation plan, Mermaid diagrams, visual summary, and approved remediation actions.

The current product has one primary UI action: **Analyze**. Behind that button, the frontend can request different evidence sources:

- Manual logs pasted or uploaded by the user.
- Linux host evidence from the backend machine.
- Docker container evidence from the backend machine.
- Combined Linux + Docker evidence.

The backend keeps two analysis HTTP endpoints for compatibility:

- `POST /api/analyze` for legacy manual log analysis.
- `POST /api/incidents/analyze` for the current source-based incident workflow.

Both paths use the same AI service model execution pipeline so manual logs and connector-backed incidents get the same provider selection, Mermaid diagram checks, and API retry behavior.

## Tech Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | Next.js 14, React 18, TypeScript | Dashboard, auth screens, incident source selection, result tabs |
| Styling | Tailwind CSS, custom global CSS | Dark dashboard UI and responsive layout |
| Icons | Lucide React | UI icons for tabs, buttons, status cards |
| Diagrams | Mermaid | Visualizes timeline, root cause, and mitigation flowcharts |
| Backend | FastAPI | HTTP API, auth-protected analysis and action endpoints |
| Data Models | Pydantic v2 | Request/response validation and AI response schema |
| Database | SQLAlchemy + SQLite by default | Users, organizations, analysis history, audit logs |
| Auth | JWT bearer tokens, bcrypt password hashing | Login, role-based endpoint access |
| AI Providers | Google Gemini, Anthropic Claude | Structured incident analysis generation |
| Local Connectors | Python subprocess against system tools | Linux and Docker evidence collection |
| Tests | Python unittest | Connector and action unit tests |

## Repository Structure

```text
ai_log_analyzer/
├── backend/
│   ├── main.py                 # FastAPI routes and request orchestration
│   ├── ai_service.py           # Gemini/Claude integration, retries, Mermaid checks
│   ├── connectors.py           # Local manual/Linux/Docker evidence collection
│   ├── actions.py              # Allowlisted remediation action execution
│   ├── schemas.py              # Pydantic API and AI response schemas
│   ├── database.py             # SQLAlchemy models and DB session setup
│   ├── auth.py                 # JWT auth, role checks, password hashing
│   ├── log_processor.py        # Manual log preprocessing
│   ├── test_incident_mvp.py    # Unit tests for connectors/actions
│   └── requirements.txt
├── frontend/
│   ├── app/                    # Next.js routes
│   ├── components/
│   │   ├── LogUploader.tsx     # Main source selection + Analyze workflow
│   │   ├── AnalysisTab.tsx     # Result tab container
│   │   ├── MermaidDiagram.tsx  # Mermaid rendering/sanitization
│   │   └── TabViews/           # Timeline, root cause, mitigation, overview views
│   ├── lib/
│   │   ├── api.ts              # Backend API client
│   │   └── types.ts            # Frontend copy of backend result types
│   └── package.json
├── README.md
└── ARCHITECTURE.md
```

## Runtime Architecture

```text
Browser
  |
  | JWT-authenticated API calls
  v
FastAPI backend
  |
  | optional evidence collection
  v
Manual logs / Linux tools / Docker CLI
  |
  | structured Pydantic evidence
  v
AIService
  |
  | Gemini or Claude structured JSON call
  v
AnalysisResult JSON
  |
  | persisted in SQLite and returned to UI
  v
Tabbed result view + Mermaid diagrams + approved actions
```

## Backend Components

### `main.py`

`main.py` owns the HTTP API and high-level orchestration.

Important endpoints:

- `POST /api/auth/register`: creates users and organizations. The first user in an organization becomes admin.
- `POST /api/auth/login`: returns a JWT token.
- `GET /api/auth/me`: returns the current authenticated user.
- `POST /api/analyze`: legacy manual log endpoint. It preprocesses raw logs and calls `AIService.analyze_logs`.
- `POST /api/incidents/analyze`: current incident workflow endpoint. It collects selected sources and calls `AIService.analyze_incident`.
- `POST /api/actions/{action_id}/execute`: executes a backend-provided allowlisted remediation action.
- `GET /api/analyses`: returns recent organization analysis history.
- `GET /api/analyses/{analysis_id}`: returns one stored analysis.
- `GET /health`: simple backend health check.

Roles:

- `viewer`: can view data but cannot run analysis or execute actions.
- `sre`: can run analysis and execute allowlisted actions.
- `admin`: can run analysis, execute actions, and manage users.

### `schemas.py`

`schemas.py` defines the API contract and AI response contract.

Core request models:

- `LogAnalysisRequest`: manual legacy input with `logs` and `domain`.
- `IncidentAnalysisRequest`: source-based input with `sources`, optional `logs`, and `domain`.

Core result model:

- `AnalysisResult`
  - `investigation_timeline`: start, symptom, observation, finding, root cause.
  - `root_cause`: investigation summary, impact, root causes, hypotheses, key findings, gaps.
  - `mitigation_plan`: prepare, pre-validate, apply, post-validate, rollback, agent-ready notes.
  - `diagrams`: Mermaid timeline, root cause, and mitigation flowcharts.
  - `source_summary`: per-source collection status.
  - `affected_components`: components likely involved in the incident.
  - `severity`: `healthy`, `info`, `warning`, or `critical`.
  - `confidence`: model confidence from 0 to 1.
  - `evidence`: structured evidence items.
  - `visual_summary`: plain-English explanation for non-technical users.
  - `recommended_actions`: backend-provided executable actions.

Gemini compatibility note: evidence metadata is represented as a list of `{key, value}` objects instead of an open dictionary. This avoids JSON Schema `additionalProperties`, which Gemini Developer API does not support in response schemas.

### `ai_service.py`

`AIService` is the only backend component that calls LLM providers.

Public methods:

- `analyze_logs(logs, domain)`: builds a manual-log prompt for `/api/analyze`.
- `analyze_incident(collected, domain)`: builds a connector-evidence prompt for `/api/incidents/analyze`, then adds backend-owned connector context to the result.

Shared internal flow:

```text
analyze_logs / analyze_incident
  -> build prompt
  -> _run_analysis(prompt)
       -> _call_model_with_retries(prompt)
            -> _analyze_with_gemini or _analyze_with_claude
       -> validate Mermaid diagrams
       -> ask model to regenerate diagrams if needed
  -> return AnalysisResult
```

Provider selection:

- `AI_PROVIDER=gemini` uses Google Gemini.
- `AI_PROVIDER=claude` uses Anthropic Claude.
- Gemini defaults to `gemini-2.5-flash-lite`.
- Gemini fallback is `gemini-2.5-flash`.
- Claude defaults to `claude-sonnet-5`.

AI API failure handling:

- Retries are centralized in `_call_model_with_retries`.
- Retryable Gemini errors include `503` and `429 RESOURCE_EXHAUSTED`.
- On retryable Gemini errors, the service switches to the backup Gemini model.
- Error logging uses `getattr` for provider-specific fields so missing `.code`, `.status`, or `.response` does not mask the original error.

Mermaid diagram handling:

- Prompts require three Mermaid diagrams.
- `_diagram_issues` checks for common render problems:
  - Markdown code fences.
  - Reserved Mermaid node IDs such as `end`, `class`, `click`, `style`, `subgraph`, `direction`.
  - Labels with special characters that are not quoted.
- `_run_analysis` gives the model up to `MAX_DIAGRAM_ATTEMPTS` attempts to regenerate invalid diagrams.
- The frontend Mermaid component remains a final rendering safety net.

### `connectors.py`

`connectors.py` converts raw local system observations into structured evidence.

Common output shape:

```python
{
    "source_summary": [SourceSummary],
    "evidence": [CollectedEvidence],
    "actions": [ExecutableAction],
}
```

Each `CollectedEvidence` includes:

- `id`: unique evidence ID.
- `source`: `manual`, `linux`, or `docker`.
- `component`: service, container, host signal, or logical component.
- `severity`: `info`, `warning`, or `critical`.
- `timestamp`: optional timestamp.
- `message`: human-readable evidence.
- `metadata`: list of key/value metadata pairs.

#### Manual Connector

The manual connector is used when source is `manual`.

Behavior:

- Reads pasted or uploaded logs from the request.
- Splits the text into lines.
- Captures up to the first 120 non-empty lines.
- Marks lines containing error keywords as `warning`.
- Does not create executable actions.

This path is used by the current UI when the user selects **Manual Logs**. The legacy `/api/analyze` endpoint uses `log_processor.py` first, then calls the AI service directly.

#### Linux Connector

The Linux connector runs on the same host as the FastAPI backend.

Commands used:

- `systemctl --failed --no-legend --plain`
- `journalctl -p warning..alert -n 120 --no-pager -o short-iso`
- `df -h /`
- `free -m`
- `uptime`

What it collects:

- Failed systemd units.
- Warning-or-higher journal entries.
- Root filesystem usage.
- Memory snapshot.
- Load average / uptime.

Severity behavior:

- Failed systemd services become `critical`.
- Error-like journal entries become `warning`.
- Disk usage at or above 85% becomes `warning`.
- Memory and load snapshots are informational.

Executable actions:

- For failed `.service` units, the connector creates a `restart_systemd_service` action.
- The action is allowlisted and can only restart targets ending in `.service`.

Failure behavior:

- If `systemctl` is unavailable, the connector returns a warning evidence item instead of failing the whole analysis.
- If collection throws an exception, the connector returns a partial failure summary.

#### Docker Connector

The Docker connector runs on the same host as the FastAPI backend.

Commands used:

- `docker ps -a --format "{{json .}}"`
- `docker logs --tail 80 <container_id>` for containers that look unhealthy, exited, dead, or non-running.

What it collects:

- Container ID.
- Container name.
- Image.
- Docker state.
- Docker status text.
- Recent logs for unhealthy/exited/dead/non-running containers.

Severity behavior:

- Running containers are informational.
- Exited, dead, unhealthy, or non-running containers are `critical`.
- Recent logs from problematic containers are `warning`.

Executable actions:

- `restart_docker_container`
- `start_docker_container`
- `stop_docker_container`

Actions are only generated for containers observed in local Docker evidence.

Failure behavior:

- If Docker CLI is unavailable, the connector returns a warning evidence item.
- If Docker returns an error, the connector returns a warning evidence item with the Docker error message.

### `actions.py`

`actions.py` executes only backend-created allowlisted remediation actions.

Supported commands:

- `docker restart <container_id>`
- `docker start <container_id>`
- `docker stop <container_id>`
- `systemctl restart <service_name.service>`

Safety model:

- The LLM does not get to create arbitrary shell commands.
- The frontend can only request execution by action ID.
- The backend searches recent analyses for a matching `recommended_actions` entry from the same organization.
- If no action is found, the backend returns `404`.
- Every execution writes an audit log.
- Viewers cannot execute actions.

## Frontend Components

### `LogUploader.tsx`

This is the primary analysis UI.

It presents four source presets:

- `Manual Logs`: sends `sources: ["manual"]` and user-provided logs.
- `Linux`: sends `sources: ["linux"]`.
- `Docker`: sends `sources: ["docker"]`.
- `Linux + Docker`: sends `sources: ["linux", "docker"]`.

The current Analyze button always calls:

```ts
analyzeIncident({
  sources: selected.sources,
  logs: logs.trim() || undefined,
  domain,
})
```

So the active dashboard uses `/api/incidents/analyze` for all source modes, including manual logs.

### `lib/api.ts`

Frontend API helper functions:

- `analyzeLogs`: calls legacy `/api/analyze`.
- `analyzeIncident`: calls current `/api/incidents/analyze`.
- `executeAction`: calls `/api/actions/{action_id}/execute`.
- Auth and history helpers for login, users, and stored analyses.

`analyzeLogs` remains exported because older components still reference it.

### `AnalysisTab.tsx` and Tab Views

The result is displayed through tabs:

- Investigation Timeline
- Root Cause
- Mitigation Plan

The tab views can render Mermaid diagrams from `result.diagrams`:

- `timeline_flowchart`
- `root_cause_diagram`
- `mitigation_flowchart`

The mitigation tab also shows approved executable actions when the backend returned them.

## Analysis Paths

### Current UI Path: Manual Logs

```text
User selects Manual Logs
  -> paste/upload logs
  -> click Analyze
  -> frontend calls POST /api/incidents/analyze
  -> backend collect_sources(["manual"], logs)
  -> manual evidence is built
  -> AIService.analyze_incident(collected, domain)
  -> shared AI execution + diagram validation
  -> connector context is attached
  -> result stored in DB
  -> result returned to frontend
```

### Current UI Path: Linux

```text
User selects Linux
  -> click Analyze
  -> frontend calls POST /api/incidents/analyze
  -> backend collect_sources(["linux"])
  -> Linux connector runs local system commands
  -> structured Linux evidence and systemd actions are built
  -> AIService.analyze_incident(...)
  -> result stored and returned
```

### Current UI Path: Docker

```text
User selects Docker
  -> click Analyze
  -> frontend calls POST /api/incidents/analyze
  -> backend collect_sources(["docker"])
  -> Docker connector reads container state and selected logs
  -> structured Docker evidence and container actions are built
  -> AIService.analyze_incident(...)
  -> result stored and returned
```

### Current UI Path: Linux + Docker

```text
User selects Linux + Docker
  -> click Analyze
  -> frontend calls POST /api/incidents/analyze
  -> backend collect_sources(["linux", "docker"])
  -> Linux and Docker evidence are merged
  -> AI analyzes cross-source incident context
  -> result stored and returned
```

### Legacy Path: `/api/analyze`

```text
Older caller sends raw logs to POST /api/analyze
  -> backend preprocess_logs(logs)
  -> AIService.analyze_logs(cleaned, domain)
  -> shared AI execution + diagram validation
  -> result stored and returned
```

This path should remain until older UI/API callers are removed.

## How To Run Locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-gemini-key"
export JWT_SECRET="your-jwt-secret"
export AI_PROVIDER="gemini"
uvicorn main:app --reload --port 8000
```

To use Claude:

```bash
export AI_PROVIDER="claude"
export ANTHROPIC_API_KEY="your-anthropic-key"
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## How To Test

### Backend Unit Tests

Run from the backend directory:

```bash
cd backend
.venv/bin/python -m py_compile *.py
.venv/bin/python -m unittest test_incident_mvp.py
```

The current unit tests cover:

- Linux connector parsing of failed services.
- Docker connector parsing of exited/unhealthy containers.
- Docker partial failure when CLI is unavailable.
- Rejection of unsafe systemd targets.
- Docker restart command mapping.

### Gemini Schema Compatibility

Gemini Developer API does not support `additionalProperties` in the response schema. Verify the schema does not contain it:

```bash
cd backend
.venv/bin/python -c "import json; from schemas import AnalysisResult; schema=json.dumps(AnalysisResult.model_json_schema()); print('additionalProperties' in schema)"
```

Expected output:

```text
False
```

### Backend Import Check

```bash
cd backend
GEMINI_API_KEY=dummy .venv/bin/python -c "import main; print('backend imports ok')"
```

### Test Manual Logs Through API

First log in through the frontend or use `/api/auth/login` to get a bearer token.

```bash
curl -X POST http://localhost:8000/api/incidents/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["manual"],
    "domain": "system",
    "logs": "Jul 04 host kernel: ERROR disk full on /var\nservice failed to write logs"
  }'
```

Expected behavior:

- Backend creates manual evidence.
- AI returns timeline, RCA, mitigation, diagrams, and visual summary.
- No executable actions are generated for manual logs.

### Test Linux Connector

```bash
curl -X POST http://localhost:8000/api/incidents/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["linux"],
    "domain": "infrastructure"
  }'
```

Useful local commands to compare connector behavior:

```bash
systemctl --failed --no-legend --plain
journalctl -p warning..alert -n 120 --no-pager -o short-iso
df -h /
free -m
uptime
```

If a failed `.service` is found, the result may include an approved restart action for that service.

### Test Docker Connector

```bash
curl -X POST http://localhost:8000/api/incidents/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["docker"],
    "domain": "infrastructure"
  }'
```

Useful local commands to compare connector behavior:

```bash
docker ps -a --format "{{json .}}"
docker logs --tail 80 <container_id>
```

To create a simple exited container for testing:

```bash
docker run --name ai-log-test-exit alpine sh -c "echo ERROR simulated failure; exit 1"
```

Then run Docker analysis. The connector should identify the exited container and generate Docker start/restart/stop actions.

Clean up after testing:

```bash
docker rm ai-log-test-exit
```

### Test Linux + Docker Together

```bash
curl -X POST http://localhost:8000/api/incidents/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["linux", "docker"],
    "domain": "infrastructure"
  }'
```

Expected behavior:

- Linux and Docker evidence are merged into one incident context.
- The AI can correlate host symptoms with container symptoms.
- The result includes source summaries for both connectors.

### Test Legacy `/api/analyze`

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "nginx",
    "logs": "2026/07/04 10:00:00 [error] upstream timed out while connecting to upstream"
  }'
```

Expected behavior:

- The endpoint remains compatible with older callers.
- It uses the same AI retry and Mermaid validation pipeline as incident analysis.

### Test Approved Action Execution

After an incident analysis returns `recommended_actions`, execute one action by ID:

```bash
curl -X POST http://localhost:8000/api/actions/<ACTION_ID>/execute \
  -H "Authorization: Bearer <TOKEN>"
```

The backend only executes action IDs found in recent stored analyses for the current organization.

## Security and Safety Design

The MVP intentionally limits automation risk.

- LLM output is never executed directly.
- The backend generates executable actions from observed connector evidence.
- Actions are mapped to fixed command templates in `actions.py`.
- Action execution requires an authenticated `admin` or `sre`.
- Every action execution creates an audit log.
- Connector failures are reported as evidence instead of crashing the analysis.
- Docker and systemd commands run only on the backend host.

## Known MVP Limits

- Connectors are local-only. They inspect the machine running FastAPI.
- No SSH, Kubernetes, cloud, or external observability connectors yet.
- No background job queue; analysis runs in the request path.
- SQLite is the default database.
- Remediation action history is stored in generic audit logs, not a dedicated action table.
- The UI uses one current Analyze workflow, but the backend keeps `/api/analyze` for compatibility.
- Docker access depends on the backend process permissions.
- systemd actions depend on host permissions and may require elevated service privileges.

## Adding New Connectors

A new connector should follow the pattern in `connectors.py`:

1. Add a new enum value to `ConnectorType` in `schemas.py`.
2. Implement `collect_<source>_evidence()` in `connectors.py`.
3. Return the standard connector output:

   ```python
   {
       "summary": SourceSummary(...),
       "evidence": [CollectedEvidence(...)],
       "actions": [ExecutableAction(...)],
   }
   ```

4. Add the connector to `collect_sources`.
5. Add frontend source selection in `LogUploader.tsx`.
6. Add TypeScript union values in `frontend/lib/types.ts`.
7. Add unit tests with mocked command/API output.
8. Add allowlisted actions in `actions.py` only if safe and deterministic.

## Future Connector Ideas

### Kubernetes

Collect:

- Pod status and restart counts.
- Events from affected namespaces.
- Deployment/ReplicaSet status.
- Recent pod logs for failing pods.
- Node pressure conditions.

Commands/API:

- `kubectl get pods -A`
- `kubectl get events -A --sort-by=.lastTimestamp`
- `kubectl describe pod`
- Kubernetes Python client for production use.

Possible actions:

- Restart deployment rollout.
- Scale deployment.
- Delete failed pod only when controlled by ReplicaSet/Deployment.

### Cloud Providers

AWS:

- CloudWatch logs.
- EC2 instance status checks.
- ECS service/task status.
- RDS events.
- ELB target health.

Azure:

- Azure Monitor logs.
- VM health.
- AKS health.
- App Service diagnostics.

GCP:

- Cloud Logging.
- GKE workload status.
- Compute Engine instance status.
- Cloud SQL events.

Design note: cloud connectors need credential storage, scoped permissions, and strong audit logging before execution actions are added.

### Observability Tools

Prometheus:

- Active alerts.
- Recent time-series around incident window.
- Target health.

Grafana:

- Dashboard panel snapshots.
- Alert annotations.

Datadog/New Relic:

- Active monitors.
- APM traces.
- Infrastructure metrics.

### Network and Edge

Nginx:

- Error logs.
- Access log spikes.
- Upstream failure rates.
- Config test output.

Load balancers:

- Target health.
- 4xx/5xx rates.
- Backend pool status.

DNS/TLS:

- Certificate expiry.
- DNS lookup failures.
- TLS handshake errors.

### CI/CD and Release Systems

GitHub Actions/GitLab/Jenkins:

- Failed deployment jobs.
- Recent deployment timestamps.
- Changed commits before outage.

This would help correlate outages with recent releases.

## Recommended MVP Improvements

### 1. Background Jobs

Move analysis into a job queue so long-running AI calls do not block HTTP requests.

Suggested approach:

- Add `status: queued | processing | completed | failed`.
- Add polling endpoint or WebSocket updates.
- Use Celery/RQ/Arq or FastAPI background tasks for a simple first step.

### 2. Dedicated Remediation Action Table

Store action proposals and executions separately from generic audit logs.

Benefits:

- Show action history in UI.
- Track before/after status.
- Add approval workflows.
- Support rollback verification.

### 3. Connector Configuration UI

Add admin-managed connector configuration.

Examples:

- Enable/disable Linux or Docker connector.
- Restrict systemd services that can be restarted.
- Configure Docker socket access warnings.
- Later, store SSH/cloud/Kubernetes credentials securely.

### 4. Incident Timeline Storage

Store evidence and analysis timeline as first-class database records instead of only storing JSON.

Benefits:

- Better search.
- Better filtering by source/component/severity.
- Easier reporting.

### 5. Stronger Mermaid Validation

Current validation catches common model mistakes. A future version could validate Mermaid with a parser or a server-side rendering check.

### 6. Retrieval and Runbook Memory

Add organization-specific runbooks and previous incidents as retrieval context.

Examples:

- "How this team usually restarts service X."
- "Known false positives."
- "Previous outage with same error pattern."

### 7. Multi-host Collection

Add SSH-based Linux/Docker connectors.

Required additions:

- Host inventory.
- Credential handling.
- Per-host permissions.
- Network timeout and partial failure model.

### 8. Kubernetes and Cloud Expansion

After local Linux/Docker is stable, Kubernetes should be the next connector because it naturally maps to DevOps incident workflows and can reuse the evidence/action model.

## Operational Notes

- Keep `/api/analyze` until no older callers use it.
- Prefer `/api/incidents/analyze` for all new analysis flows.
- Keep the AI response schema Gemini-compatible by avoiding open dictionaries in Pydantic response models.
- Do not add arbitrary command execution. New remediation should always be an explicit `ActionType` mapped to fixed backend command logic.
- Add tests for every connector parser and every action command mapping.
