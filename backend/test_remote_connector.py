import subprocess
import unittest
from unittest.mock import MagicMock, patch

from schemas import ConnectorType


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class RemoteConnectorAvailabilityTests(unittest.TestCase):
    @patch("connectors_remote._PARAMIKO_AVAILABLE", False)
    def test_missing_paramiko_returns_partial_failure(self):
        import connectors_remote
        result = connectors_remote.collect_remote_evidence(None, "org-1", db=MagicMock())
        self.assertFalse(result["summary"].collected)
        self.assertEqual(result["summary"].source, ConnectorType.REMOTE)

    def test_no_configured_targets_returns_partial_failure(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        import connectors_remote
        result = connectors_remote.collect_remote_evidence(None, "org-1", db=db)
        self.assertFalse(result["summary"].collected)
        self.assertIn("No remote targets", result["evidence"][0].message)


class RemoteConnectorCredentialTests(unittest.TestCase):
    def _fake_target(self, auth_method="password"):
        target = MagicMock()
        target.name = "test-host"
        target.host = "10.0.0.5"
        target.port = 22
        target.username = "diag"
        target.auth_method = auth_method
        target.encrypted_secret = "encrypted"
        return target

    @patch("connectors_remote.decrypt_value")
    def test_undecryptable_secret_produces_warning_not_crash(self, decrypt_value):
        from crypto_utils import CredentialEncryptionError
        decrypt_value.side_effect = CredentialEncryptionError("bad key")

        import connectors_remote
        target = self._fake_target()
        evidence = connectors_remote._collect_target_evidence(target)

        self.assertEqual(len(evidence), 1)
        self.assertIn("Could not decrypt", evidence[0].message)
        self.assertEqual(evidence[0].severity.value, "warning")

    @patch("connectors_remote._connect")
    @patch("connectors_remote.decrypt_value")
    def test_connection_failure_degrades_to_warning_not_crash(self, decrypt_value, connect):
        decrypt_value.return_value = "s3cret"
        connect.side_effect = TimeoutError("connection timed out")

        import connectors_remote
        target = self._fake_target()
        evidence = connectors_remote._collect_target_evidence(target)

        self.assertEqual(len(evidence), 1)
        self.assertIn("Could not connect", evidence[0].message)
        self.assertEqual(evidence[0].severity.value, "warning")

    @patch("connectors_remote._connect")
    @patch("connectors_remote.decrypt_value")
    def test_successful_collection_reuses_shared_system_checks(self, decrypt_value, connect):
        decrypt_value.return_value = "s3cret"
        client = MagicMock()
        connect.return_value = client

        def fake_exec_command(command, timeout=None):
            stdout = MagicMock()
            stderr = MagicMock()
            if "systemctl" in command:
                stdout.read.return_value = b"nginx.service loaded failed failed Nginx\n"
            else:
                stdout.read.return_value = b""
            stderr.read.return_value = b""
            stdout.channel.recv_exit_status.return_value = 0
            return (MagicMock(), stdout, stderr)

        client.exec_command.side_effect = fake_exec_command

        import connectors_remote
        target = self._fake_target()
        evidence = connectors_remote._collect_target_evidence(target)

        client.close.assert_called_once()
        self.assertTrue(any("nginx.service" in item.message for item in evidence))


if __name__ == "__main__":
    unittest.main()
