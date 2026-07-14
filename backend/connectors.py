import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from typing import Callable, Dict, List

from schemas import ActionType, CollectedEvidence, ConnectorType, EvidenceMetadata, ExecutableAction, Severity, SourceSummary
import logging

logger  = logging.getLogger(__name__)

ERROR_PATTERN = re.compile(r"\b(error|failed|fatal|critical|panic|oom|denied|unhealthy)\b", re.IGNORECASE)
SERVICE_PATTERN = re.compile(r"([a-zA-Z0-9_.@-]+\.service)")


def _run(command: List[str], timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _metadata_items(metadata: Dict[str, str] | None) -> List[EvidenceMetadata]:
    return [
        EvidenceMetadata(key=str(key), value=str(value))
        for key, value in (metadata or {}).items()
    ]


def _evidence(
    source: ConnectorType,
    component: str,
    message: str,
    severity: Severity = Severity.INFO,
    metadata: Dict[str, str] | None = None,
    timestamp: str | None = None,
) -> CollectedEvidence:
    return CollectedEvidence(
        id=str(uuid.uuid4()),
        source=source,
        component=component,
        severity=severity,
        timestamp=timestamp,
        message=message.strip()[:2000],
        metadata=_metadata_items(metadata),
    )


def _failure_summary(source: ConnectorType, message: str) -> Dict:
    return {
        "summary": SourceSummary(
            source=source,
            status=Severity.WARNING,
            collected=False,
            message=message,
            item_count=0,
        ),
        "evidence": [
            _evidence(source, "connector", message, Severity.WARNING)
        ],
        "actions": [],
    }


def _collect_system_evidence(
    source: ConnectorType,
    run: Callable[[List[str]], subprocess.CompletedProcess],
    component_prefix: str = "",
) -> Dict:
    evidence: List[CollectedEvidence] = []
    failed_services: List[str] = []
    any_command_succeeded = False

    def safe_run(command: List[str]) -> subprocess.CompletedProcess:
        try:
            logger.info("safe_run in _collect_system_evidence")
            return run(command)
        except Exception as exc:
            logger.error(f"exception in safe_run: {exc}")
            return subprocess.CompletedProcess(args=command, returncode=-1, stdout="", stderr=str(exc))

    failed = safe_run(["systemctl", "--failed", "--no-legend", "--plain"])
    logger.info(f"systemctl --failed...: {failed}")
    if failed.returncode == 0:
        any_command_succeeded = True
        for line in failed.stdout.splitlines()[:20]:
            if not line.strip():
                continue
            parts = line.split()
            service_name = next((part for part in parts if part.endswith(".service")), parts[0] if parts else "systemd")
            failed_services.append(service_name)
            evidence.append(_evidence(
                source,
                f"{component_prefix}{service_name}",
                f"Failed systemd unit detected: {line}",
                Severity.CRITICAL,
                {"raw": line},
            ))

    journal = safe_run(["journalctl", "-p", "warning..emerg", "-n", "120", "--no-pager", "-o", "short-iso"])
    logger.info(f"journalctl -p...: {journal}")
    if journal.returncode == 0:
        any_command_succeeded = True
        for line in journal.stdout.splitlines()[-80:]:
            if ERROR_PATTERN.search(line):
                service_match = SERVICE_PATTERN.search(line)
                component = service_match.group(1) if service_match else "linux"
                evidence.append(_evidence(source, f"{component_prefix}{component}", line, Severity.WARNING))

    disk = safe_run(["df", "-h", "/"])
    logger.info(f"df -h...: {disk}")
    if disk.returncode == 0:
        any_command_succeeded = True
        if disk.stdout.strip():
            lines = disk.stdout.splitlines()
            if len(lines) > 1:
                usage = lines[1].split()
                used_pct = usage[4] if len(usage) > 4 else "unknown"
                try:
                    high_usage = used_pct.endswith("%") and int(used_pct[:-1]) >= 85
                except ValueError:
                    high_usage = False
                severity = Severity.WARNING if high_usage else Severity.INFO
                evidence.append(_evidence(
                    source,
                    f"{component_prefix}disk:/",
                    f"Root filesystem usage is {used_pct}.",
                    severity,
                    {"raw": lines[1]},
                ))

    memory = safe_run(["free", "-m"])
    logger.info(f"free -m: {memory}")
    if memory.returncode == 0:
        any_command_succeeded = True
        if memory.stdout.strip():
            evidence.append(_evidence(
                source,
                f"{component_prefix}memory",
                "Memory snapshot collected.",
                Severity.INFO,
                {"raw": memory.stdout.strip()[:1000]},
            ))

    uptime = safe_run(["uptime"])
    if uptime.returncode == 0:
        any_command_succeeded = True
        if uptime.stdout.strip():
            evidence.append(_evidence(source, f"{component_prefix}load", uptime.stdout.strip(), Severity.INFO))

    logger.info(f"evidence: {evidence}")
    logger.info(f"failed_service: {failed_services}")
    logger.info(f"any_cmd_succeeded: {any_command_succeeded}")
    return {
        "evidence": evidence,
        "failed_services": failed_services,
        "any_command_succeeded": any_command_succeeded,
    }


def collect_linux_evidence() -> Dict:
    if not shutil.which("systemctl"):
        return _failure_summary(ConnectorType.LINUX, "systemctl is not available on this host.")

    try:
        collected = _collect_system_evidence(ConnectorType.LINUX, _run)
    except Exception as exc:
        return _failure_summary(ConnectorType.LINUX, f"Linux evidence collection failed: {exc}")

    evidence = collected["evidence"]
    actions = [
        ExecutableAction(
            id=f"systemd-restart:{service_name}",
            label=f"Restart {service_name}",
            action_type=ActionType.RESTART_SYSTEMD_SERVICE,
            target=service_name,
            risk_level="high",
            preconditions=["Service appeared in local systemd failed-unit evidence."],
            source=ConnectorType.LINUX,
        )
        for service_name in collected["failed_services"]
    ]

    status = Severity.CRITICAL if any(item.severity == Severity.CRITICAL for item in evidence) else Severity.INFO
    return {
        "summary": SourceSummary(
            source=ConnectorType.LINUX,
            status=status,
            collected=True,
            message=f"Collected {len(evidence)} Linux evidence items.",
            item_count=len(evidence),
        ),
        "evidence": evidence[:120],
        "actions": actions,
    }


def collect_docker_evidence() -> Dict:
    evidence: List[CollectedEvidence] = []
    actions: List[ExecutableAction] = []

    if not shutil.which("docker"):
        return _failure_summary(ConnectorType.DOCKER, "Docker CLI is not available on this host.")

    try:
        ps = _run([
            "docker",
            "ps",
            "-a",
            "--format",
            "{{json .}}",
        ], timeout=10)
        if ps.returncode != 0:
            return _failure_summary(ConnectorType.DOCKER, f"Docker collection failed: {ps.stderr.strip() or ps.stdout.strip()}")

        containers = []
        for line in ps.stdout.splitlines():
            if not line.strip():
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                evidence.append(_evidence(ConnectorType.DOCKER, "docker", f"Unparseable docker ps line: {line}", Severity.WARNING))

        for container in containers[:50]:
            container_id = container.get("ID", "")
            name = container.get("Names", container_id)
            state = container.get("State", "unknown")
            status_text = container.get("Status", "")
            image = container.get("Image", "")
            lowered = f"{state} {status_text}".lower()
            severity = Severity.INFO
            if "exited" in lowered or "dead" in lowered or "unhealthy" in lowered or state.lower() != "running":
                severity = Severity.CRITICAL

            evidence.append(_evidence(
                ConnectorType.DOCKER,
                name,
                f"Container {name} is {state}: {status_text}",
                severity,
                {"container_id": container_id, "image": image, "status": status_text, "state": state},
            ))

            if severity == Severity.CRITICAL:
                logs = _run(["docker", "logs", "--tail", "80", container_id], timeout=10)
                log_text = "\n".join((logs.stdout + "\n" + logs.stderr).splitlines()[-80:])
                if log_text.strip():
                    evidence.append(_evidence(
                        ConnectorType.DOCKER,
                        name,
                        f"Recent container logs:\n{log_text}",
                        Severity.WARNING,
                        {"container_id": container_id},
                    ))
                actions.extend([
                    ExecutableAction(
                        id=f"docker-restart:{container_id}",
                        label=f"Restart {name}",
                        action_type=ActionType.RESTART_DOCKER_CONTAINER,
                        target=container_id,
                        risk_level="medium",
                        preconditions=["Container appeared in local Docker evidence."],
                        source=ConnectorType.DOCKER,
                    ),
                    ExecutableAction(
                        id=f"docker-start:{container_id}",
                        label=f"Start {name}",
                        action_type=ActionType.START_DOCKER_CONTAINER,
                        target=container_id,
                        risk_level="medium",
                        preconditions=["Container appeared in local Docker evidence."],
                        source=ConnectorType.DOCKER,
                    ),
                    ExecutableAction(
                        id=f"docker-stop:{container_id}",
                        label=f"Stop {name}",
                        action_type=ActionType.STOP_DOCKER_CONTAINER,
                        target=container_id,
                        risk_level="high",
                        preconditions=["Container appeared in local Docker evidence."],
                        source=ConnectorType.DOCKER,
                    ),
                ])
    except Exception as exc:
        return _failure_summary(ConnectorType.DOCKER, f"Docker evidence collection failed: {exc}")

    status = Severity.CRITICAL if any(item.severity == Severity.CRITICAL for item in evidence) else Severity.INFO
    return {
        "summary": SourceSummary(
            source=ConnectorType.DOCKER,
            status=status,
            collected=True,
            message=f"Collected {len(evidence)} Docker evidence items.",
            item_count=len(evidence),
        ),
        "evidence": evidence[:160],
        "actions": actions,
    }


def collect_manual_evidence(logs: str | None) -> Dict:
    text = (logs or "").strip()
    if not text:
        return _failure_summary(ConnectorType.MANUAL, "No manual logs were provided.")

    lines = text.splitlines()
    evidence = [
        _evidence(
            ConnectorType.MANUAL,
            "manual-log",
            line,
            Severity.WARNING if ERROR_PATTERN.search(line) else Severity.INFO,
            timestamp=datetime.utcnow().isoformat(),
        )
        for line in lines[:120]
        if line.strip()
    ]
    return {
        "summary": SourceSummary(
            source=ConnectorType.MANUAL,
            status=Severity.WARNING if any(item.severity == Severity.WARNING for item in evidence) else Severity.INFO,
            collected=True,
            message=f"Collected {len(evidence)} manual log lines.",
            item_count=len(evidence),
        ),
        "evidence": evidence,
        "actions": [],
    }


def collect_sources(sources: List[ConnectorType],
            logs: str | None = None,
            vm_targets: List[str] | None = None,
            remote_targets: List[str] | None = None,
            db=None,
            organization_id: str | None = None,) -> Dict:
    summaries: List[SourceSummary] = []
    evidence: List[CollectedEvidence] = []
    actions: List[ExecutableAction] = []

    for source in sources:
        if source == ConnectorType.MANUAL:
            result = collect_manual_evidence(logs)
        elif source == ConnectorType.LINUX:
            result = collect_linux_evidence()
        elif source == ConnectorType.DOCKER:
            result = collect_docker_evidence()
        elif source == ConnectorType.VM:
            from connectors_vm import collect_vm_evidence
            if db is None or organization_id is None:
                result = _failure_summary(ConnectorType.VM, "VM evidence collection requires an authenticated request context.")
            else:
                result = collect_vm_evidence(vm_targets, organization_id, db)
        elif source == ConnectorType.REMOTE:
            from connectors_remote import collect_remote_evidence
            if db is None or organization_id is None:
                result = _failure_summary(ConnectorType.REMOTE, "Remote evidence collection requires an authenticated request context.")
            else:
                result = collect_remote_evidence(remote_targets, organization_id, db)
        else:
            continue

        summaries.append(result["summary"])
        evidence.extend(result["evidence"])
        actions.extend(result["actions"])

    return {
        "source_summary": summaries,
        "evidence": evidence,
        "actions": actions,
    }
