# Fig 4 Redesign: Task-Optimized Memory Comparison

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a visually striking `figure*` showing how the same seed program diverges into structurally opposite architectures on LoCoMo vs ALFWorld, with a cross-transfer matrix.

**Architecture:** Pure TikZ + listings in LaTeX. Four quadrants: seed (top-left), cross-transfer table (top-right), LoCoMo program (bottom-left), ALFWorld program (bottom-right). Thick diverging arrows from seed to each program. Each program panel = minimap (left strip) + 3-4 annotated code blocks (right).

**Source programs:**
- Seed: `seeds/vector_search.py` (79 lines, imports: dataclasses)
- LoCoMo best: `outputs/2026-03-15-09-03-41/programs/iter_15.py` (235 lines, imports: dataclasses, json, re, typing; uses SQL + LLM)
- ALFWorld best: `outputs/2026-03-17-19-35-14/programs/iter_16.py` (453 lines, imports: dataclasses, typing, re; uses in-memory dict + regex)

---

## Layout (figure* = full textwidth ~13.7cm)

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ┌─────────┐                      ┌──────────────────────┐  │
│   │  SEED   │                      │  Cross-Transfer      │  │
│   │ 79 lines│                      │  Matrix (3×3)        │  │
│   │ minimap │                      │                      │  │
│   └────┬────┘                      └──────────────────────┘  │
│        │                                                     │
│        │  thick arrows with labels                           │
│     ┌──┴───────┐                                             │
│     ▼          ▼                                             │
│  ┌─────────────────────┐    ┌─────────────────────────────┐  │
│  │ LoCoMo (blue)       │    │ ALFWorld (red)              │  │
│  │ ┌───┐ ┌───────────┐ │    │ ┌───┐ ┌───────────────────┐│  │
│  │ │   │ │ Block 1   │ │    │ │   │ │ Block 1           ││  │
│  │ │ m │ │ INSTRUCTION│ │    │ │ m │ │ INSTRUCTION       ││  │
│  │ │ i │ ├───────────┤ │    │ │ i │ ├───────────────────┤│  │
│  │ │ n │ │ Block 2   │ │    │ │ n │ │ Block 2           ││  │
│  │ │ i │ │ Schema    │ │    │ │ i │ │ Schema            ││  │
│  │ │ m │ ├───────────┤ │    │ │ m │ ├───────────────────┤│  │
│  │ │ a │ │ Block 3   │ │    │ │ a │ │ Block 3           ││  │
│  │ │ p │ │ Storage   │ │    │ │ p │ │ Storage           ││  │
│  │ │   │ ├───────────┤ │    │ │   │ ├───────────────────┤│  │
│  │ │   │ │ Block 4   │ │    │ │   │ │ Block 4           ││  │
│  │ │   │ │ Retrieval │ │    │ │   │ │ Retrieval         ││  │
│  │ └───┘ └───────────┘ │    │ └───┘ └───────────────────┘│  │
│  └─────────────────────┘    └─────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Component Details

### A. Seed Panel (top-left)
- Small box (~3cm wide × 2.5cm tall)
- Title: **Seed: Vanilla RAG** with gray border
- Minimap: thin vertical strip (0.4cm wide) showing tiny colored lines representing 79 lines of code
  - Blue lines = class defs, green = methods, gray = other
- Right side: key stats in small text
  - "79 lines"
  - "1 field (summary)"
  - "ChromaDB semantic search"
  - "No task-specific logic"

### B. Diverging Arrows (seed → programs)
- Two thick curved arrows from seed panel
- Left arrow (blue, LoCoMo): label "LoCoMo · 20 iterations" on the arrow path
- Right arrow (red, ALFWorld): label "ALFWorld · 20 iterations" on the arrow path
- Style: thick (1.5pt), slightly curved (bend), with arrowhead
- The arrows should feel like a "fork" or "divergence"

### C. LoCoMo Program Panel (bottom-left, blue theme)
- ~6.5cm wide × ~7cm tall
- Left strip: **Minimap** (0.5cm wide)
  - Tiny colored rectangles representing 235 lines
  - Color bands: blue = INSTRUCTION constants (lines 8-31), purple = KnowledgeItem/Query classes (34-55), orange = KnowledgeBase (58+), with darker bands for write() and read()
  - Stats below minimap: "235 lines", "json, re, sql"
  - Bracket markers on the right side of minimap pointing to which block is zoomed
- Right side: **4 annotated blocks** stacked vertically, each with:
  - A small colored header bar with block title
  - 4-6 lines of key code (using lstlisting or \texttt)
  - A brief annotation line in gray italic explaining the technique

  **Block 1 — Instruction Policy** (blue header)
  - Show INSTRUCTION_RESPONSE excerpt: "Answer only from retrieved evidence... For yes/no, output exactly Yes or No..."
  - Annotation: "Task-specific output format constraints"

  **Block 2 — Schema** (blue header)
  - Show KnowledgeItem fields: summary, topic, entities, keyphrases, facts, reliability
  - Annotation: "Multi-signal declarative record"

  **Block 3 — SQL Storage** (blue header)
  - Show: CREATE TABLE + INSERT with index_text
  - Annotation: "Precomputed searchable index for fast lexical retrieval"

  **Block 4 — LLM-Augmented Retrieval** (blue header)
  - Show: Jaccard + intent_boost scoring, then llm_completion(context)
  - Annotation: "Intent-aware ranking → LLM synthesis over top-5"

### D. ALFWorld Program Panel (bottom-right, red theme)
- Same layout as LoCoMo but red theme
- Minimap for 453 lines (much taller/denser than LoCoMo)
  - Stats: "453 lines", "re, typing"
  - Notable: No SQL, no JSON, no LLM in read

  **Block 1 — Instruction Policy** (red header)
  - Show ALWAYS_ON_KNOWLEDGE excerpt: "ALFRED rules: Parse goals into ACTION + OBJECT + STATE + DESTINATION..."
  - Annotation: "Domain-specific execution rules as always-on context"

  **Block 2 — Schema** (red header)
  - Show KnowledgeItem fields: task_summary, successful_steps, action_type, primary_object, required_state, destination
  - Annotation: "Procedural task-slot record"

  **Block 3 — Regex Slot Inference** (red header)
  - Show: regex patterns for action_type detection + normalize() function
  - Annotation: "Deterministic slot extraction via regex; no LLM needed"

  **Block 4 — Weighted Slot Matching** (red header)
  - Show: primary_obj match +4.0, mismatch -1.8, checklist generation
  - Annotation: "Typed field scoring with wrong-object penalty → deterministic checklist"

### E. Cross-Transfer Table (top-right)
- ~5.5cm wide × 2.5cm tall
- Title: **Cross-Task Transfer** (bold, small font)
- 4×4 table (1 header row + 3 data rows, 1 header col + 3 data cols):

```
              │ ALFWorld Policy │ LoCoMo Policy │ Vanilla Policy
──────────────┼─────────────────┼───────────────┼──────────────
ALFWorld Str. │     0.00        │     0.00      │    0.00
LoCoMo Str.  │     0.00        │     0.00      │    0.00
Vector Str.  │     0.00        │     0.00      │    0.00
```

- Diagonal cells (matching structure+policy) highlighted with light background
- All values 0.00 for now (placeholder)
- Subtitle in gray: "Structure = code; Policy = INSTRUCTION constants"
- This table serves Obs 2 AND Obs 3 (co-evolution necessity)

## Visual Style

- **Minimap**: Inspired by VS Code's minimap — thin vertical strip with colored horizontal bars representing code density and structure regions. Each "line" is a 0.3pt horizontal rule colored by category.
- **Code blocks**: Use lstlisting with evolvedcode style (already defined in main.tex). Tiny font (4-5pt). Background color matches theme (blue!3 or red!3).
- **Arrows**: TikZ `\draw[->, >=stealth, line width=1.5pt, bend left/right]` with text label along path using `node[midway, sloped, above]`.
- **Color scheme**: LoCoMo = blue (blue!70!black headers, blue!5 bg), ALFWorld = red (red!70!black headers, red!5 bg). Consistent with current fig4.tex.
- **Borders**: Thin gray fcolorbox around each major panel.

## Files

- **Create**: `Repos/paper/figures/fig4.tex` (overwrite current)
- **Modify**: None (results.tex already uses `\input{figures/fig4}`)
- **Verify**: `latexmk -pdf main.tex` compiles cleanly

---

## Implementation Tasks

### Task 1: Minimap Macro

- [ ] Define `\minimap` TikZ command that draws a vertical strip of colored horizontal lines
- [ ] Parameters: height, line count, color bands (list of {start_line, end_line, color})
- [ ] Each "line" = thin horizontal rule, width ~0.4cm, height per-line = total_height / line_count
- [ ] Test standalone compilation

### Task 2: Code Block Macro

- [ ] Define `\codeblock` macro: colored header bar + lstlisting snippet + gray annotation
- [ ] Parameters: title, color theme, code content, annotation text
- [ ] Use `evolvedcode` lstlisting style at 4pt font
- [ ] Test standalone

### Task 3: Seed Panel

- [ ] Draw seed panel with minimap (79 lines) + stats
- [ ] Gray theme, small size
- [ ] Title: "Seed: Vanilla RAG"

### Task 4: Program Panels

- [ ] Draw LoCoMo panel (blue): minimap + 4 code blocks
- [ ] Draw ALFWorld panel (red): minimap + 4 code blocks
- [ ] Extract actual code snippets from the evolved programs
- [ ] Write annotation text for each block

### Task 5: Diverging Arrows

- [ ] Draw two thick curved arrows from seed → each program panel
- [ ] Add text labels on arrow paths ("LoCoMo · 20 iter", "ALFWorld · 20 iter")

### Task 6: Cross-Transfer Table

- [ ] Draw the 3×3 matrix with booktabs styling
- [ ] Placeholder 0.00 values
- [ ] Title and subtitle

### Task 7: Assembly & Polish

- [ ] Combine all components in TikZ coordinate system
- [ ] Adjust spacing to fit within figure* width
- [ ] Write caption
- [ ] Compile and verify
- [ ] Open PDF and visual check
