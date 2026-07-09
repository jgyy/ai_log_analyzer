"""
VirtualBox connector: host-level VM lifecycle facts via VBoxManage, plus
optional guest-level diagnostics (reusing the same failure signatures the
Linux connector looks for) via `VBoxManage guestcontrol`, which reaches a
VM's guest OS through the hypervisor channel rather than the network — the
only path that still works when a VM's display stack or networking is
broken (black screen, no SSH, no console TTY).

Guest-level checks require diagnostic credentials to be registered for the
VM first (see crypto_utils.py / database.VMCredential). Host-level facts
(power state, snapshots, Guest Additions status) never require credentials.
"""
import re
import shutil
import subprocess
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from connectors import _evidence, _failure_summary, _run
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
    """
    return _run(
        [
            "VBoxManage", "guestcontrol", vm_name, "run",
            "--username", username,
            "--password", password,
            "--exe", "/bin/bash",
            "--",
            "bash", "-c", shell_command,
        ],
        timeout=timeout,
    )


def _collect_guest_diagnostics(vm_name: str, username: str, password: str) -> List:
    """
    Re-runs the same failure signatures the Linux connector looks for
    (failed units, disk pressure) plus the VM-specific display-stack /
    ownership-drift checks this connector adds, against a VM's guest OS.
    """
    evidence = []

    failed_units = _guest_run(vm_name, username, password, "systemctl --failed --no-legend --plain")
    if failed_units.returncode == 0 and failed_units.stdout.strip():
        for line in failed_units.stdout.splitlines()[:20]:
            parts = line.split()
            service_name = next((p for p in parts if p.endswith(".service")), parts[0] if parts else "systemd")
            evidence.append(_evidence(
                ConnectorType.VM,
                f"vm:{vm_name}:{service_name}",
                f"Failed systemd unit in guest: {line}",
                Severity.CRITICAL,
                {"vm": vm_name, "raw": line},
            ))

    # Display-stack crash signature (gdm-x-session Fatal server error, X
    # display retry exhaustion) — the exact pattern behind the black-screen
    # / non-blinking-cursor failure this connector was built to catch.
    gdm_journal = _guest_run(
        vm_name, username, password,
        "journalctl -u gdm3 -b --no-pager 2>/dev/null | tail -n 200",
    )
    if gdm_journal.returncode == 0 and gdm_journal.stdout.strip():
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

    # Ownership/permission drift — catches things like a broad `chown -R`
    # having reassigned system files to a regular user (dpkg -V flags mode/
    # owner mismatches against the package database, unlike debsums which
    # only checks file content).
    dpkg_verify = _guest_run(vm_name, username, password, "dpkg -V 2>/dev/null | head -n 50")
    if dpkg_verify.stdout.strip():
        mismatch_lines = [l for l in dpkg_verify.stdout.splitlines() if l.strip()]
        if mismatch_lines:
            evidence.append(_evidence(
                ConnectorType.VM,
                f"vm:{vm_name}:package-integrity",
                f"{len(mismatch_lines)} file(s) differ from their package-installed "
                f"state (ownership/permissions/content) — possible sign of a broad "
                f"chown/chmod having touched system files:\n" + "\n".join(mismatch_lines[:20]),
                Severity.WARNING,
                {"vm": vm_name},
            ))

    # Disk pressure — the "No space left on device" cascade seen when a
    # runaway log fills the guest's root filesystem.
    disk = _guest_run(vm_name, username, password, "df -h / 2>/dev/null")
    if disk.returncode == 0 and disk.stdout.strip():
        lines = disk.stdout.splitlines()
        if len(lines) > 1:
            usage_parts = lines[1].split()
            used_pct = usage_parts[4] if len(usage_parts) > 4 else "unknown"
            try:
                high_usage = used_pct.endswith("%") and int(used_pct[:-1]) >= 90
            except ValueError:
                high_usage = False
            evidence.append(_evidence(
                ConnectorType.VM,
                f"vm:{vm_name}:disk-cascade",
                f"Guest root filesystem usage is {used_pct}.",
                Severity.CRITICAL if high_usage else Severity.INFO,
                {"vm": vm_name, "raw": lines[1]},
            ))

    if failed_units.returncode != 0 and gdm_journal.returncode != 0 and dpkg_verify.returncode != 0:
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
                f"guest-level checks (display stack, package integrity, disk) "
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
