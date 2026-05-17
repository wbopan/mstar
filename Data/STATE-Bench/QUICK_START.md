# Quick Start

Run an AI agent against the benchmark tasks in under 5 minutes.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure OpenAI endpoint(s) with GPT-4.1 (or compatible) deployments

## 1. Install dependencies

```bash
uv sync
```

## 2. Configure Azure OpenAI

Create a `.env` file (or export these variables):

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENTS=gpt-4.1       # comma-separated deployment names
AZURE_OPENAI_API_VERSION=2025-03-01-preview

# Optional: additional endpoints for higher throughput
AZURE_OPENAI_ENDPOINT_2=https://your-second-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENTS_2=gpt-4.1
```

The client auto-discovers all `ENDPOINT_N` / `DEPLOYMENTS_N` pairs and load-balances across them.

## 3. Generate tasks and task environments

```bash
uv run python scripts/generate_tasks.py --domain travel
uv run python scripts/generate_tasks.py --domain customer_support
uv run python scripts/generate_tasks.py --domain shopping_assistant
```

This creates per domain:
- `domains/<domain>/tasks/*.json` — numbered task definitions
- `domains/<domain>/task_envs/*.json` — per-task environment snapshots referenced by `task_env_path`

Use `--check` to verify that checked-in task artifacts still match the current generator logic without rewriting files.

```bash
uv run python scripts/generate_tasks.py --domain travel --check
```

## 4. Run a single task

```bash
uv run python scripts/run_task.py --task 1-cancel_economy_domestic --domain travel
```

Run multiple times to measure stability:

```bash
uv run python scripts/run_task.py --task 1-cancel_economy_domestic --num-runs 3
```

Output: trajectory JSONs saved to `outputs/<domain>/run{N}/{task_id}.json`. Task definitions load their environment through `task_env_path` via the shared env loader.

## 5. Run all tasks

```bash
# Run all tasks × 3 runs (25 parallel workers by default)
uv run python scripts/run_batch.py --domain travel --num-runs 3

# Run specific tasks
uv run python scripts/run_batch.py --domain travel --tasks 1-cancel_economy_domestic,2-cancel_business_international

# Control parallelism
uv run python scripts/run_batch.py --domain travel --num-runs 3 --workers 10
```

## 6. Run with a custom agent

`VanillaAgent` is the built-in default benchmark agent. It has no memory layer. It just runs the normal tool-calling loop against the task.

For a new custom memory agent, the usual workflow is:

1. Run `VanillaAgent` first to generate baseline trajectories.
2. Ingest those saved trajectories into your own memory store.
3. Run your custom memory agent on the same tasks.
4. Rescore both result sets and compare metrics.

Put your agent implementation in `agents/`, for example `agents/my_agent.py`, and give it a class name such as `MyMemoryAgent`.

The runner auto-discovers every agent class in `agents/`. If your file defines `class MyMemoryAgent(...)`, you run it with `--agent MyMemoryAgent`. There is no registry to update.

Start by extending `VanillaAgent`. It already implements the normal Responses API loop, tool calling, and tool-result chaining. Your code only needs to add memory retrieval before the turn and memory ingestion after the task.

If your memory backend is already populated from somewhere else, you can skip the baseline run and just run your custom agent directly. But for the common "learn from prior benchmark trajectories" setup, yes: run vanilla first, ingest those trajectories, then evaluate your memory agent.

### Recommended evaluation workflow

Run the baseline into its own output directory:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --num-runs 3 \
  --output-dir outputs/travel_vanilla
```

Then ingest those saved trajectory files into your own memory backend. This ingestion step is owned by your agent system, not by the benchmark harness. For example, your ingestion script or service can read `outputs/travel_vanilla/run*/` and store memories in your database or vector index.

Then run your memory agent into a separate output directory:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --agent MyMemoryAgent \
  --agent-config configs/my_agent_memory.json \
  --num-runs 3 \
  --output-dir outputs/travel_memory
```

Then score and compare both directories:

```bash
uv run python scripts/rescore.py \
  --domain travel \
  --num-runs 3 \
  --source-dir outputs/travel_vanilla

uv run python scripts/rescore.py \
  --domain travel \
  --num-runs 3 \
  --source-dir outputs/travel_memory

uv run python scripts/compute_metrics.py \
  --results-dir outputs/travel_vanilla \
  --num-runs 3

uv run python scripts/compute_metrics.py \
  --results-dir outputs/travel_memory \
  --num-runs 3 \
  --compare outputs/travel_vanilla
```

Keep baseline and custom-agent runs in separate output directories. That makes ingestion, rescoring, and metric comparison much cleaner.

### Minimal `VanillaAgent` example

```python
from agents.base import AgentRuntimeContext
from agents.vanilla import VanillaAgent

class MyMemoryAgent(VanillaAgent):
    def __init__(
        self,
        client,
        system_prompt,
        tools,
        tool_handlers,
        runtime_context: AgentRuntimeContext | None = None,
    ):
        super().__init__(client, system_prompt, tools, tool_handlers, runtime_context=runtime_context)
        self.config = runtime_context.config if runtime_context else {}

    def prepare_conversation(self, conversation):
        return conversation

    def ingest_trajectory(self, trajectory):
        return None
```

### What the harness passes

Your custom agent is instantiated with:
- `client`
- `system_prompt`
- `tools`
- `tool_handlers`
- optional `runtime_context`

If your constructor accepts `runtime_context`, it contains:
- `task_id`, `user_id`, `domain`, `now`
- `output_dir`, `run_idx`
- `task_summary`
- `state_requirements`
- `task_requirements`
- `config`

`config` comes from `--agent-config path/to/config.json`.

In concrete terms, `--agent-config` is just a JSON blob that the runner loads once and forwards to `runtime_context.config`. The benchmark does not interpret those fields. They are entirely for your agent, for example memory backend URLs, retrieval depth, feature flags, or model settings.

This means the benchmark does not know how your memory store works. It only gives your agent the hooks and config needed to talk to it.

### Example memory pattern

This is the most common custom-agent pattern: ingest completed trajectories, retrieve relevant memories later, and append them to a temporary system message before the latest user turn.

In this example, memories are scoped by `task_id`. A trajectory from task A is only retrieved when solving task A again.

```python
from collections import defaultdict
from agents.base import AgentRuntimeContext
from agents.vanilla import VanillaAgent

class InMemoryStore:
    def __init__(self):
        self.by_task = defaultdict(list)

    def retrieve(self, task_id: str, k: int = 5) -> list[str]:
        return self.by_task.get(task_id, [])[-k:]

    def ingest(self, task_id: str, trajectory) -> None:
        summary = f"Completed task {task_id} in {len(trajectory.conversation)} messages"
        self.by_task[task_id].append(summary)

class MemoryAgent(VanillaAgent):
    def __init__(
        self,
        client,
        system_prompt,
        tools,
        tool_handlers,
        runtime_context: AgentRuntimeContext | None = None,
    ):
        super().__init__(client, system_prompt, tools, tool_handlers, runtime_context=runtime_context)
        self.runtime_context = runtime_context
        self.memory_store = InMemoryStore()

    def prepare_conversation(self, conversation):
        task_id = self.runtime_context.task_id if self.runtime_context else ""
        memories = self.memory_store.retrieve(task_id, k=5)
        if not memories:
            return conversation

        memory_text = "\n".join(f"- {m}" for m in memories)
        return self.inject_system_message(
            conversation,
            "Relevant memories from past trajectories for this task:\n" + memory_text,
            before_last_user=True,
        )

    def ingest_trajectory(self, trajectory):
        task_id = self.runtime_context.task_id if self.runtime_context else ""
        if task_id:
            self.memory_store.ingest(task_id, trajectory)
```

### Cost Tracking For Memory Agents

The benchmark's `cost_usd` metric includes all **agent-side model spend** and excludes simulator and judge cost.

That means:
- normal `VanillaAgent` solve calls are tracked automatically
- if your memory agent makes extra LLM calls for retrieval or ingestion, record them with `self.add_response_usage(...)`
- if your memory agent creates embeddings, record them with `self.add_embedding_usage(...)`

Example:

```python
def prepare_conversation(self, conversation):
    query_response = self.client.complete_json_response(
        prompt="Rewrite this user turn as a retrieval query",
        system_prompt="Return JSON only.",
    )
    self.add_response_usage(query_response.usage, category="memory_retrieval")

    self.add_embedding_usage(
        input_tokens=120,
        model_name="text-embedding-3-large",
        category="memory_retrieval",
    )

    memories = self.memory_store.retrieve(self.runtime_context.task_id, k=5)
    if not memories:
        return conversation
    return self.inject_system_message(
        conversation,
        "Relevant memories:\n" + "\n".join(memories),
        before_last_user=True,
    )
```

Use these categories:
- `agent_turn`
- `memory_ingestion`
- `memory_retrieval`

In `--verbose`, metrics will then show the cost breakdown by bucket.

### Optional `--agent-config`

Example config file:

```json
{
  "top_k": 5,
  "memory_url": "http://localhost:9000",
  "reasoning_effort": "medium"
}
```

Inside your agent, read it from `runtime_context.config`.

For example, if `configs/my_agent_memory.json` contains `{"top_k": 5}`, then inside your agent `runtime_context.config["top_k"]` will be `5`.

### Run your custom agent

If you already populated your memory store, you can run one task directly:

```bash
uv run python scripts/run_task.py \
  --task 1-cancel_economy_domestic \
  --domain travel \
  --agent MyMemoryAgent \
  --agent-config configs/my_agent_memory.json
```

Run a full batch:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --agent MyMemoryAgent \
  --agent-config configs/my_agent_memory.json \
  --num-runs 3
```

Run and score inline in one step:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --agent MyMemoryAgent \
  --agent-config configs/my_agent_memory.json \
  --num-runs 3 \
  --score-all
```

Without inline scoring, run these after trajectories are written:

```bash
uv run python scripts/rescore.py --domain travel --num-runs 3 --judge-type all
uv run python scripts/compute_metrics.py --domain travel --num-runs 3 --verbose
```

See the bring-your-own-memory section in [README.md](README.md) for the full contract and additional examples.

## 7. Rescore trajectories

```bash
uv run python scripts/rescore.py --domain travel --num-runs 3
```

Rescoring adds canonical task-completion and UX fields to the saved outputs.

## 8. Compute metrics

```bash
uv run python scripts/compute_metrics.py --domain travel --num-runs 3 --verbose
```

Produces:
- `outputs/<domain>/metrics.json` — aggregate metrics
- `outputs/<domain>/per_task_metrics/{task_id}.json` — per-task breakdowns with per-run scores and reasoning

## 9. Read results

Each rescored trajectory JSON contains fields such as:

```json
{
  "task_id": "1-cancel_economy_domestic",
  "user_id": "user_002",
  "state_requirements_met": 1,
  "task_requirements_met": 0,
  "task_completion_pass": 0,
  "task_requirements_reasoning": "Agent completed the cancellation but did not satisfy the non-state communication requirement.",
  "ux_score": 3.8,
  "turns": 5,
  "tool_calls": 3,
  "conversation": [...]
}
```

**Pass** = `task_completion_pass == 1`.

Primary metrics are task-completion rate, UX aggregates, efficiency-on-pass (`mean_turns_pass`, `mean_tool_calls_pass`), and optional verbose UX dimension breakdowns.
