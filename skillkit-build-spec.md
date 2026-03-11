# SkillKit — AI Agent Skills Manager

## Build Spec for Claude Code

Read this entire file before starting implementation.

---

## What Is This?

**SkillKit** is an open-source dashboard for managing AI agent skill files. It answers the questions every team building agents eventually asks: "What can our agent actually do? Where are the gaps? Which skills overlap? What should we write next?"

A **skill** is a markdown file with YAML frontmatter that tells an AI agent HOW to perform a specific domain task. This pattern was formalized by Anthropic's Agent Skills specification and is used in Claude Code's SKILL.md system. Nicolas Bustamante's work on production AI agents at Fintool demonstrated that skills — not models, not prompts — are the core competitive moat: "The model is not the product. The skills are the product."

SkillKit is the product management layer for that system.

### The Problem It Solves

At 5 skills, you can manage them by listing a directory. At 30+ skills across multiple domains, you lose track of what's covered, what overlaps, and what's missing. Teams discover gaps only when users hit them. Overlap causes the agent to pick the wrong skill for ambiguous queries. New team members don't know what skills exist or what to write next. SkillKit fixes all of this with a single visual dashboard.

### Why It Goes Viral

This tool sits at the intersection of two trends: the explosion of agent-building (everyone's writing skills) and the total absence of tooling for managing them. There are thousands of tutorials on writing agent skills and zero tools for managing a catalog of them. SkillKit fills a gap that every serious agent builder will hit.

---

## Skill File Format

SkillKit reads any markdown file with YAML frontmatter. The format is intentionally minimal — if you're already writing agent skills in markdown, SkillKit probably works with them out of the box.

### Minimal Valid Skill

```yaml
---
name: summarize_document
description: "Summarize a document with key findings, methodology, and conclusions."
---

# Summarize Document

## When to Use
User asks for a summary, overview, or key takeaways from a document.

## Steps
1. Identify the document type and purpose
2. Extract key findings or conclusions
3. Note methodology if relevant
4. Produce structured summary

## Output Format
...

## Common Pitfalls
...
```

### Full Frontmatter Schema

| Field | Required | Type | Default | Purpose |
|-------|----------|------|---------|---------|
| `name` | Yes | string | — | Unique identifier, should match filename |
| `description` | Yes | string | — | One-line summary, used for agent discovery and overlap detection |
| `output_format` | No | string | `"text"` | e.g., `structured_report`, `comparison_table`, `classification`, `summary` |
| `domain` | No | string | `"general"` | Arbitrary domain label for grouping (e.g., `finance`, `devops`, `medical`, `legal`) |
| `status` | No | string | `"active"` | `active`, `draft`, or `deprecated` — draft skills are shown in dashboard but excluded from agent discovery |
| `domain_areas` | No | list[string] | — | Optional tags for coverage map placement (rows) |
| `task_types` | No | list[string] | — | Optional tags for coverage map placement (columns) |
| `version` | No | string | — | Optional version string for tracking changes |
| `author` | No | string | — | Optional author for multi-contributor teams |
| `tags` | No | list[string] | — | Optional freeform tags for additional filtering |

SkillKit gracefully handles missing optional fields. A file with just `name` and `description` in the frontmatter works fine — you lose coverage map placement and some filtering, but catalog view, overlap detection, and gap analysis all work.

### Directory Structure

SkillKit supports a flat directory (all skills in one folder) or a three-tier override hierarchy:

```
skills/                  ← Flat mode: all skills here
```

or:

```
skills/
├── default/             ← Base skills, ship with the system
├── org/                 ← Organization-level overrides (team customizations)
└── user/                ← User-level overrides (individual preferences)
```

**Override rule:** If the same skill name exists in multiple tiers, **user > org > default**. The highest tier wins. Lower tiers are "shadowed" — visible in the dashboard but not loaded by the agent.

SkillKit auto-detects which mode you're using. If `default/`, `org/`, or `user/` subdirectories exist, it uses tiered mode. Otherwise, flat mode.

---

## The Five Features

### Feature 1: Catalog View

**What it does:** Displays every skill in the directory as a searchable, sortable, filterable table.

**Requirements:**
- Scan skills directory (flat or tiered), parse YAML frontmatter from every `.md` file
- Display per skill: name, description, domain, output_format, status, tier (if tiered mode), word count of body, last modified date, author (if present), tags (if present)
- Override indicators (tiered mode only): if a skill exists in multiple tiers, show which tier is active and which are shadowed. Example: `summarize_report` → "user (shadows: default)"
- Sort by: name, domain, word count, last modified, status
- Filter by: domain (dropdown), output_format (dropdown), status (checkboxes), tier (checkboxes), tags (multi-select), free-text search across name + description
- Click/expand a skill to view the full markdown content rendered as HTML
- Summary stats at top: total skills, count by status (active/draft/deprecated), count by domain

**UI layout:**
- Sidebar: filter controls
- Main area: table with expandable rows
- Top bar: summary stats and search

### Feature 2: Coverage Map

**What it does:** Answers "What can my agent do, and where are the holes?" Displays an interactive domain × task-type heatmap.

**The matrix:**
- **Rows = domain areas.** User-defined in a config file. Examples: for a financial agent, rows might be Equities, Fixed Income, Derivatives, Risk, Compliance. For a devops agent: CI/CD, Monitoring, Incident Response, Infrastructure, Security.
- **Columns = task types.** User-defined in a config file. Examples: Analyze, Compare, Classify, Summarize, Generate, Recommend, Monitor, Debug.
- **Cell content:** Which skill(s) cover that intersection. A skill can span multiple cells.

**Skill-to-cell mapping (two modes, user chooses):**
1. **Manual tagging:** Skills include `domain_areas` and `task_types` in frontmatter. Precise, requires author effort.
2. **Auto-inference:** Compute embedding similarity between each skill's description + "When to Use" section and the row/column labels. Less precise, zero author effort. Show a confidence indicator so users know which placements are inferred vs tagged.

**Heatmap colors:**
- Green: covered by 1+ active skills (show names on hover)
- Yellow: covered only by draft skills (incomplete)
- Red/empty: no coverage
- Gray outline: skill exists but was never loaded in the last N agent runs (dead skill, if query log available)

**Interactions:**
- Click empty cell → generate stub skill for that intersection (Feature 5)
- Click filled cell → expand to show skill(s) with links to full content
- Click yellow cell → show draft skill, prompt to complete it

**Coverage score:**
- `(green cells + yellow cells) / total cells × 100`
- Track over time in a JSON file, display as sparkline
- Show delta since last recorded score

**Config file:**

```yaml
# coverage_config.yaml
#
# Customize these to match your agent's domain.
# The defaults below are generic starting points.

domain_areas:
  - Data Analysis
  - Content Generation
  - Code & Development
  - Research
  - Communication
  - Operations

task_types:
  - Analyze
  - Compare
  - Classify
  - Summarize
  - Generate
  - Recommend
  - Monitor
  - Debug
```

**First-run experience:** If no `coverage_config.yaml` exists, SkillKit auto-generates one by extracting unique `domain` values from existing skills as rows, and using a default set of task types as columns. This means SkillKit works out of the box without any configuration — the coverage map reflects whatever skills are already present.

### Feature 3: Overlap Detection

**What it does:** Finds skills that might confuse the agent because they trigger on similar queries.

**Embedding similarity:**
- For each skill, extract `description` + the "When to Use" section from the body
- Concatenate into a single text block per skill
- Compute embeddings using `sentence-transformers` (`all-MiniLM-L6-v2` by default, configurable)
- Pairwise cosine similarity across all skills
- Flag pairs above configurable thresholds:
  - \> 0.85: **High overlap risk** — agent will struggle to choose between these
  - 0.70–0.85: **Moderate overlap risk** — may cause occasional misrouting
  - < 0.70: **Low risk** — distinct enough

**Query simulator:**
- Text input: user types a test query
- Compute query embedding, rank all skills by similarity
- Display ranked list with scores
- If top two skills are within 0.05 of each other, highlight as "ambiguous"
- This is the single most useful debugging tool for agent skill selection issues

**Overlap report:**
- Table: Skill A, Skill B, Similarity Score, Risk Level
- Sorted by score descending
- Expand each pair to see the specific text driving the similarity
- Actionable suggestions: "Consider merging," "Add differentiating trigger keywords," or "Distinct enough — no action"

**Caching:**
- Embeddings are expensive to compute. Cache them keyed by file content hash (SHA-256 of file bytes).
- Only recompute when a file changes. Store cache in `data/embedding_cache.json`.
- On a catalog of 50 skills, initial embedding takes ~10 seconds. Cached loads take < 1 second.

### Feature 4: Gap Analysis

**What it does:** Identifies what the agent CAN'T do — queries that matched no skill, and domain areas without coverage.

**Unmatched query log:**
- SkillKit reads a JSON log file that the agent writes during operation
- Expected format per entry:
  ```json
  {
    "timestamp": "2026-03-10T14:30:00",
    "query": "What caused the outage yesterday?",
    "skill_loaded": null,
    "skill_candidates": []
  }
  ```
  Entries where `skill_loaded` is null are unmatched queries.
- If the log file doesn't exist yet, SkillKit shows the gap analysis page with a setup guide explaining what format to log and where to put the file. This feature degrades gracefully — everything else works without it.

**Query clustering:**
- Group unmatched queries by embedding similarity (cluster threshold configurable, default 0.75)
- For each cluster: count, representative example query, suggested skill name + description
- Rank clusters by frequency — most common gap = highest priority

**Coverage matrix gaps:**
- List all empty cells from the coverage map
- Prioritize: gaps in rows/columns that already have other skills (extending existing coverage is higher leverage than starting a new domain from scratch)
- Show each gap as a clickable "Create stub" button

**Dead skill detection (requires query log):**
- If log has 50+ entries, identify skills that were never loaded
- Possible causes: bad description (agent doesn't recognize it), obsolete, redundant with another skill
- Suggest: improve description, deprecate, or merge

**Suggested new skills:**
- For each high-priority gap, generate a suggested name, description, and coverage tags
- Click to create stub (Feature 5)

### Feature 5: Stub Generation

**What it does:** Creates new skill files pre-populated with frontmatter and section scaffolding.

**Triggers:**
- Click empty cell in coverage map
- Click "Create stub" in gap analysis
- Manual creation via sidebar form (enter name, domain, description)

**Generated template:**

```yaml
---
name: {generated_name}
description: "TODO: {generated_description}"
output_format: text
domain: {from_context_or_user_input}
status: draft
domain_areas: [{from_coverage_map_row_if_applicable}]
task_types: [{from_coverage_map_column_if_applicable}]
---

# {Title}

## When to Use
TODO: Define when the agent should load this skill. What words or patterns
in the user's query indicate this skill is needed? Be specific.

## Steps
TODO: Define the step-by-step procedure. Number each step. This is where
you encode domain expertise — what should the agent check, in what order?

## Output Format
TODO: Define the structured output template. Use code-fenced blocks with
placeholders so the agent produces consistent, parseable output.

## Common Pitfalls
TODO: What mistakes would an LLM typically make here? What does it need to
know that isn't in its training data? This section is your competitive moat.
```

**Name generation:**
- From coverage map: `{task_type}_{domain_area}`, lowercased, spaces to underscores
- From gap analysis: use suggested name from clustering
- From manual form: user-provided

**File placement:**
- Flat mode: write to `skills/`
- Tiered mode: write to `skills/default/` (user can move to org/ or user/ manually)
- Collision check: if a file with that name already exists, warn and don't overwrite

**Draft queue:**
- Dedicated view showing only `status: draft` skills
- Columns: name, description, created date, domain_areas, task_types
- If gap analysis data available, annotate each draft with estimated query coverage (how many unmatched queries it would address)
- This is the "what to write next" prioritization list

---

## Non-Functional Requirements

### Read-Only Principle
SkillKit never modifies existing skill files. The only writes are:
- New stub files (Feature 5)
- `data/coverage_history.json` (coverage scores over time)
- `data/embedding_cache.json` (cached embeddings keyed by content hash)

Skill editing happens in the user's editor of choice. SkillKit is for visualization and management, not editing.

### Performance
- Embedding computation is the expensive operation. Cache by content hash — only recompute on change.
- Coverage map rendering: instant (frontmatter parsing only, unless using auto-inference).
- Target: < 3 second load time for 50 skills. < 10 seconds for 200 skills.
- Overlap detection with warm cache: < 1 second for 50 skills.

### Configuration

All configuration via a single `skillkit.yaml` file in the project root:

```yaml
# skillkit.yaml

# Path to skills directory (flat or tiered)
skills_dir: ./skills

# Path to coverage config (domain areas × task types)
coverage_config: ./coverage_config.yaml

# Path to agent query log (optional — gap analysis degrades gracefully without it)
query_log: ./query_log.json

# Embedding model for overlap detection
embedding_model: all-MiniLM-L6-v2

# Overlap thresholds
overlap_high: 0.85
overlap_moderate: 0.70

# Query clustering threshold for gap analysis
cluster_threshold: 0.75
```

All paths support both relative and absolute. Every field has a sensible default — SkillKit runs with zero configuration if you just point it at a skills directory.

### First-Run Experience

Critical for adoption. When a user runs `streamlit run app.py` for the first time:

1. If no `skillkit.yaml`: auto-detect `./skills/` directory. If it exists, use it. If not, create it with a single example skill.
2. If no `coverage_config.yaml`: auto-generate from existing skill domains + default task types.
3. If no query log: show gap analysis page with setup instructions instead of empty state.
4. If no skills at all: show a welcome page with quickstart guide and a "Create your first skill" button that generates a stub.

The tool should be useful within 30 seconds of `pip install` for someone who already has skill files, and within 2 minutes for someone starting from scratch.

---

## Project Structure

```
skillkit/
├── app.py                    ← Main Streamlit application (page routing + layout)
├── skill_parser.py           ← SkillRegistry: parse frontmatter, resolve overrides, flat/tiered detection
├── coverage.py               ← Coverage map logic, matrix building, auto-inference
├── overlap.py                ← Embedding similarity, caching, query simulation
├── gap_analysis.py           ← Unmatched query clustering, gap identification, dead skill detection
├── stub_generator.py         ← Blank skill file creation from templates
├── config.py                 ← Configuration loading, defaults, first-run setup
├── skillkit.yaml             ← Main config (auto-generated on first run if missing)
├── coverage_config.yaml      ← Domain areas × task types (auto-generated on first run if missing)
├── requirements.txt          ← Dependencies
├── README.md                 ← Setup, usage, screenshots, contributing guide
├── LICENSE                   ← MIT
├── .gitignore
├── CLAUDE.md                 ← Instructions for Claude Code development sessions
├── examples/
│   ├── customer_support/     ← Example skill set: customer support agent
│   │   ├── handle_refund.md
│   │   ├── escalate_ticket.md
│   │   ├── classify_inquiry.md
│   │   └── summarize_interaction.md
│   ├── devops/               ← Example skill set: devops agent
│   │   ├── diagnose_outage.md
│   │   ├── analyze_logs.md
│   │   ├── classify_alert.md
│   │   └── generate_postmortem.md
│   └── research/             ← Example skill set: research agent
│       ├── summarize_paper.md
│       ├── compare_studies.md
│       ├── extract_methodology.md
│       └── assess_evidence_quality.md
└── data/
    ├── coverage_history.json ← Coverage scores over time (auto-created)
    └── embedding_cache.json  ← Cached skill embeddings (auto-created)
```

### Example Skill Sets

Ship three example skill sets covering different domains. These serve three purposes:
1. **Immediate demo:** User can explore the dashboard with real content before writing their own skills
2. **Template:** Users copy and adapt examples for their domain
3. **Test coverage:** Ensures all features work across different skill shapes and domains

Each example set should have 4 skills with different output formats, at least one draft, and at least one pair with moderate overlap (to demonstrate overlap detection).

---

## README.md Content

```markdown
# SkillKit — Manage Your AI Agent's Skills

SkillKit is a visual dashboard for managing AI agent skill files. If you're
building agents that use markdown-based skills (the pattern used by Claude Code,
Anthropic's Agent Skills spec, and production agent systems), SkillKit helps
you see what your agent can do, find gaps, detect overlapping skills, and
scaffold new ones.

## What It Does

- **Catalog View** — Browse, search, and filter all your skills
- **Coverage Map** — Interactive heatmap showing what your agent can do and where the gaps are
- **Overlap Detection** — Find skills that might confuse your agent on similar queries
- **Gap Analysis** — Identify what your agent can't do, prioritized by user demand
- **Stub Generation** — Click a gap to create a new skill template, ready to fill in

## Quickstart

pip install skillkit
cd your-project
skillkit

That's it. SkillKit auto-detects your skills directory and generates a
default configuration. If you don't have skills yet, it creates an example
set to explore.

## Skill File Format

Any markdown file with YAML frontmatter works:

    ---
    name: summarize_document
    description: "Summarize a document with key findings and conclusions."
    domain: research
    status: active
    ---

    # Summarize Document

    ## When to Use
    ...

    ## Steps
    ...

See the examples/ directory for complete skill files across multiple domains.

## Screenshots

[Coverage map heatmap]
[Overlap detection with query simulator]
[Gap analysis with suggested skills]

## Configuration

SkillKit works with zero configuration. For customization, create a
skillkit.yaml in your project root. See docs for all options.

## Why Skills Matter

"The model is not the product. The skills are the product."
— Nicolas Bustamante, Lessons from Building AI Agents

Skills encode domain expertise as structured instructions. They give agents
consistency, accuracy, and capabilities beyond what the base model provides.
But without visibility into your skill catalog, you get gaps, overlaps, and
drift. SkillKit fixes that.

## Contributing

PRs welcome. See CONTRIBUTING.md for guidelines.

## License

MIT
```

---

## CLAUDE.md Content

```markdown
# SkillKit Development Guide

## What This Is
A Streamlit dashboard for managing AI agent skill files. Skills are markdown
files with YAML frontmatter that encode domain expertise for AI agents.

## Key Architecture Decisions
- Dashboard is READ-ONLY on existing skill files (only writes new stubs)
- Supports flat directory or three-tier hierarchy (default/ < org/ < user/)
- Overlap detection uses sentence-transformers (default: all-MiniLM-L6-v2)
- Coverage map dimensions are user-configurable via coverage_config.yaml
- Embeddings are cached by SHA-256 content hash
- All features degrade gracefully when optional data (query log, coverage config) is missing

## Tech Stack
- Streamlit for UI
- PyYAML for frontmatter parsing
- sentence-transformers for embeddings
- numpy for cosine similarity
- pandas for data tables

## Module Responsibilities
- app.py: Page routing and Streamlit layout only — no business logic
- skill_parser.py: All file I/O and frontmatter parsing
- coverage.py: Matrix building, auto-inference, coverage scoring
- overlap.py: Embedding computation, caching, similarity calculations
- gap_analysis.py: Query log processing, clustering, dead skill detection
- stub_generator.py: Template rendering and file creation
- config.py: Configuration loading with defaults, first-run setup

## File Conventions
- Skill files: markdown with YAML frontmatter (--- delimited)
- Status field: active | draft | deprecated
- All config in skillkit.yaml (auto-generated with defaults if missing)

## Testing
- Each module has a corresponding test file in tests/
- Run: pytest tests/
- Example skill sets in examples/ are used as test fixtures
- Overlap detection tests use known-similar and known-different skill pairs

## Stop and Re-Plan If
- You're about to modify an existing skill file that isn't a newly generated stub
- You're adding a dependency not in requirements.txt
- Any single page takes > 3 seconds to render with 50 skills
- You're hardcoding domain-specific content (all domain knowledge lives in skill files and config, never in code)
```

---

## Model Selection by Phase

**Design and planning phase: Claude Opus 4.6 with extended thinking, in claude.ai (chat interface).**
Architecture decisions, module decomposition, API surface design, data model design, and UX flow planning should all be done conversationally with Opus 4.6 in extended thinking mode. This is a dialogue — you're asking questions, iterating on tradeoffs, and converging on a design. That's what the chat interface is for. Extended thinking gives Opus more room to reason through tradeoffs before committing. Bring this spec into a claude.ai conversation, walk through the design of each module, and produce a detailed DESIGN.md before writing any code.

**Implementation phase: Claude Sonnet 4 via Claude Code (terminal).**
Once the design is locked and DESIGN.md is written, switch to Claude Code in the terminal for the actual coding. Sonnet is fast, capable at implementation, and cost-effective for the iterative write-test-fix cycle. The DESIGN.md from the planning phase provides the architectural guardrails. Drop it into the project directory so Claude Code reads it on every session.

**Review and polish phase: Back to Claude Opus 4.6 with extended thinking, in claude.ai.**
Before release, bring the completed codebase (or key files) back to the chat interface for Opus to review. Architecture review, edge case analysis, documentation quality, and first-run experience polish. Opus is better at spotting subtle issues in how modules interact and whether the user experience is coherent end-to-end.

---

## Implementation Order

Build in this sequence. Each step is independently testable and demoable.

1. **config.py + skill_parser.py** — Configuration loading with defaults. Skill parsing with flat/tiered auto-detection and override resolution. Test: point at examples/ directory, print correct catalog with override information.

2. **app.py + Feature 1 (Catalog)** — Streamlit app with catalog table, filters, expandable skill content. Test: shows all example skills, filters work, override indicators display correctly in tiered mode.

3. **Example skill sets** — Create the three example domains (customer support, devops, research), 4 skills each with varied formats, at least one draft and one overlapping pair per domain. Test: catalog shows all 12 skills across 3 domains.

4. **coverage_config.yaml + coverage.py** — Coverage map logic with manual tagging mode. Auto-generate config from existing skills on first run. Test: matrix renders correctly for example skills with manual tags.

5. **app.py + Feature 2 (Coverage Map)** — Heatmap page with click-to-create interaction. Coverage score calculation and history tracking. Test: renders matrix, empty cells are red, clicking one opens stub creation.

6. **overlap.py** — Embedding computation with content-hash caching. Pairwise similarity. Query simulation. Test: correctly identifies known-overlapping example skills, query simulator ranks correctly.

7. **app.py + Feature 3 (Overlap Detection)** — Overlap report page with query simulator. Test: shows flagged pairs, simulator highlights ambiguous queries.

8. **stub_generator.py + Feature 5 (Stub Generation)** — Template rendering, file creation with collision detection. Draft queue view. Test: generate stub from coverage map gap, file appears with correct frontmatter.

9. **gap_analysis.py + Feature 4 (Gap Analysis)** — Query log processing (graceful if missing), clustering, dead skill detection, suggested skills. Test: with synthetic query log, clusters unmatched queries and suggests new skills.

10. **First-run experience** — Polish the zero-config startup path. Auto-detection, auto-generation, welcome page, quickstart. Test: clone repo, run `streamlit run app.py` with no setup, see working dashboard with example skills.

11. **README.md + screenshots + packaging** — Documentation, screenshots of each feature, pip-installable package with `skillkit` CLI entry point.

---

## Packaging for Distribution

### PyPI Package

```
# setup.py or pyproject.toml
name: skillkit
entry_points:
  console_scripts:
    - skillkit = skillkit.app:main
```

`skillkit` command should launch the Streamlit app with sensible defaults (look for skills in current directory).

### GitHub Repository Structure

```
skillkit/
├── skillkit/              ← Package source
│   ├── __init__.py
│   ├── app.py
│   ├── skill_parser.py
│   ├── coverage.py
│   ├── overlap.py
│   ├── gap_analysis.py
│   ├── stub_generator.py
│   └── config.py
├── examples/              ← Example skill sets (included in package)
├── tests/                 ← Test suite
├── docs/                  ← Extended documentation
├── screenshots/           ← For README
├── README.md
├── LICENSE
├── CLAUDE.md
├── pyproject.toml
├── requirements.txt
└── .github/
    └── workflows/
        └── ci.yml         ← GitHub Actions: lint + test on PR
```

### What Makes It Spread

1. **Zero friction:** `pip install skillkit && skillkit` works immediately with example skills. No configuration required.
2. **Instant value:** The overlap detection query simulator is the single most useful debugging tool for agent skill selection. People will share it for that alone.
3. **Visual:** The coverage heatmap is inherently shareable — screenshot of your agent's capability matrix is a natural social media post.
4. **Framework agnostic:** Works with any markdown skill files — Claude Code, LangChain, CrewAI, custom systems. Doesn't lock you into any agent framework.
5. **Example domains:** Shipping with customer support, devops, and research examples means three different communities see themselves in it immediately.
6. **Non-engineers can use it:** The dashboard is visual, the stub generator scaffolds the hard parts, the gap analysis tells you what to write next. Product managers and domain experts can contribute skills without writing code.

---

## Future Roadmap

### v1.0 — Core Dashboard (This Build)
Everything described above: catalog, coverage map, overlap detection, gap analysis, stub generation. Ship as pip-installable package with example skill sets.

### v1.01 - Easy launching of a text editor
If not already included in the 1.0 build, enable a user to easily launch into their text editor and edit the skill they are working on.  Make the user's interaction between the text editor and skillkit as straightforward as posssible.

### v1.1 — Skill Quality Scoring
Automated quality checks on skill files: does it have all recommended sections (When to Use, Steps, Output Format, Common Pitfalls)? Are the TODO placeholders filled in? Is the description under 200 characters (for clean agent discovery)? Is the output format template parseable? Display a quality score per skill and a dashboard-wide average. Flag skills that need attention.

### v1.2 — Agent Integration Hooks
Standard interface for agents to write query logs that SkillKit reads. Publish a small Python library (`skillkit-agent`) with a `log_query()` function that agents call after each turn. Supports any agent framework — just import and call. Makes gap analysis work out of the box without custom logging code.

### v1.3 — Skill Versioning and Diff
Track skill changes over time using git history (if the skills directory is in a git repo). Show a changelog per skill: what changed, when, by whom. Diff view between versions. Connect to eval scores if available (Module 6 pattern): "This skill edit caused a 3% accuracy drop."

### v2.0 — SkillHub: Community Skills Repository

**The big vision.** A GitHub-based public repository of community-contributed skills, organized by domain.

**How it works:**
- `skillhub` is a public GitHub repository with a standardized directory structure:
  ```
  skillhub/
  ├── domains/
  │   ├── customer-support/
  │   │   ├── handle_refund.md
  │   │   ├── escalate_ticket.md
  │   │   └── ...
  │   ├── devops/
  │   ├── finance/
  │   ├── legal/
  │   ├── medical/
  │   ├── research/
  │   ├── sales/
  │   ├── education/
  │   └── ...
  ├── CONTRIBUTING.md          ← Skill submission guidelines + quality checklist
  ├── SKILL_TEMPLATE.md        ← Canonical skill template
  └── quality_checks.py        ← CI script that validates skill format on PR
  ```

- **Contributing a skill:** Fork the repo, add your skill file to the appropriate domain directory, open a PR. GitHub Actions runs automated quality checks (valid frontmatter, all sections present, description under 200 chars). Community reviewers check domain accuracy.

- **Installing skills from SkillHub:**
  ```bash
  # Browse available skills
  skillkit hub search "customer support"

  # Install a skill into your local skills directory
  skillkit hub install customer-support/handle_refund

  # Install an entire domain
  skillkit hub install customer-support/

  # Update installed skills to latest versions
  skillkit hub update
  ```

- **SkillKit dashboard integration:** A "Hub" tab in the dashboard that shows available community skills, filterable by domain. Click to preview, click again to install into your local `skills/default/` directory. Shows which hub skills you've already installed and whether updates are available.

- **Quality tiers in the hub:**
  - **Community:** Any valid skill that passes automated checks. No review required.
  - **Reviewed:** Manually reviewed by domain contributors for accuracy and completeness. Badge displayed in SkillKit.
  - **Featured:** Highlighted by maintainers as exemplary. Used in documentation and tutorials.

- **Why GitHub and not a custom platform:**
  - Zero infrastructure cost
  - Existing contributor workflows (fork, PR, review)
  - Version history for free
  - Issues and discussions for skill improvement feedback
  - Stars and forks as social proof
  - CI/CD via GitHub Actions for quality gates

- **Network effects:** Every skill contributed to SkillHub makes the hub more valuable. Every SkillKit user who installs from the hub is a potential contributor. The coverage map's gap analysis can suggest: "No skill exists for this gap in your catalog — but SkillHub has 3 community skills that might fit. Install one?"

### v2.1 — Skill Analytics
For teams running agents in production: track which skills are loaded most often, which produce the best user ratings, which have the highest retry rates (agent loads skill but output fails validation). Feed this back into the coverage map as usage heatmap overlay.

### v2.2 — Multi-Agent Skill Coordination
For systems running multiple specialized agents: visualize which agent owns which skills, identify cross-agent gaps (no agent handles this query type), and detect cross-agent overlap (two agents both claim they can handle the same query).

---

*Spec created: March 2026*
*Target: open-source release on GitHub + PyPI*
*Build with: Claude Code (Sonnet for implementation, Opus 4.6 extended thinking for design and review)*
