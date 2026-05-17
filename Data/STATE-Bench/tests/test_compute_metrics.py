from scripts.compute_metrics import build_matrices, compute_summary


def test_compute_summary_includes_state_task_and_completion_rates():
    runs = [
        {
            "t1": {
                "task_id": "t1",
                "score": 5,
                "reasoning": "ok",
                "state_requirements_met": 1,
                "task_requirements_met": 1,
                "task_completion_pass": 1,
                "turns": 3,
                "tool_calls": 1,
                "input_tokens": 100,
                "cached_input_tokens": 50,
                "output_tokens": 10,
                "total_tokens": 110,
                "cost_usd": 0.001,
                "agent_turn_cost_usd": 0.0007,
                "memory_ingestion_cost_usd": 0.0002,
                "memory_retrieval_cost_usd": 0.0,
                "embedding_cost_usd": 0.0001,
                "embedding_input_tokens": 20,
            },
            "t2": {
                "task_id": "t2",
                "score": 2,
                "reasoning": "bad",
                "state_requirements_met": 1,
                "task_requirements_met": 0,
                "task_completion_pass": 0,
                "turns": 4,
                "tool_calls": 2,
                "input_tokens": 200,
                "cached_input_tokens": 0,
                "output_tokens": 20,
                "total_tokens": 220,
                "cost_usd": 0.002,
                "agent_turn_cost_usd": 0.0015,
                "memory_ingestion_cost_usd": 0.0,
                "memory_retrieval_cost_usd": 0.0002,
                "embedding_cost_usd": 0.0003,
                "embedding_input_tokens": 40,
            },
        },
        {
            "t1": {
                "task_id": "t1",
                "score": 3,
                "reasoning": "meh",
                "state_requirements_met": 0,
                "task_requirements_met": 1,
                "task_completion_pass": 0,
                "turns": 5,
                "tool_calls": 3,
                "input_tokens": 300,
                "cached_input_tokens": 100,
                "output_tokens": 30,
                "total_tokens": 330,
                "cost_usd": 0.003,
                "agent_turn_cost_usd": 0.002,
                "memory_ingestion_cost_usd": 0.0005,
                "memory_retrieval_cost_usd": 0.0002,
                "embedding_cost_usd": 0.0003,
                "embedding_input_tokens": 60,
            },
            "t2": {
                "task_id": "t2",
                "score": 4,
                "reasoning": "fine",
                "state_requirements_met": 1,
                "task_requirements_met": 1,
                "task_completion_pass": 1,
                "turns": 2,
                "tool_calls": 1,
                "input_tokens": 400,
                "cached_input_tokens": 150,
                "output_tokens": 40,
                "total_tokens": 440,
                "cost_usd": 0.004,
                "agent_turn_cost_usd": 0.003,
                "memory_ingestion_cost_usd": 0.0003,
                "memory_retrieval_cost_usd": 0.0004,
                "embedding_cost_usd": 0.0003,
                "embedding_input_tokens": 80,
            },
        },
    ]

    summary = compute_summary(build_matrices(runs))

    assert summary["state_pass@1"] == 0.75
    assert summary["task_requirements_pass@1"] == 0.75
    assert summary["task_completion_pass@1"] == 0.5
    assert summary["per_run_state_pass_counts"] == [2, 1]
    assert summary["per_run_task_requirements_pass_counts"] == [1, 2]
    assert summary["per_run_task_completion_pass_counts"] == [1, 1]
    assert summary["mean_cost_usd"] == 0.0025
    assert summary["mean_cost_usd_pass"] == 0.0025
    assert summary["mean_input_tokens"] == 250.0
    assert summary["mean_cached_input_tokens"] == 75.0
    assert summary["mean_output_tokens"] == 25.0
    assert summary["mean_total_tokens"] == 275.0
    assert summary["mean_embedding_input_tokens"] == 50.0
    assert summary["mean_agent_turn_cost_usd"] == 0.0018
    assert summary["mean_memory_ingestion_cost_usd"] == 0.00025
    assert summary["mean_memory_retrieval_cost_usd"] == 0.0002
    assert summary["mean_embedding_cost_usd"] == 0.00025
    assert "pass^2" not in summary


def test_compute_summary_includes_ux_scores():
    runs = [
        {
            "t1": {
                "task_id": "t1",
                "score": 1,
                "ux_score": 4.2,
                "reasoning": "ok",
                "state_requirements_met": 1,
                "task_requirements_met": 1,
                "task_completion_pass": 1,
                "turns": 3,
                "tool_calls": 1,
                "input_tokens": 100,
                "cached_input_tokens": 0,
                "output_tokens": 10,
                "total_tokens": 110,
                "cost_usd": 0.001,
                "agent_turn_cost_usd": 0.0008,
                "memory_ingestion_cost_usd": 0.0001,
                "memory_retrieval_cost_usd": 0.0,
                "embedding_cost_usd": 0.0001,
                "embedding_input_tokens": 10,
            }
        },
        {
            "t1": {
                "task_id": "t1",
                "score": 0,
                "ux_score": 3.8,
                "reasoning": "bad",
                "state_requirements_met": 0,
                "task_requirements_met": 0,
                "task_completion_pass": 0,
                "turns": 5,
                "tool_calls": 2,
                "input_tokens": 200,
                "cached_input_tokens": 50,
                "output_tokens": 20,
                "total_tokens": 220,
                "cost_usd": 0.002,
                "agent_turn_cost_usd": 0.0014,
                "memory_ingestion_cost_usd": 0.0002,
                "memory_retrieval_cost_usd": 0.0002,
                "embedding_cost_usd": 0.0002,
                "embedding_input_tokens": 30,
            }
        },
    ]

    summary = compute_summary(build_matrices(runs))

    assert summary["mean_ux_score"] == 4.0
    assert summary["per_run_ux_scores"] == [4.2, 3.8]
