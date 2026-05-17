# Changelog

## v0.3 (2026-04-21)

### Infrastructure
- Moved each domain from shared run-level environments to per-task just-in-time environment loading via task-local `task_env_path` snapshots, avoiding cross-task DB collisions during generation, execution, and replay.

### Shopping assistant
- Substantially improved task challenge quality in the shopping domain, with harder and more realistic multi-step scenarios that better stress planning, constraint tracking, and policy-compliant user communication.

### Custom agent API
- Clarified and stabilized the bring-your-own-agent integration path around `VanillaAgent`, `prepare_conversation()`, and `ingest_trajectory()`, with clearer docs for generating vanilla baselines, ingesting trajectories into an external memory backend, and evaluating custom memory agents in separate output directories.

## v0.2 (2026-04-16)

### Scoring redesign
- Split single 1-5 correctness judge into two independent metrics:
  - **Metric 1 (Task Success):** Binary pass/fail via structured verification points
  - **Metric 2 (UX Quality):** 5-dimension scoring (consent, user ease, completeness, info quality, disambiguation), avg 1-5
- Added `--score-all` flag to `run_batch.py` for single-pass dual scoring
- Added `--judge-type all` to `rescore.py` for dual rescoring
- Added waste call tracking (tool errors + redundant calls) to `compute_metrics.py`

### Travel tool model
- Hotel and car workflows now separate searchable inventory from existing reservations
- Hotels: `search_hotels`, `book_hotel`, `get_hotel_reservation`, `cancel_hotel_reservation`
- Cars: `search_car_rentals`, `book_car_rental`, `get_car_rental`, `cancel_car_rental`

### Shopping assistant
- Fuzzy search matching (50% keyword threshold) for query and feature filters
- Improved `search_products` tool description for clearer usage guidance
- Fixed 6 compound task expected outcomes

### Infrastructure
- Renamed package `byom_bench` → `state_bench`
- Renamed project `Enterprise-Bench` → `STATE-Bench` (Stateful Task Agent Evaluation Benchmark)
