"""plot_embedding_landscape.py — Program embedding landscape data pipeline.

Collects all evolved programs from experiment runs,
embeds them with qwen/qwen3-embedding-8b via litellm/OpenRouter,
projects to 2D with t-SNE, and exports fig5_data.json for the D3 frontend.

Usage:
    uv run --with litellm --with scikit-learn python paper/figures/landscape/plot_embedding_landscape.py

Outputs:
    paper/figures/landscape/fig5_data.json
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "outputs"
FIGURES_DIR = Path(__file__).resolve().parent
CACHE_FILE = Path(__file__).resolve().parent / ".embedding_cache_normalized.json"

EMBEDDING_MODEL = "openrouter/qwen/qwen3-embedding-8b"

TSNE_RANDOM_STATE = 21

# Which experiment dirs to include and their display labels + colors
EXPERIMENT_GROUPS = {
    "t1-locomo-ours": ("LoCoMo", "#2196F3"),
    "t1-hb-data-tasks-ours": ("HB-Data", "#4CAF50"),
    "t1-hb-emergency-ours": ("HB-Emergency", "#8BC34A"),
    "t1-pr-finance-ours": ("PRB-Finance", "#FF9800"),
    "t1-pr-legal-ours": ("PRB-Legal", "#FF5722"),
    "t2-locomo-linear": ("LoCoMo-Linear", "#9467bd"),
    "t1-alfworld-seen-ours": ("ALFWorld-Seen", "#E91E63"),
    "t1-alfworld-unseen-ours": ("ALFWorld-Unseen", "#9C27B0"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# AST normalization: remove task-specific semantics, keep structure
# ---------------------------------------------------------------------------


class _Normalizer(ast.NodeTransformer):
    """Normalize an AST to remove task-specific content while preserving structure.

    - Variable / function / class / field names -> v0, v1, ...
    - String literals -> dots of same length
    - Numeric literals -> 0
    - Imports, control flow, call patterns, type annotations preserved
    """

    KEEP_NAMES = frozenset(
        {
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",
            "None",
            "True",
            "False",
            "Optional",
            "Any",
            "json",
            "re",
            "math",
            "hashlib",
            "sqlite3",
            "collections",
            "dataclasses",
            "typing",
            "datetime",
            "textwrap",
            "chromadb",
            "dataclass",
            "field",
            "self",
            "KnowledgeBase",
            "KnowledgeItem",
            "Query",
            "write",
            "read",
            "toolkit",
            "__init__",
            "__post_init__",
            "__repr__",
            "__str__",
            "default",
            "default_factory",
            "metadata",
        }
    )

    def __init__(self):
        self._name_map: dict[str, str] = {}
        self._counter = 0

    def _map_name(self, name: str) -> str:
        if name in self.KEEP_NAMES or name.startswith("__"):
            return name
        if name not in self._name_map:
            self._name_map[name] = f"v{self._counter}"
            self._counter += 1
        return self._name_map[name]

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self._map_name(node.id)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = self._map_name(node.name)
        return self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        node.name = self._map_name(node.name)
        return self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._map_name(node.arg)
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        node.attr = self._map_name(node.attr)
        return self.generic_visit(node)

    def visit_alias(self, node: ast.alias) -> ast.alias:
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, str):
            node.value = f"S{len(node.value)}"
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            node.value = 0
        return node

    def visit_keyword(self, node: ast.keyword) -> ast.keyword:
        if node.arg and node.arg not in self.KEEP_NAMES:
            node.arg = self._map_name(node.arg)
        return self.generic_visit(node)


def normalize_code(source: str) -> str:
    """Parse source, normalize AST, unparse back to code string."""
    try:
        tree = ast.parse(source)
        tree = _Normalizer().visit(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except SyntaxError:
        return source


def load_programs() -> list[dict]:
    """Load all programs from experiment dirs with metadata."""
    programs = []
    for exp_name, (label, color) in EXPERIMENT_GROUPS.items():
        prog_dir = OUTPUTS_DIR / exp_name / "programs"
        if not prog_dir.exists():
            print(f"  SKIP {exp_name}: no programs dir")
            continue

        state_file = OUTPUTS_DIR / exp_name / "state.json"
        state = json.loads(state_file.read_text()) if state_file.exists() else {}

        import re as re_mod

        exp_programs = []
        for py_file in sorted(prog_dir.glob("*.py")):
            raw_code = py_file.read_text()
            code = normalize_code(raw_code)
            name = py_file.stem
            is_seed = name.startswith("seed")
            score = 0.0
            m = re_mod.search(r"score=([\d.]+)", raw_code.split("\n")[0])
            if m:
                score = float(m.group(1))
            p = {
                "code": code,
                "name": name,
                "experiment": exp_name,
                "label": label,
                "color": color,
                "is_seed": is_seed,
                "is_best": False,
                "score": score,
                "file": str(py_file),
                "content_hash": content_hash(code),
            }
            exp_programs.append(p)

        # Mark best evolved program per experiment
        summary_file = OUTPUTS_DIR / exp_name / "summary.json"
        if summary_file.exists():
            summary = json.loads(summary_file.read_text())
            best_hash = summary.get("best_program_hash", "")
            sh = state.get("score_history", [])
            best_iter = None
            for entry in sh:
                if entry["program_hash"] == best_hash:
                    best_iter = entry["iteration"]
                    break
            if best_iter is not None:
                best_gen = summary.get("best_program_generation", -1)
                if best_gen == 0:
                    seeds_at_0 = [e for e in sh if e["parent_hash"] is None]
                    for idx, e in enumerate(seeds_at_0):
                        if e["program_hash"] == best_hash:
                            best_name = f"seed_{idx}"
                            break
                else:
                    best_name = f"iter_{best_iter}"
                for p in exp_programs:
                    if p["name"] == best_name:
                        p["is_best"] = True
                        break

        programs.extend(exp_programs)

    # Deduplicate seeds
    seen_hashes = set()
    deduped = []
    for p in programs:
        if p["is_seed"]:
            if p["content_hash"] in seen_hashes:
                continue
            seen_hashes.add(p["content_hash"])
            p["label"] = "Seed"
            p["color"] = "#757575"
        deduped.append(p)
    programs = deduped
    print(f"Loaded {len(programs)} programs ({sum(p['is_seed'] for p in programs)} unique seeds)")
    return programs


def embed_programs(programs: list[dict]) -> list[list[float]]:
    """Embed programs using litellm, with file-based caching."""
    import litellm

    cache: dict[str, list[float]] = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())
        print(f"Loaded {len(cache)} cached embeddings")

    embeddings = []
    to_embed: list[tuple[int, str, str]] = []

    for i, prog in enumerate(programs):
        ch = prog["content_hash"]
        if ch in cache:
            embeddings.append(cache[ch])
        else:
            embeddings.append(None)
            to_embed.append((i, ch, prog["code"]))

    if to_embed:
        print(f"Embedding {len(to_embed)} new programs (cached: {len(programs) - len(to_embed)})...")
        batch_size = 16
        for batch_start in range(0, len(to_embed), batch_size):
            batch = to_embed[batch_start : batch_start + batch_size]
            texts = [code for _, _, code in batch]
            print(
                f"  Batch {batch_start // batch_size + 1}/{(len(to_embed) + batch_size - 1) // batch_size} ({len(batch)} programs)..."
            )
            resp = litellm.embedding(model=EMBEDDING_MODEL, input=texts)
            for j, (idx, ch, _) in enumerate(batch):
                emb = resp.data[j]["embedding"]
                embeddings[idx] = emb
                cache[ch] = emb

        CACHE_FILE.write_text(json.dumps(cache))
        print(f"Saved {len(cache)} embeddings to cache")
    else:
        print("All embeddings cached, no API calls needed")

    return embeddings


def _build_lineage():
    """Build lineage edges and seed-to-best paths from state files."""
    edges = []

    for exp_name in EXPERIMENT_GROUPS:
        state_file = OUTPUTS_DIR / exp_name / "state.json"
        if not state_file.exists():
            continue
        state = json.loads(state_file.read_text())
        sh = state.get("score_history", [])

        hash_to_file_id: dict[str, str] = {}
        seed_counter = 0
        for entry in sh:
            ph = entry["program_hash"]
            if ph in hash_to_file_id:
                continue
            if entry["parent_hash"] is None:
                hash_to_file_id[ph] = f"seed:seed_{seed_counter}"
                seed_counter += 1
            else:
                hash_to_file_id[ph] = f"{exp_name}:iter_{entry['iteration']}"

        prog_dir = OUTPUTS_DIR / exp_name / "programs"
        seen_edges = set()
        for entry in sh:
            parent_hash = entry["parent_hash"]
            if parent_hash is None:
                continue
            child_file = f"iter_{entry['iteration']}"
            child_path = prog_dir / f"{child_file}.py"
            if not child_path.exists():
                continue
            child_id = f"{exp_name}:{child_file}"
            if parent_hash in hash_to_file_id:
                from_id = hash_to_file_id[parent_hash]
                edge_key = (from_id, child_id)
                if from_id != child_id and edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append((from_id, child_id, exp_name))

    child_to_parent: dict[str, tuple[str, str]] = {}
    for from_id, to_id, exp in edges:
        child_to_parent[to_id] = (from_id, exp)

    best_path_edges: set[tuple[str, str, str]] = set()
    for exp_name in EXPERIMENT_GROUPS:
        state_file = OUTPUTS_DIR / exp_name / "state.json"
        summary_file = OUTPUTS_DIR / exp_name / "summary.json"
        if not state_file.exists() or not summary_file.exists():
            continue
        state = json.loads(state_file.read_text())
        sh = state.get("score_history", [])
        summary = json.loads(summary_file.read_text())
        best_hash = summary.get("best_program_hash", "")
        if not best_hash:
            continue

        h2f: dict[str, str] = {}
        sc = 0
        for entry in sh:
            ph = entry["program_hash"]
            if ph in h2f:
                continue
            if entry["parent_hash"] is None:
                h2f[ph] = f"seed:seed_{sc}"
                sc += 1
            else:
                h2f[ph] = f"{exp_name}:iter_{entry['iteration']}"

        best_file_id = h2f.get(best_hash)
        if not best_file_id:
            continue
        current = best_file_id
        safety = 30
        while current and safety > 0:
            safety -= 1
            if current not in child_to_parent:
                break
            parent_id, _ = child_to_parent[current]
            best_path_edges.add((parent_id, current, exp_name))
            current = parent_id

    return edges, best_path_edges


def extract_structural_features(raw_code: str) -> dict:
    """Extract key structural features from raw (un-normalized) source code."""
    features = {}
    try:
        tree = ast.parse(raw_code)
    except SyntaxError:
        return features

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    features["uses_sqlite3"] = "sqlite3" in imports
    features["uses_chromadb"] = "chromadb" in imports or "chroma" in raw_code
    features["uses_re"] = "re" in imports
    features["uses_hashlib"] = "hashlib" in imports
    features["uses_math"] = "math" in imports

    import re as re_mod

    features["n_indexes"] = len(re_mod.findall(r"CREATE\s+INDEX", raw_code, re_mod.I))
    features["n_tables"] = len(re_mod.findall(r"CREATE\s+TABLE", raw_code, re_mod.I))

    features["n_private_funcs"] = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("_")
        and node.name not in ("__init__", "__post_init__", "__repr__", "__str__")
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Query":
            features["q_fields"] = sum(1 for n in node.body if isinstance(n, (ast.AnnAssign, ast.Assign)))
            break
    else:
        features["q_fields"] = 0

    features["n_score_ops"] = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "read":
            features["n_score_ops"] = sum(
                1 for n in ast.walk(node) if isinstance(n, (ast.BinOp, ast.AugAssign, ast.Compare))
            )
            break

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "KnowledgeItem":
            features["ki_fields"] = sum(1 for n in node.body if isinstance(n, (ast.AnnAssign, ast.Assign)))
            break
    else:
        features["ki_fields"] = 0

    features["llm_in_read"] = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "read":
            src = ast.unparse(node)
            if "llm" in src.lower() or "completion" in src.lower():
                features["llm_in_read"] = True
            break

    features["loc"] = len(raw_code.splitlines())
    features["n_functions"] = sum(
        1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )

    return features


def _compute_archetype(p: dict) -> str:
    """Classify a program into a storage architecture archetype."""
    if p["is_seed"]:
        return "Seed"
    f = p.get("features", {})
    sql = f.get("uses_sqlite3", False)
    chroma = f.get("uses_chromadb", False)
    llm = f.get("llm_in_read", False)
    if sql and chroma:
        return "SQL+Vector"
    elif sql and not chroma:
        return "SQL-only"
    elif not sql and chroma:
        return "Vector+LLM" if llm else "Vector-only"
    else:
        return "LLM-centric"


def main() -> None:
    import numpy as np
    from sklearn.manifold import TSNE

    programs = load_programs()
    if not programs:
        print("No programs found!")
        return

    for p in programs:
        raw_code = Path(p["file"]).read_text()
        p["features"] = extract_structural_features(raw_code)

    embeddings = embed_programs(programs)
    emb_array = np.array(embeddings)
    print(f"Embedding matrix shape: {emb_array.shape}")

    print(f"Running t-SNE (perp=50, exag=24, seed={TSNE_RANDOM_STATE})...")
    reducer = TSNE(
        n_components=2,
        perplexity=50,
        early_exaggeration=24,
        metric="cosine",
        random_state=TSNE_RANDOM_STATE,
        init="random",
        learning_rate="auto",
    )
    coords_2d = reducer.fit_transform(emb_array)

    # Build lineage edges
    all_edges, best_edges = _build_lineage()
    best_edge_keys = {(f, t) for f, t, _ in best_edges}
    lineage_edges = []
    for from_id, to_id, exp in all_edges:
        lineage_edges.append(
            {
                "from": from_id,
                "to": to_id,
                "experiment": exp,
                "is_best_path": (from_id, to_id) in best_edge_keys,
            }
        )

    # Export data for D3 frontend
    export_data = []
    for i, p in enumerate(programs):
        entry = {
            "id": f"{p['experiment']}:{p['name']}" if not p["is_seed"] else f"seed:{p['name']}",
            "name": p["name"],
            "experiment": p["experiment"],
            "label": p["label"],
            "color": p["color"],
            "is_seed": p["is_seed"],
            "is_best": p.get("is_best", False),
            "score": p.get("score", 0.0),
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
            "features": p.get("features", {}),
            "archetype": _compute_archetype(p),
            "file": p["file"],
        }
        export_data.append(entry)
    combined = {"programs": export_data, "edges": lineage_edges}
    export_path = FIGURES_DIR / "fig5_data.json"
    export_path.write_text(json.dumps(combined, indent=2))
    print(f"Exported: {export_path} ({len(export_data)} programs, {len(lineage_edges)} edges)")


if __name__ == "__main__":
    main()
