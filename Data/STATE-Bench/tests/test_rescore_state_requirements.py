"""Tests for rescore integration with deterministic state requirements."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from scripts.rescore import rescore_one


def test_rescore_writes_state_requirement_fields(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_path = tasks_dir / "1-cancel_economy_domestic.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "1-cancel_economy_domestic",
                "task_summary": "Task summary",
                "state_requirements": [
                    {
                        "entity_type": "bookings",
                        "record_key": "BK-1000",
                        "field": "status",
                        "expected_value": "cancelled",
                    }
                ],
                "task_requirements": [{"id": "r1", "kind": "must", "requirement": "warn about the connection", "evidence": "conversation"}],
                "user_id": "user_001",
                "opening_message": "hello",
                "user_simulator": {"personality": "cooperative", "user_sim_context": "User simulator context", "known_info": [], "unknown_info": [], "task_rules": []},
            }
        )
    )

    traj_path = tmp_path / "traj.json"
    traj_path.write_text(
        json.dumps(
            {
                "task_id": "1-cancel_economy_domestic",
                "conversation": [{"role": "user", "content": "cancel it"}],
                "state_diff": {
                    "created": {},
                    "modified": {"bookings": {"BK-1000": {"status": {"old": "confirmed", "new": "cancelled"}}}},
                    "deleted": {},
                },
            }
        )
    )

    task_requirements_judge = MagicMock()
    task_requirements_judge.evaluate.return_value = type("TaskReqResult", (), {
        "score": 1,
        "reasoning": "task requirements pass",
        "details": [{"id": "r1", "passed": True}],
    })()

    output_path = tmp_path / "out.json"
    result = rescore_one(traj_path, tasks_dir, task_requirements_judge, None, output_path)
    saved = json.loads(output_path.read_text())

    assert result["status"] == "OK"
    assert saved["state_requirements_met"] == 1
    assert "matched the saved state_diff" in saved["state_requirements_reasoning"]
    assert saved["task_requirements_met"] == 1
    assert saved["task_requirements_reasoning"] == "task requirements pass"
    assert saved["task_requirements_details"] == [{"id": "r1", "passed": True}]
    assert saved["task_completion_pass"] == 1



def test_rescore_can_write_ux_fields_only(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "1-cancel_economy_domestic.json").write_text(
        json.dumps(
            {
                "task_id": "1-cancel_economy_domestic",
                "task_summary": "Task summary",
                "user_id": "user_001",
                "opening_message": "hello",
                "user_simulator": {"personality": "cooperative", "user_sim_context": "User simulator context", "known_info": [], "unknown_info": [], "task_rules": []},
            }
        )
    )

    traj_path = tmp_path / "traj.json"
    traj_path.write_text(json.dumps({"task_id": "1-cancel_economy_domestic", "conversation": [{"role": "user", "content": "cancel it"}], "state_diff": {"created": {}, "modified": {}, "deleted": {}}}))

    ux_judge = MagicMock()
    ux_judge.evaluate.return_value = MagicMock(
        consent=4, ease=3, discovery=5, information_quality=4, disambiguation=3, ux_score=3.8, reasoning="ux ok"
    )

    output_path = tmp_path / "out.json"
    result = rescore_one(traj_path, tasks_dir, None, ux_judge, output_path)
    saved = json.loads(output_path.read_text())

    assert result["status"] == "OK"
    assert result["ux_score"] == 3.8
    assert saved["ux_consent"] == 4
    assert saved["ux_ease"] == 3
    assert saved["ux_discovery"] == 5
    assert saved["ux_information_quality"] == 4
    assert saved["ux_disambiguation"] == 3
    assert saved["ux_score"] == 3.8
    assert saved["ux_reasoning"] == "ux ok"

