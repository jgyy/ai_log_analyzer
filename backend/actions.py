import subprocess
from typing import Iterable

from schemas import ActionExecutionResponse, ActionType, ExecutableAction


def find_action(action_id: str, actions: Iterable[ExecutableAction]) -> ExecutableAction | None:
    for action in actions:
        if action.id == action_id:
            return action
    return None


def execute_allowlisted_action(action: ExecutableAction) -> ActionExecutionResponse:
    command = _command_for_action(action)
    if not command:
        return ActionExecutionResponse(
            action_id=action.id,
            status="rejected",
            error="Action type is not allowlisted.",
        )

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except Exception as exc:
        return ActionExecutionResponse(action_id=action.id, status="failed", error=str(exc))

    status = "completed" if result.returncode == 0 else "failed"
    return ActionExecutionResponse(
        action_id=action.id,
        status=status,
        output=(result.stdout or "").strip()[:4000],
        error=(result.stderr or "").strip()[:4000],
    )


def _command_for_action(action: ExecutableAction) -> list[str] | None:
    if action.action_type == ActionType.RESTART_DOCKER_CONTAINER:
        return ["docker", "restart", action.target]
    if action.action_type == ActionType.START_DOCKER_CONTAINER:
        return ["docker", "start", action.target]
    if action.action_type == ActionType.STOP_DOCKER_CONTAINER:
        return ["docker", "stop", action.target]
    if action.action_type == ActionType.RESTART_SYSTEMD_SERVICE and action.target.endswith(".service"):
        return ["systemctl", "restart", action.target]
    return None
