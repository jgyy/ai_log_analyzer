# Add VirtualBox VM support (host lifecycle + guest diagnostics)

## Summary

Adds a new `virtualbox` evidence source alongside the existing Manual/Linux/Docker
connectors. The backend (running on the VirtualBox **host**) can now:

- List registered VMs and their power/snapshot/Guest Additions state
- Pull guest-level diagnostics (failed services, display-stack crash loops,
  package/ownership integrity drift, disk pressure) via `VBoxManage guestcontrol`
  — which reaches inside a VM through the hypervisor channel, so it still works
  even when the guest's network and display are both down
- Offer allowlisted remediation actions: start/stop/restart a VM, and restore
  the last snapshot (behind an explicit confirmation gate, both client- and
  server-side, since it's destructive)
- Supports any host (OS-agnostic) but only Linux guest currently

This was motivated by an actual debugging session where a VM went to a black
screen with a non-blinking cursor after a broad `chown -R` corrupted file
ownership across the guest — the guest-diagnostic checks (`dpkg -V` drift,
GDM/X crash-loop detection) are modeled directly on the checks that diagnosed
that incident manually.

## What's new

**Backend**
- `connectors_vm.py` — new VirtualBox connector (host facts + guest diagnostics)
- `crypto_utils.py` — lightweight Fernet-based encrypt/decrypt for storing VM
  guest credentials at rest (see **Security notes** below — this is explicitly
  not a KMS substitute)
- `database.py` — new `VMCredential` table, one row per (organization, VM name),
  username/password stored encrypted, unique constraint on org+VM
- `schemas.py` — `ConnectorType.VM`, new `ActionType`s (`start_vm`, `stop_vm`,
  `restart_vm`, `restore_vm_snapshot`, `restart_gdm_service`), `VMInfo`,
  `VMCredentialCreate`/`VMCredentialStatus`, `vm_targets` on the incident
  analysis request, `ActionExecutionRequest` (carries `confirm: bool`)
- `connectors.py` — `collect_sources()` now routes `ConnectorType.VM` to the
  new connector, given `db`/`organization_id`/`vm_targets`
- `actions.py` — `VBoxManage` command mapping for the new action types;
  `restore_vm_snapshot` is rejected server-side unless `confirm=true`
- `main.py`:
  - `GET /api/vms` — list VMs + per-org credential status (any authenticated user)
  - `POST/DELETE /api/vms/{vm_name}/credentials` — admin-only, never returns
    the stored secret back
  - `execute_action` now re-verifies a VM still exists immediately before
    running any VM lifecycle/snapshot action, and audit-logs the `confirm` flag
- `test_vm_connector.py` — 9 new tests (credential encryption round-trip,
  confirm-gating, missing-VBoxManage/credential fallbacks, display-stack
  detection, guest-command timeout handling)

**Frontend**
- `LogUploader.tsx` — new "VirtualBox VMs" evidence-source preset with a VM
  picker (fetched from `GET /api/vms`)
- `AppHeader.tsx` — new "VMs" nav item (admin/SRE)
- `app/dashboard/vms/page.tsx` — new admin page to view VM state and
  configure/remove diagnostic credentials (password never round-tripped to
  the client)
- `MitigationTab.tsx` — `restore_vm_snapshot` requires typing the VM name to
  confirm before the request is sent (in addition to the server-side gate)
- `AnalysisTab.tsx` / `types.ts` / `api.ts` — plumbing for the above
  (`vm_targets`, `confirm`, `VMInfo` type)

## Environment changes

`.env.example` has been updated to add:

```
VM_CREDENTIAL_ENCRYPTION_KEY=
```

**Action required for every environment (dev, staging, prod):** generate a
real value before this feature can be used —

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Also add `cryptography` to `requirements.txt` (not yet pinned in this PR —
whatever version your lockfile resolves is fine, no specific constraint needed).

If the key is unset, credential save/decrypt calls fail with a clear
`CredentialEncryptionError` rather than silently storing plaintext.

## Security notes / follow-ups

- Guest credentials are for **read-only diagnostics only**. Setup docs
  recommend a dedicated low-privilege guest account (e.g. `vm-diagnostics`,
  in the `systemd-journal` group only) — never a full admin/root login.
- `crypto_utils.py` is explicitly documented as a stand-in for a real
  secrets manager (Vault/KMS) — no key versioning, single env-sourced key.
  Rotating `VM_CREDENTIAL_ENCRYPTION_KEY` will make previously-stored
  credentials undecryptable; flagged in-code.
- `restore_vm_snapshot` requires explicit confirmation both client- and
  server-side, since it discards guest state irreversibly.
- **Follow-up (not in this PR):** the AI analysis prompt can currently
  over-escalate a single ambiguous `dpkg -V` mismatch (e.g. `/etc/sudoers`
  conffile drift, which is routinely modified by provisioning tooling) into
  language like "malware" or "system compromise." Prompt tightening to
  require corroborating evidence before that framing is a good fast-follow.

## Testing

- `python -m unittest discover` — 29/29 passing (20 pre-existing + 9 new)
- `npx tsc --noEmit` — clean on all new/modified frontend files
- Manually verified end-to-end against a real VirtualBox VM: credential
  setup, guest diagnostics (failed units, display-stack detection, package
  integrity, disk), snapshot-restore confirmation flow

## Out of scope for this PR

- Non-VirtualBox hypervisors (libvirt/KVM, cloud VM APIs)
- SSH-based guest access as an alternative to `guestcontrol`
- Prompt-level fix for AI over-escalation on ambiguous integrity findings
