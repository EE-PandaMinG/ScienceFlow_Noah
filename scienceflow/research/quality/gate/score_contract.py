"""Legacy score-contract policy shared by full-run owners."""

from __future__ import annotations

from typing import Any

from scienceflow.research.quality.gate.policy import legacy_score_contract_enabled
from scienceflow.runtime.safety.policy.execution_policy import (
    final_validation_score_contract_error,
    format_score_contract_repair_feedback,
)


def agent_gate_policy_context(agent: Any) -> tuple[str, str, str]:
    profile = str(getattr(agent, "_scienceflow_task_profile", "auto") or "auto")
    backend = str(getattr(agent, "_scienceflow_evaluator_backend", "") or "")
    artifact = str(getattr(agent, "_lnr_candidate_artifact_rel", "") or "")
    return profile, backend, artifact


def legacy_score_gate_enabled_for_agent(agent: Any) -> bool:
    profile, backend, artifact = agent_gate_policy_context(agent)
    return legacy_score_contract_enabled(
        task_profile=profile,
        evaluator_backend=backend,
        candidate_artifact=artifact,
    )


def score_contract_user_message(
    detail: str, *, script_label: str = "solution.py"
) -> str:
    return format_score_contract_repair_feedback(detail, script_label=script_label)


def score_contract_errors(stdout: str) -> tuple[str | None, str | None]:
    """Return hard parse errors separately from final-line warnings."""
    hard_error = final_validation_score_contract_error(
        stdout,
        require_present=True,
        require_final_line=False,
    )
    if hard_error:
        return hard_error, None
    soft_warning = final_validation_score_contract_error(
        stdout,
        require_present=True,
        require_final_line=True,
    )
    return None, soft_warning


__all__ = [
    "agent_gate_policy_context",
    "legacy_score_gate_enabled_for_agent",
    "score_contract_errors",
    "score_contract_user_message",
]
