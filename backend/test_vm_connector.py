import subprocess
import unittest
from unittest.mock import MagicMock, patch

from actions import execute_allowlisted_action
from schemas import ActionType, ConnectorType, ExecutableAction


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class CryptoUtilsTests(unittest.TestCase):
    def test_encrypt_decrypt_round_trips(self):
        import os
        from cryptography.fernet import Fernet
        os.environ["VM_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        import crypto_utils
        crypto_utils._get_fernet.cache_clear()

        encrypted = crypto_utils.encrypt_value("s3cret-password")
        self.assertNotEqual(encrypted, "s3cret-password")
        self.assertEqual(crypto_utils.decrypt_value(encrypted), "s3cret-password")

    def test_missing_key_raises_clear_error(self):
        import os
        os.environ.pop("VM_CREDENTIAL_ENCRYPTION_KEY", None)

        import crypto_utils
        crypto_utils._get_fernet.cache_clear()

        with self.assertRaises(crypto_utils.CredentialEncryptionError):
            crypto_utils.encrypt_value("anything")


class VMActionGatingTests(unittest.TestCase):
    def test_snapshot_restore_rejected_without_confirmation(self):
        action = ExecutableAction(
            id="vm-restore-snapshot:test-vm",
            label="Restore last snapshot",
            action_type=ActionType.RESTORE_VM_SNAPSHOT,
            target="test-vm",
            source=ConnectorType.VM,
        )
        result = execute_allowlisted_action(action, confirm=False)
        self.assertEqual(result.status, "rejected")
        self.assertIn("confirm=true", result.error)

    @patch("actions.subprocess.run")
    def test_snapshot_restore_executes_when_confirmed(self, run):
        run.return_value = completed("snapshot restored\n")
        action = ExecutableAction(
            id="vm-restore-snapshot:test-vm",
            label="Restore last snapshot",
            action_type=ActionType.RESTORE_VM_SNAPSHOT,
            target="test-vm",
            source=ConnectorType.VM,
        )
        result = execute_allowlisted_action(action, confirm=True)
        self.assertEqual(result.status, "completed")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["VBoxManage", "snapshot", "test-vm", "restorecurrent"])

    @patch("actions.subprocess.run")
    def test_start_vm_uses_headless_type(self, run):
        run.return_value = completed("started\n")
        action = ExecutableAction(
            id="vm-start:test-vm",
            label="Start VM",
            action_type=ActionType.START_VM,
            target="test-vm",
            source=ConnectorType.VM,
        )
        result = execute_allowlisted_action(action)
        self.assertEqual(result.status, "completed")
        self.assertEqual(run.call_args.args[0], ["VBoxManage", "startvm", "test-vm", "--type", "headless"])


class VMConnectorTests(unittest.TestCase):
    @patch("connectors_vm.shutil.which")
    def test_no_vboxmanage_returns_partial_failure(self, which):
        which.return_value = None
        import connectors_vm
        result = connectors_vm.collect_vm_evidence(None, "org-1", db=MagicMock())
        self.assertFalse(result["summary"].collected)
        self.assertEqual(result["summary"].source, ConnectorType.VM)

    @patch("connectors_vm._get_credential")
    @patch("connectors_vm.get_vm_info")
    @patch("connectors_vm.shutil.which")
    def test_missing_credentials_produce_warning_not_failure(self, which, get_vm_info, get_credential):
        which.return_value = "/usr/bin/VBoxManage"
        get_vm_info.return_value = {
            "name": "test-vm", "uuid": "abc", "state": "running",
            "guest_additions_running": True, "guest_os": "Debian",
            "memory_mb": "2048", "snapshot_count": 1,
        }
        get_credential.return_value = None

        import connectors_vm
        result = connectors_vm.collect_vm_evidence(["test-vm"], "org-1", db=MagicMock())

        self.assertTrue(result["summary"].collected)
        messages = [e.message for e in result["evidence"]]
        self.assertTrue(any("No diagnostic credentials configured" in m for m in messages))
        # Lifecycle + snapshot-restore actions should still be offered even
        # without guest credentials, since they don't require guest access.
        action_types = {a.action_type for a in result["actions"]}
        self.assertIn(ActionType.RESTART_VM, action_types)
        self.assertIn(ActionType.RESTORE_VM_SNAPSHOT, action_types)

    @patch("connectors_vm._guest_run")
    @patch("connectors_vm._get_credential")
    @patch("connectors_vm.get_vm_info")
    @patch("connectors_vm.shutil.which")
    def test_display_stack_crash_detected_as_critical(self, which, get_vm_info, get_credential, guest_run):
        which.return_value = "/usr/bin/VBoxManage"
        get_vm_info.return_value = {
            "name": "test-vm", "uuid": "abc", "state": "running",
            "guest_additions_running": True, "guest_os": "Debian",
            "memory_mb": "2048", "snapshot_count": 0,
        }
        get_credential.return_value = ("diag-user", "diag-pass")

        def fake_guest_run(vm_name, username, password, shell_command, timeout=15):
            if "gdm3" in shell_command:
                return completed("gdm-x-session[1543]: (EE) Fatal server error:\nmaximum number of X display failures reached\n")
            return completed("")

        guest_run.side_effect = fake_guest_run

        import connectors_vm
        result = connectors_vm.collect_vm_evidence(["test-vm"], "org-1", db=MagicMock())

        display_evidence = [e for e in result["evidence"] if "display-stack" in e.component]
        self.assertTrue(len(display_evidence) > 0)
        self.assertEqual(display_evidence[0].severity.value, "critical")


if __name__ == "__main__":
    unittest.main()
