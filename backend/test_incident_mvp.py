import subprocess
import unittest
from unittest.mock import patch

from actions import execute_allowlisted_action
from connectors import collect_docker_evidence, collect_linux_evidence
from schemas import ActionType, ConnectorType, ExecutableAction, Severity


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class ConnectorTests(unittest.TestCase):
    @patch("connectors.shutil.which")
    @patch("connectors._run")
    def test_linux_connector_collects_failed_services(self, run, which):
        which.return_value = "/usr/bin/tool"

        def fake_run(command, timeout=8):
            if command[:2] == ["systemctl", "--failed"]:
                return completed("nginx.service loaded failed failed Web Server\n")
            if command[0] == "journalctl":
                return completed("2026-07-03T10:00:00 host nginx.service: failed to bind port\n")
            if command[0] == "df":
                return completed("Filesystem Size Used Avail Use% Mounted on\n/dev/root 20G 18G 2G 90% /\n")
            if command[0] == "free":
                return completed("Mem: 1000 800 200\n")
            if command[0] == "uptime":
                return completed("10:00 up 1 day, load average: 1.00, 0.50, 0.25\n")
            return completed()

        run.side_effect = fake_run
        result = collect_linux_evidence()

        self.assertTrue(result["summary"].collected)
        self.assertEqual(result["summary"].status, Severity.CRITICAL)
        self.assertTrue(any(item.component == "nginx.service" for item in result["evidence"]))
        self.assertTrue(any(action.id == "systemd-restart:nginx.service" for action in result["actions"]))

    @patch("connectors.shutil.which")
    @patch("connectors._run")
    def test_docker_connector_collects_unhealthy_container_actions(self, run, which):
        which.return_value = "/usr/bin/docker"

        def fake_run(command, timeout=8):
            if command[:2] == ["docker", "ps"]:
                return completed('{"ID":"abc123","Names":"api","Image":"example/api","State":"exited","Status":"Exited (1)"}\n')
            if command[:2] == ["docker", "logs"]:
                return completed("ERROR database connection refused\n")
            return completed()

        run.side_effect = fake_run
        result = collect_docker_evidence()

        self.assertTrue(result["summary"].collected)
        self.assertEqual(result["summary"].status, Severity.CRITICAL)
        self.assertTrue(any(item.component == "api" for item in result["evidence"]))
        self.assertTrue(any(action.id == "docker-restart:abc123" for action in result["actions"]))

    @patch("connectors.shutil.which")
    def test_docker_connector_returns_partial_failure(self, which):
        which.return_value = None
        result = collect_docker_evidence()

        self.assertFalse(result["summary"].collected)
        self.assertEqual(result["summary"].source, ConnectorType.DOCKER)
        self.assertEqual(result["summary"].status, Severity.WARNING)


class ActionTests(unittest.TestCase):
    def test_rejects_non_service_systemd_target(self):
        action = ExecutableAction(
            id="systemd-restart:sshd",
            label="Restart sshd",
            action_type=ActionType.RESTART_SYSTEMD_SERVICE,
            target="sshd",
            source=ConnectorType.LINUX,
        )

        result = execute_allowlisted_action(action)
        self.assertEqual(result.status, "rejected")

    @patch("actions.subprocess.run")
    def test_executes_allowlisted_docker_restart(self, run):
        run.return_value = completed("container restarted\n")
        action = ExecutableAction(
            id="docker-restart:abc123",
            label="Restart api",
            action_type=ActionType.RESTART_DOCKER_CONTAINER,
            target="abc123",
            source=ConnectorType.DOCKER,
        )

        result = execute_allowlisted_action(action)
        self.assertEqual(result.status, "completed")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["docker", "restart", "abc123"])


if __name__ == "__main__":
    unittest.main()
