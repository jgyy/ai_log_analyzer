"""
Generic SSH-based connector for remote hosts, VMs, and other external
systems that are not running on the same machine as the backend.

This addresses the gap the local connectors (Linux/Docker) and the
VirtualBox connector (connectors_vm.py) don't cover: any box reachable
over the network via SSH — a cloud VM, a bare-metal server in another
rack, a colo box, etc. — regardless of hypervisor.

Design notes:
- Connection profiles (host/port/username/auth_method + encrypted
  secret) are stored per-organization in the `remote_targets` table
  (see database.py) and managed via /api/remote-targets endpoints,
  mirroring the existing VM credential UX.
- Diagnostics reuse the exact same failure-signature checks as
  collect_linux_evidence() (failed systemd units, warning+ journal
  entries, disk pressure, memory, load) via the shared
  `_collect_system_evidence` helper in connectors.py — this connector
  only supplies a different transport (SSH exec instead of local
  subprocess).
"""
import io
import subprocess
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from connectors import _collect_system_evidence, _evidence, _failure_summary
from crypto_utils import CredentialEncryptionError, decrypt_value
from database import RemoteTarget
from schemas import ConnectorType, Severity, SourceSummary
import logging

logger = logging.getLogger(__name__)

REMOTE_COMMAND_TIMEOUT = 15

try:
    import paramiko
    _PARAMIKO_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    paramiko = None
    _PARAMIKO_AVAILABLE = False


def _paramiko_available() -> bool:
    return _PARAMIKO_AVAILABLE


def _get_target(db: Session, organization_id: str, name: str) -> Optional[RemoteTarget]:
    return (
        db.query(RemoteTarget)
        .filter(RemoteTarget.organization_id == organization_id, RemoteTarget.name == name)
        .first()
    )


def _decrypt_secret(row: RemoteTarget) -> Optional[str]:
    try:
        return decrypt_value(row.encrypted_secret)
    except CredentialEncryptionError:
        return None


def _connect(row: RemoteTarget, secret: str, timeout: int = 10) -> "paramiko.SSHClient":
    """
    Opens an SSH connection for a configured remote target. Raises on
    failure — callers are responsible for turning that into evidence
    rather than crashing the whole incident analysis.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if row.auth_method == "ssh_key":
        pkey = paramiko.RSAKey.from_private_key(io.StringIO(secret))
        client.connect(
            hostname=row.host, port=row.port or 22, username=row.username,
            pkey=pkey, timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
        )
    else:
        client.connect(
            hostname=row.host, port=row.port or 22, username=row.username,
            password=secret, timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
        )
    return client


def _remote_run_factory(client: "paramiko.SSHClient"):
    """
    Returns a callable with the same shape as connectors._run
    (List[str] -> subprocess.CompletedProcess) so remote diagnostics can
    reuse _collect_system_evidence unchanged.
    """
    def run(command: List[str], timeout: int = REMOTE_COMMAND_TIMEOUT) -> subprocess.CompletedProcess:
        shell_command = " ".join(command)
        try:
            _, stdout, stderr = client.exec_command(shell_command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            returncode = stdout.channel.recv_exit_status()
            return subprocess.CompletedProcess(args=command, returncode=returncode, stdout=out, stderr=err)
        except Exception as exc:
            logger.error(f"remote command failed: {exc}")
            return subprocess.CompletedProcess(args=command, returncode=-1, stdout="", stderr=str(exc))

    return run


def _collect_target_evidence(row: RemoteTarget) -> List:
    label = f"remote:{row.name}"
    secret = _decrypt_secret(row)
    if secret is None:
        return [_evidence(
            ConnectorType.REMOTE,
            f"{label}:credentials",
            f"Could not decrypt stored credentials for remote target '{row.name}'. "
            "The encryption key may have changed since it was stored.",
            Severity.WARNING,
            {"target": row.name},
        )]

    try:
        client = _connect(row, secret)
    except Exception as exc:
        return [_evidence(
            ConnectorType.REMOTE,
            f"{label}:connection",
            f"Could not connect to remote target '{row.name}' ({row.host}:{row.port}): {exc}",
            Severity.WARNING,
            {"target": row.name, "host": row.host},
        )]

    try:
        run = _remote_run_factory(client)
        collected = _collect_system_evidence(ConnectorType.REMOTE, run, component_prefix=f"{label}:")
        evidence = collected["evidence"]
        if not collected["any_command_succeeded"]:
            evidence.append(_evidence(
                ConnectorType.REMOTE,
                f"{label}:access",
                f"Connected to '{row.name}' but could not run any diagnostic commands "
                "— the account may lack permissions, or the host may not expose the "
                "expected Linux tooling (systemctl/journalctl/df/free).",
                Severity.WARNING,
                {"target": row.name},
            ))
        return evidence
    finally:
        client.close()


def collect_remote_evidence(target_names: Optional[List[str]], organization_id: str, db: Session) -> Dict:
    if not _paramiko_available():
        return _failure_summary(
            ConnectorType.REMOTE,
            "The 'paramiko' package is not installed on the backend — remote/SSH log "
            "collection is unavailable. Install it with `pip install paramiko`.",
        )

    query = db.query(RemoteTarget).filter(RemoteTarget.organization_id == organization_id)
    if target_names:
        query = query.filter(RemoteTarget.name.in_(target_names))
    targets = query.all()

    if not targets:
        return _failure_summary(
            ConnectorType.REMOTE,
            "No remote targets are configured for this organization. Add one under "
            "Remote Targets before selecting the Remote/VM (SSH) source.",
        )

    evidence = []
    for row in targets:
        evidence.extend(_collect_target_evidence(row))

    status = Severity.CRITICAL if any(item.severity == Severity.CRITICAL for item in evidence) else Severity.INFO
    return {
        "summary": SourceSummary(
            source=ConnectorType.REMOTE,
            status=status,
            collected=True,
            message=f"Collected {len(evidence)} remote evidence items from {len(targets)} target(s).",
            item_count=len(evidence),
        ),
        "evidence": evidence[:160],
        # No remediation actions are offered for remote targets yet — this
        # connector is diagnostic-only for its first iteration, matching
        # how the VM connector started before lifecycle actions were added.
        "actions": [],
    }
