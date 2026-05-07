# STATE-Bench

A multi-domain benchmark for evaluating AI agents with agentic memory. It measures whether agents can learn from prior trajectories and improve on realistic enterprise tasks.

## Current Benchmark Shape

The checked-in benchmark currently contains 450 tasks.

| Domain | Tasks | Description |
|--------|-------|-------------|
| **Travel** | 150 | Flights, hotels, and car rentals with cancellations, rebookings, fee calculations, policy reasoning, and multi-step booking flows |
| **Customer Support** | 150 | Returns, refunds, exchanges, warranties, shipping claims, and challenge scenarios with policy gates and two-step enforcement |
| **Shopping Assistant** | 150 | Product search, comparison, cart management, promo codes, and compatibility checks |


## Train/Test Splits

Train/test splits are manifest-only: task JSON files, task IDs, registry order, task environments, and trajectory paths stay unchanged. Consumers should read the split manifest and filter task IDs from it.

| Domain | Split Manifest | Status |
|--------|----------------|--------|
| **Travel** | [`domains/travel/splits/train_test_v1.json`](domains/travel/splits/train_test_v1.json) | 100 train / 50 test |
| **Customer Support** | [`domains/customer_support/splits/train_test_v1.json`](domains/customer_support/splits/train_test_v1.json) | 100 train / 50 test |
| **Shopping Assistant** | [`domains/shopping_assistant/splits/train_test_v1.json`](domains/shopping_assistant/splits/train_test_v1.json) | 100 train / 50 test |

Each split manifest includes `splits.train`, `splits.test`, per-task metadata, and summary counts. Its `task_type` values come from the task JSONs; `scenario_family` appears only as generation provenance for split balancing.

## Quick Start

See [QUICK_START.md](QUICK_START.md) for setup and a minimal walkthrough.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure OpenAI API access

```bash
AZURE_OPENAI_API_VERSION=2025-03-01-preview
AZURE_OPENAI_ENDPOINT_1=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENTS_1=gpt-5.1-001,gpt-5.1-002,gpt-5.1-003
```

You can provide additional pooled endpoints with `AZURE_OPENAI_ENDPOINT_2`, `AZURE_OPENAI_DEPLOYMENTS_2`, and so on. Agent, simulator, and judge traffic all use the same pooled client; separate `_JUDGE` environment variables are no longer used.

## Workflow

The benchmark flow is split into four stages.

1. Generate checked-in task definitions and per-task environment snapshots.
2. Run agents and save trajectories.
3. Rescore saved trajectories for task completion and UX.
4. Compute aggregate metrics from judged outputs.

```bash
# Generate tasks and per-task environments
uv run python scripts/generate_tasks.py --domain travel
uv run python scripts/generate_tasks.py --domain customer_support
uv run python scripts/generate_tasks.py --domain shopping_assistant

# Validate checked-in artifacts against current generation logic
uv run python scripts/generate_tasks.py --domain travel --check
uv run python scripts/generate_tasks.py --domain customer_support --check

# Run a single task
uv run python scripts/run_task.py --task 1-cancel_economy_domestic --domain travel

# Run a full batch
uv run python scripts/run_batch.py --domain travel --num-runs 3
uv run python scripts/run_batch.py --domain travel --agent MyMemoryAgent --num-runs 3

# Rescore existing trajectories
uv run python scripts/rescore.py --domain travel --num-runs 3
uv run python scripts/rescore.py --domain travel --num-runs 3 --judge-type all
uv run python scripts/rescore.py --domain travel --num-runs 3 --reasoning-effort high

# Compute metrics from judged trajectories
uv run python scripts/compute_metrics.py --domain travel --num-runs 3
uv run python scripts/compute_metrics.py --results-dir outputs/travel --num-runs 3 --verbose

# Audit tasks and trajectories
uv run python scripts/audit.py --domain travel --phase pre
uv run python scripts/audit.py --domain travel --phase post
uv run python scripts/audit.py --domain travel --phase all --llm-review
```

## Scoring And Metrics

| Dimension | Method |
|-----------|--------|
| **Task Completion** | Combined binary metric from deterministic state checks plus judged non-state task requirements. |
| **UX** | Judge-generated `ux_score` plus dimension-level scores for consent, ease, discovery, information quality, and disambiguation. |
| **Efficiency** | Deterministic: turns and tool calls, plus pass-only efficiency aggregates. |

Primary aggregate outputs are `state_pass@1`, `task_requirements_pass@1`, `task_completion_pass@1`, mean UX metrics, `mean_turns`, `mean_turns_pass`, `mean_tool_calls`, and `mean_tool_calls_pass`.

## Bring Your Own Memory Agent

The benchmark ships a `VanillaAgent` with no memory. Your custom memory agent should normally subclass `VanillaAgent` and add retrieval and ingestion hooks on top of the default tool-calling loop.

The harness stays memory-agnostic. It does not manage your memory backend, embeddings, indexing, or storage. Instead, it provides a stable lifecycle for custom agents:

- Discovery: put a file in `agents/`, for example `agents/my_agent.py`, and define a uniquely named class such as `MyMemoryAgent`. Run with `--agent MyMemoryAgent`.
- Construction: the runner instantiates your class with `client`, `system_prompt`, `tools`, and `tool_handlers`.
- Optional runtime context: if your constructor accepts `runtime_context=...`, the runners pass task metadata and a free-form config payload from `--agent-config path/to/config.json`.
- Pre-turn retrieval: override `prepare_conversation()` to retrieve memories and inject a system message into the current turn input.
- Post-run ingestion: override `ingest_trajectory()` to ingest the finished trajectory into your own store.

### Recommended Workflow

For a new memory agent, the normal evaluation flow is:

1. Run `VanillaAgent` first to generate baseline trajectories.
2. Ingest those saved trajectories into your own memory backend.
3. Run your custom memory agent on the same tasks.
4. Rescore both result sets and compare metrics.

Keep baseline and custom-agent runs in separate output directories so ingestion and metric comparison stay clean.

Example:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --num-runs 3 \
  --output-dir outputs/travel_vanilla

# Your own ingestion step reads outputs/travel_vanilla/run*/

uv run python scripts/run_batch.py \
  --domain travel \
  --agent MyMemoryAgent \
  --agent-config configs/my_agent_memory.json \
  --num-runs 3 \
  --output-dir outputs/travel_memory

uv run python scripts/rescore.py \
  --domain travel \
  --num-runs 3 \
  --source-dir outputs/travel_vanilla

uv run python scripts/rescore.py \
  --domain travel \
  --num-runs 3 \
  --source-dir outputs/travel_memory

uv run python scripts/compute_metrics.py \
  --results-dir outputs/travel_memory \
  --num-runs 3 \
  --compare outputs/travel_vanilla
```

### What `VanillaAgent` Gives You

- `VanillaAgent` is the built-in baseline agent.
- It has no memory layer.
- It already implements the standard Responses API loop and tool execution.
- Your custom memory agent usually only needs to override `prepare_conversation()` and `ingest_trajectory()`.

### Pattern 1: Retrieval + System Message Injection

This is the default custom-agent pattern. Extend `VanillaAgent`, retrieve memories before the LLM call, and inject them as a temporary system message just before the latest user message.

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

This pattern shows the two key hooks together:
- `ingest_trajectory()` ingests the completed trajectory into your store
- `prepare_conversation()` retrieves stored memories and appends them as a temporary system message before the latest user turn

### Cost Accounting For Custom Agents

The benchmark now reports `cost_usd` as total **agent-side model spend** for a task.

Included:
- normal Responses API calls made while solving the task
- memory ingestion or memory retrieval LLM calls made by your agent
- embedding-model calls, if your memory system uses embeddings

Excluded:
- user simulator
- judge or rescoring calls
- vector DB or storage infrastructure cost

If your custom agent makes extra model calls outside the default `VanillaAgent` turn loop, record them explicitly:

```python
response = self.client.complete_json_response(...)
self.add_response_usage(response.usage, category="memory_retrieval")

self.add_embedding_usage(
    input_tokens=1536,
    model_name="text-embedding-3-large",
    category="memory_retrieval",
)
```

Valid categories are:
- `agent_turn`
- `memory_ingestion`
- `memory_retrieval`

This keeps the top-level `cost_usd` metric correct while also exposing a verbose breakdown.

Run it through the pipeline the same way as any custom agent:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --agent MemoryAgent \
  --agent-config configs/my_agent_memory.json \
  --num-runs 3 \
  --score-all
```

### Pattern 2: Memory Tool

Add a retrieval tool so the model can query memory on demand. Your retrieval backend still lives entirely inside your agent.

```python
from agents.vanilla import VanillaAgent

class MemoryToolAgent(VanillaAgent):
    def __init__(self, client, system_prompt, tools, tool_handlers, runtime_context=None):
        self.memory_store = build_memory_store(runtime_context)
        memory_tool_schema = {
            "type": "function",
            "name": "retrieve_memories",
            "description": "Search past experiences for relevant procedures and outcomes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"}
                },
                "required": ["query"],
            },
        }
        all_tools = tools + [memory_tool_schema]

        def handle_memory(args):
            results = self.memory_store.retrieve(args["query"], k=5)
            return {"memories": results}

        all_handlers = {**tool_handlers, "retrieve_memories": handle_memory}
        super().__init__(client, system_prompt, all_tools, all_handlers, runtime_context=runtime_context)

    def ingest_trajectory(self, trajectory):
        self.memory_store.ingest(trajectory)
```

If `retrieve_memories` itself calls another LLM or embedding model under the hood, record that cost inside your agent or memory adapter with `self.add_response_usage(...)` or `self.add_embedding_usage(...)`.

### Recommended Store Contract

The benchmark does not require a specific memory API, but this shape fits the built-in lifecycle well:

```python
class MyMemoryStore:
    def retrieve(self, query: str, k: int = 5) -> list[str]:
        ...

    def ingest(self, trajectory) -> None:
        ...
```

In practice:

- Retrieval typically runs at the start of each turn using the latest user message or a derived query.
- Injection typically adds a temporary `role="system"` message between the prior conversation and the current user turn.
- Ingestion typically runs once per completed task and stores the conversation, tool outcomes, task metadata, and optionally pass/fail labels after rescoring.

### Demonstration: `OracleAgent`

The repo also includes `OracleAgent` in [agents/oracle.py](agents/oracle.py) as an oracle-style demonstration.

Behavior:

- It reads prior baseline trajectories for the exact same `task_id` only.
- It gives the LLM the ground-truth `task_summary`, `state_requirements`, and `task_requirements`, plus same-task baseline trajectories as evidence.
- It writes one brief per task to `outputs/<domain>/learning_opportunities/<task_id>.json`.
- If that brief already exists, it skips regeneration and immediately injects the saved brief when solving that same task again.
- There is no cross-pollination across tasks. Learning from task A is only used for task A.

Precompute missing briefs once:

```bash
uv run python scripts/precompute_oracle_briefs.py --domain travel
```

Run the oracle agent:

```bash
uv run python scripts/run_batch.py \
  --domain travel \
  --agent OracleAgent \
  --num-runs 1 \
  --agent-config configs/oracle_agent.json
```

Example config:

```json
{
  "baseline_outputs_dir": "outputs/travel",
  "learning_dir": "outputs/travel/learning_opportunities",
  "max_trajectories_per_task": 3,
  "reasoning_effort": "medium"
}
```

### Running With A Custom Agent

The custom-agent pipeline is:

1. Create `agents/my_agent.py` with a `VanillaAgent` subclass.
2. Give the class a unique name, for example `MyMemoryAgent`.
3. Run it with `--agent MyMemoryAgent`.
4. Optionally pass JSON config with `--agent-config path/to/config.json`; this is forwarded to `runtime_context.config`.
5. Save trajectories to `outputs/<domain>/run{N}/...`, then rescore or run inline scoring.

Minimal file shape:

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

At runtime, if your constructor accepts `runtime_context`, the runners pass:
- `task_id`, `user_id`, `domain`, `now`
- `output_dir`, `run_idx`
- `task_summary`, `state_requirements`, `task_requirements`
- `config` from `--agent-config`

Run one task with your agent:

```bash
uv run python scripts/run_task.py \
  --task 1-cancel_economy_domestic \
  --domain travel \
  --agent MyMemoryAgent \
  --agent-config configs/my_agent_memory.json
```

Run a full batch with your agent:

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

Without inline scoring, run these after the trajectories are written:

```bash
uv run python scripts/rescore.py --domain travel --num-runs 3 --judge-type all
uv run python scripts/compute_metrics.py --domain travel --num-runs 3 --verbose
```

## Audit Framework

The unified audit system in `scripts/audit.py` validates all domains.

**Pre-run audits** check task definitions: schema compliance, entity cross-references, solvability, expected outcome completeness, and policy math.

**Post-run audits** check trajectories: trajectory structure, termination, state-diff consistency, false pass/fail detection, and optional LLM-based trajectory review.

```bash
uv run python scripts/audit.py --domain travel --phase all --llm-review --format json
```

## Notable Implementation Details

- `state_bench/orchestrator.py` generates trajectories and efficiency metrics only.
- `scripts/rescore.py` applies task-completion and UX judges to saved trajectories.
- `scripts/compute_metrics.py` aggregates only judged outputs.
- `state_bench/env_loader.py` loads per-task environments from `task_env_path`.
- `state_bench/client.py` supports least-busy deployment pooling and sticky routing for threaded tool-calling flows that rely on `previous_response_id`.

## Task Metadata And Naming

Task JSONs include a canonical `task_type` field. Use `task_type` for semantic grouping, splits, and distribution analysis instead of parsing legacy task ID prefixes.

Existing task IDs remain stable for historical outputs and task-local environment paths. New task slugs should describe the behavior under test and avoid origin or difficulty prefixes such as `challenge_`, `adversarial_`, `hard_`, `spare_`, or `expansion_`. Prefer names like `change_international_medical_lt7d` over `challenge_medical_yyze_intl_lt7d`.

## Complete Audit

Use `scripts/audit.py` to validate tasks before a run and trajectories after a run. A complete audit has three parts: pre-run task validation, post-run trajectory validation, and optional customer-support failure attribution.

Run the pre-run audit before generating new trajectories:

```bash
uv run python scripts/audit.py --domain customer_support --phase pre
```

This checks the task set itself: file count, schema compliance, duplicate IDs, unresolved placeholders, `TASK_DONE` reachability, summary completeness, valid user IDs, entity cross-references, entity ownership, family/category coverage, information path, canonical replay sequence, policy gates, simulator information, and policy math.

Run the standard post-run audit after trajectories have been generated and scored:

```bash
uv run python scripts/audit.py --domain customer_support --phase post --num-runs 5
```

This checks saved trajectories: JSON structure, termination markers, state-diff consistency, task-summary/state-diff alignment, likely false passes, likely false failures, and any configured efficiency checks. It does not assign final root-cause labels to every failure.

Run the customer-support attribution audit when you need root-cause labels for every saved trajectory:

```bash
uv run python scripts/audit.py --domain customer_support --phase post --num-runs 5 --failure-attribution
```

This runs the standard post-run audit and then writes:

- `outputs/customer_support/harness_audit_4_24_2026.json`
- `outputs/customer_support/harness_audit_4_24_2026.md`

The attribution audit regenerates tasks in memory, validates canonical replays, recomputes state scoring, checks policy math, replays saved tool calls against fresh environments, records write-tool policy/preview diagnostics, and labels trajectories as `PASS`, `AGENT_ERROR`, `TASK_BUG`, `HARNESS_BUG`, `JUDGE_BUG`, `FALSE_PASS`, or `BLOCKED_AMBIGUOUS`.

Use `--phase all` to run pre- and post-run checks together:

```bash
uv run python scripts/audit.py --domain customer_support --phase all --num-runs 5
```

Add `--llm-review` only when deterministic post-run checks need model-assisted review of ambiguous trajectory evidence:

```bash
uv run python scripts/audit.py --domain customer_support --phase post --num-runs 5 --llm-review
```

Common options:

- `--domain`: domain to audit, such as `travel`, `customer_support`, or `shopping_assistant`.
- `--phase`: `pre`, `post`, or `all`.
- `--num-runs`: number of run directories to load for post-run audits.
- `--runs-dir`: alternate output directory for saved trajectories.
- `--single-task`: limit the audit to one task ID.
- `--format json`: emit the audit report as JSON.
- `--max-llm-tasks`: cap LLM review volume when `--llm-review` is enabled.

## License

MIT
