import re
import shutil
import subprocess
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from connectors import _collect_system_evidence, _evidence, _failure_summary, _run
from crypto_utils import CredentialEncryptionError, decrypt_value
from database import VMCredential
from schemas import ActionType, ConnectorType, ExecutableAction, Severity, SourceSummary

GUEST_COMMAND_TIMEOUT = 15
# Best-effort parse of VBoxManage's --machinereadable `key="value"` output.
_KV_PATTERN = re.compile(r'^([A-Za-z0-9_]+)="?(.*?)"?$')


def _vboxmanage_available() -> bool:
    return shutil.which("VBoxManage") is not None


def _parse_machinereadable(output: str) -> Dict[str, str]:
    parsed = {}
    for line in output.splitlines():
        match = _KV_PATTERN.match(line.strip())
        if match:
            parsed[match.group(1)] = match.group(2)
    return parsed


def list_vms() -> List[Dict[str, str]]:
    """Returns [{name, uuid, state}] for every registered VM on this host."""
    if not _vboxmanage_available():
        return []

    result = _run(["VBoxManage", "list", "vms"], timeout=10)
    if result.returncode != 0:
        return []

    running = set()
    running_result = _run(["VBoxManage", "list", "runningvms"], timeout=10)
    if running_result.returncode == 0:
        for line in running_result.stdout.splitlines():
            match = re.match(r'^"(.+)"\s+\{(.+)\}$', line.strip())
            if match:
                running.add(match.group(2))

    vms = []
    for line in result.stdout.splitlines():
        match = re.match(r'^"(.+)"\s+\{(.+)\}$', line.strip())
        if not match:
            continue
        name, vm_uuid = match.group(1), match.group(2)
        vms.append({
            "name": name,
            "uuid": vm_uuid,
            "state": "running" if vm_uuid in running else "unknown",
        })
    return vms


def get_vm_info(vm_name: str) -> Optional[Dict[str, str]]:
    """Detailed host-level facts for a single VM via --machinereadable."""
    result = _run(["VBoxManage", "showvminfo", vm_name, "--machinereadable"], timeout=10)
    if result.returncode != 0:
        return None
    info = _parse_machinereadable(result.stdout)

    snapshot_count = len([k for k in info if re.match(r"^SnapshotName", k)])

    return {
        "name": info.get("name", vm_name),
        "uuid": info.get("UUID", ""),
        "state": info.get("VMState", "unknown"),
        "guest_additions_running": info.get("GuestAdditionsRunLevel", "0") not in ("0", ""),
        "guest_os": info.get("ostype", "unknown"),
        "memory_mb": info.get("memory", "unknown"),
        "snapshot_count": snapshot_count,
    }


def _get_credential(db: Session, organization_id: str, vm_name: str) -> Optional[tuple[str, str]]:
    row = (
        db.query(VMCredential)
        .filter(VMCredential.organization_id == organization_id, VMCredential.vm_name == vm_name)
        .first()
    )
    if not row:
        return None
    try:
        return decrypt_value(row.encrypted_username), decrypt_value(row.encrypted_password)
    except CredentialEncryptionError:
        return None


def _guest_run(vm_name: str, username: str, password: str, shell_command: str, timeout: int = GUEST_COMMAND_TIMEOUT) -> subprocess.CompletedProcess:
    """
    Runs `shell_command` inside the guest via VBoxManage guestcontrol,
    using the hypervisor's guest channel (works even if the guest's network
    and display stack are both down, as long as Guest Additions are running).

    Uses /bin/sh rather than /bin/bash: every diagnostic command this
    connector runs is plain POSIX shell, and not every guest image ships
    bash. `--exe` already supplies argv0 for the invoked program, so the
    args after `--` should NOT repeat the shell name — doing so shifts
    every argument by one position and breaks execution (e.g. `sh -c` was
    read as "open a script named sh").

    Never raises: a slow/unreachable guest should degrade to a failed
    check for that one command, not crash the whole incident analysis.
    Guestcontrol commands are noticeably slower than local subprocess
    calls (they go through the hypervisor channel and the guest's own
    process spawn), so callers running unusually heavy commands should
    pass a longer timeout than GUEST_COMMAND_TIMEOUT.
    """
    try:
        return _run(
            [
                "VBoxManage", "guestcontrol", vm_name, "run",
                "--username", username,
                "--password", password,
                "--exe", "/bin/sh",
                "--",
                "-c", shell_command,
            ],
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=[], returncode=-1, stdout="",
            stderr=f"guestcontrol command timed out after {timeout}s",
        )
    except Exception as exc:
        return subprocess.CompletedProcess(
            args=[], returncode=-1, stdout="", stderr=f"guestcontrol command failed: {exc}",
        )


def _collect_guest_diagnostics(vm_name: str, username: str, password: str) -> List:
    """
    Runs the exact same failure-signature checks as
    connectors.collect_linux_evidence() (failed systemd units, warning+
    journal entries, disk pressure, memory, load) against the VM's guest OS,
    via the shared `_collect_system_evidence` helper — rather than this
    connector reimplementing its own narrower, VM-specific versions of the
    same checks. On top of that shared set, this connector adds one
    genuinely VM-specific check: a display-stack crash signature.

    Note: a previous `dpkg -V` package-integrity check has been removed.
    It hashes every installed file against the package database, which is
    far slower than the other checks even locally, and over the
    `VBoxManage guestcontrol` channel it reliably timed out — especially
    on busier or larger guests — degrading every analysis run instead of
    adding a rarely-useful signal.
    """
    def guest_run(command: List[str], timeout: int = GUEST_COMMAND_TIMEOUT) -> subprocess.CompletedProcess:
        return _guest_run(vm_name, username, password, " ".join(command), timeout=timeout)

    collected = _collect_system_evidence(ConnectorType.VM, guest_run, component_prefix=f"vm:{vm_name}:")
    evidence = collected["evidence"]
    any_succeeded = collected["any_command_succeeded"]

    # Display-stack crash signature (gdm-x-session Fatal server error, X
    # display retry exhaustion) — the exact pattern behind the black-screen
    # / non-blinking-cursor failure this connector was built to catch.
    # This is genuinely VM-specific, so it isn't part of the shared checks.
    gdm_journal = _guest_run(
        vm_name, username, password,
        "journalctl -u gdm3 -b --no-pager 2>/dev/null | tail -n 200",
    )
    if gdm_journal.returncode == 0:
        any_succeeded = True
        text = gdm_journal.stdout
        if "Fatal server error" in text or "maximum number of X display failures reached" in text:
            evidence.append(_evidence(
                ConnectorType.VM,
                f"vm:{vm_name}:display-stack",
                "Guest X server is crash-looping (Fatal server error / max display "
                "failures reached) — GDM will show a black screen with a "
                "non-blinking cursor. Check Xorg log permissions/ownership under "
                "the GDM user's home directory.",
                Severity.CRITICAL,
                {"vm": vm_name},
            ))

    if not any_succeeded:
        evidence.append(_evidence(
            ConnectorType.VM,
            f"vm:{vm_name}:guest-access",
            "Could not run diagnostic commands in the guest — Guest Additions "
            "may not be running, or the stored credentials may be invalid.",
            Severity.WARNING,
            {"vm": vm_name},
        ))

    return evidence


def collect_vm_evidence(vm_names: Optional[List[str]], organization_id: str, db: Session) -> Dict:
    if not _vboxmanage_available():
        return _failure_summary(ConnectorType.VM, "VBoxManage is not available on this host.")

    targets = vm_names or [vm["name"] for vm in list_vms()]
    if not targets:
        return _failure_summary(ConnectorType.VM, "No VirtualBox VMs found on this host.")

    evidence = []
    actions: List[ExecutableAction] = []

    for vm_name in targets:
        info = get_vm_info(vm_name)
        if info is None:
            evidence.append(_evidence(
                ConnectorType.VM,
                f"vm:{vm_name}:power-state",
                f"Could not read VM info for '{vm_name}' — it may not exist on this host.",
                Severity.WARNING,
                {"vm": vm_name},
            ))
            continue

        state = info["state"]
        severity = Severity.INFO if state == "running" else Severity.WARNING
        evidence.append(_evidence(
            ConnectorType.VM,
            f"vm:{vm_name}:power-state",
            f"VM '{vm_name}' is {state}"
            + (f" (Guest Additions {'running' if info['guest_additions_running'] else 'not running'})" if state == "running" else "."),
            severity,
            {"vm": vm_name, "state": state, "guest_additions_running": str(info["guest_additions_running"])},
        ))

        # Lifecycle actions are always safe to offer, regardless of guest access.
        if state == "running":
            actions.append(ExecutableAction(
                id=f"vm-restart:{vm_name}",
                label=f"Restart VM '{vm_name}'",
                action_type=ActionType.RESTART_VM,
                target=vm_name,
                risk_level="medium",
                preconditions=[f"VM '{vm_name}' is currently running."],
                source=ConnectorType.VM,
            ))
            actions.append(ExecutableAction(
                id=f"vm-stop:{vm_name}",
                label=f"Stop VM '{vm_name}'",
                action_type=ActionType.STOP_VM,
                target=vm_name,
                risk_level="high",
                preconditions=[f"VM '{vm_name}' is currently running."],
                source=ConnectorType.VM,
            ))
        else:
            actions.append(ExecutableAction(
                id=f"vm-start:{vm_name}",
                label=f"Start VM '{vm_name}'",
                action_type=ActionType.START_VM,
                target=vm_name,
                risk_level="low",
                preconditions=[f"VM '{vm_name}' is currently {state}."],
                source=ConnectorType.VM,
            ))

        if info["snapshot_count"] > 0:
            actions.append(ExecutableAction(
                id=f"vm-restore-snapshot:{vm_name}",
                label=f"Restore last snapshot for '{vm_name}'",
                action_type=ActionType.RESTORE_VM_SNAPSHOT,
                target=vm_name,
                risk_level="high",
                preconditions=[
                    f"VM '{vm_name}' has {info['snapshot_count']} snapshot(s) available.",
                    "This discards all guest state since the snapshot was taken and requires explicit confirmation.",
                ],
                source=ConnectorType.VM,
            ))

        if state != "running":
            continue

        credential = _get_credential(db, organization_id, vm_name)
        if credential is None:
            evidence.append(_evidence(
                ConnectorType.VM,
                f"vm:{vm_name}:guest-access",
                f"No diagnostic credentials configured for '{vm_name}' — "
                f"guest-level checks (display stack, disk, logs) "
                f"were skipped. Host-level facts only.",
                Severity.WARNING,
                {"vm": vm_name},
            ))
            continue

        username, password = credential
        evidence.extend(_collect_guest_diagnostics(vm_name, username, password))

    status = Severity.CRITICAL if any(item.severity == Severity.CRITICAL for item in evidence) else Severity.INFO
    return {
        "summary": SourceSummary(
            source=ConnectorType.VM,
            status=status,
            collected=True,
            message=f"Collected {len(evidence)} evidence items across {len(targets)} VM(s).",
            item_count=len(evidence),
        ),
        "evidence": evidence[:160],
        "actions": actions,
    }
