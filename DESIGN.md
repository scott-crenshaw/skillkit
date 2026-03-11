# SkillKit — DESIGN.md

## Purpose of This Document

This is the architectural specification for SkillKit v1.0. It translates the build spec
(`skillkit-build-spec.md`) into concrete data models, module interfaces, implementation
decisions, and resolved design tradeoffs. Claude Code should read this file before every
coding session.

**Rule: If the build spec says WHAT, this document says HOW.**

---

## Resolved Design Decisions

These were debated during the planning phase. They are now final.

### D1: Embedding Dependencies Are Optional

`pip install skillkit` installs only the core: Streamlit, PyYAML, pandas, markdown.
`pip install skillkit[analysis]` adds sentence-transformers, numpy, torch.

The core install supports: catalog view, coverage map (manual tags), stub generation,
draft queue, gap analysis (coverage matrix gaps only — no query clustering).

The analysis install adds: overlap detection, query simulator, auto-inference for coverage
map, gap analysis query clustering.

**Implementation rule:** Every import of sentence-transformers or numpy must be inside a
try/except or behind a lazy import. The app must never crash because these are missing —
it shows a clear install message on the relevant page instead.

```python
# Pattern for optional imports — use everywhere in overlap.py and gap_analysis.py
def _check_analysis_deps():
    """Returns True if analysis dependencies are available."""
    try:
        import sentence_transformers
        import numpy
        return True
    except ImportError:
        return False

ANALYSIS_AVAILABLE = _check_analysis_deps()
```

### D2: Pure Streamlit UI (No Custom JS Components)

The coverage map renders using `st.columns` and styled `st.container` widgets. Click
interactions use `st.button` inside each cell. No hover tooltips — click to see cell
details instead. This keeps the project 100% Python and maximizes contributor
accessibility.

The coverage map data model (`CoverageMatrix`) is rendering-agnostic. If a JS component
is ever needed, only the rendering function in `app.py` changes.

### D3: Auto-Inference Deferred to v1.1

v1.0 ships with manual tagging only for the coverage map. Skills without `domain_areas`
and `task_types` frontmatter simply don't appear on the map. This is clearly communicated
in the UI: "N skills are not mapped to the coverage grid. Add domain_areas and task_types
to their frontmatter to place them."

### D4: Coverage History Snapshots on Launch

Coverage score is recorded to `data/coverage_history.json` on every app launch where the
score has changed since the last entry. Maximum one entry per calendar day (if launched
multiple times, only the latest score for that day is kept).

### D5: Package Structure From Day One

All code lives inside the `skillkit/` package from the first commit. No restructuring
later. The `pyproject.toml` and entry point are created in step 1 alongside `config.py`.

### D6: Flat Mode First, Tiered Mode Second

Implement and test all features in flat directory mode. Add tiered mode (override
resolution, tier indicators, tier filters) as a clean extension after flat mode is solid.
The `SkillRegistry` interface is the same for both — tiered mode just adds `tier` and
`shadows` fields to each `Skill` object.

### D7: Gap Analysis Supports Manual Query Entry

In addition to reading from a query log file, the gap analysis page has a text area where
users can paste or type queries they know their agent can't handle. These are stored in
`data/manual_queries.json` and merged with the query log (if present) for analysis. This
makes gap analysis useful on day one without agent instrumentation.

---

## Package Structure

```
skillkit/
├── pyproject.toml
├── README.md
├── LICENSE
├── CLAUDE.md
├── DESIGN.md                      ← This file
├── skillkit-build-spec.md         ← Original spec (reference)
├── skillkit/
│   ├── __init__.py                ← Version string, package metadata
│   ├── app.py                     ← Streamlit app: page routing, layout, rendering
│   ├── config.py                  ← Config loading, defaults, first-run setup
│   ├── skill_parser.py            ← SkillRegistry: parse, resolve overrides, search
│   ├── coverage.py                ← CoverageMatrix: build, score, history
│   ├── overlap.py                 ← Embeddings, similarity, query simulation, caching
│   ├── gap_analysis.py            ← Query log processing, clustering, dead skills
│   ├── stub_generator.py          ← Stub file creation, collision detection
│   └── ui_components.py           ← Reusable Streamlit rendering helpers
├── examples/
│   ├── customer_support/
│   │   ├── handle_refund.md
│   │   ├── escalate_ticket.md
│   │   ├── classify_inquiry.md
│   │   └── summarize_interaction.md
│   ├── devops/
│   │   ├── diagnose_outage.md
│   │   ├── analyze_logs.md
│   │   ├── classify_alert.md
│   │   └── generate_postmortem.md
│   └── research/
│       ├── summarize_paper.md
│       ├── compare_studies.md
│       ├── extract_methodology.md
│       └── assess_evidence_quality.md
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_skill_parser.py
│   ├── test_coverage.py
│   ├── test_overlap.py
│   ├── test_gap_analysis.py
│   └── test_stub_generator.py
└── data/                          ← Auto-created at runtime
    ├── coverage_history.json
    ├── embedding_cache.json
    └── manual_queries.json
```

**Note:** `ui_components.py` is added beyond the spec. It holds reusable rendering
functions (stat cards, styled containers, the coverage grid renderer) to keep `app.py`
focused on page routing and layout, not widget construction.

---

## Data Models

All models are Python dataclasses. No Pydantic, no attrs — minimize dependencies.

### Skill

The core data object. Represents one parsed skill file.

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

@dataclass
class Skill:
    """A single parsed skill file."""

    # === Required (from frontmatter) ===
    name: str
    description: str

    # === Optional (from frontmatter, with defaults) ===
    output_format: str = "text"
    domain: str = "general"
    status: str = "active"              # active | draft | deprecated
    domain_areas: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    version: Optional[str] = None
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    # === Computed (from file metadata and parsing) ===
    file_path: Path = Path()            # Absolute path to the .md file
    body: str = ""                      # Markdown content below frontmatter
    word_count: int = 0                 # Word count of body
    last_modified: Optional[datetime] = None
    when_to_use: str = ""               # Extracted "When to Use" section text

    # === Tiered mode only ===
    tier: Optional[str] = None          # "default" | "org" | "user" | None (flat mode)
    is_active: bool = True              # False if shadowed by higher-tier override
    shadows: list[str] = field(default_factory=list)  # Tiers this skill shadows

    # === Derived identifier ===
    @property
    def id(self) -> str:
        """Unique identifier. In flat mode, same as name. In tiered mode,
        name is unique across tiers (only active version matters)."""
        return self.name
```

**Parsing rules:**
- `name` and `description` are required. If either is missing, log a warning and skip
  the file.
- `status` must be one of `active`, `draft`, `deprecated`. Unknown values default to
  `active` with a warning.
- `when_to_use` is extracted by finding the first `## When to Use` heading in the body
  and taking all text until the next `##` heading. If not found, empty string.
- `word_count` counts words in `body` using `len(body.split())`.
- `last_modified` comes from `os.path.getmtime()`.

### SkillRegistry

The container that holds all parsed skills and provides query methods.

```python
@dataclass
class SkillRegistry:
    """Collection of all parsed skills with query methods."""

    skills: list[Skill] = field(default_factory=list)
    mode: str = "flat"                  # "flat" | "tiered"
    skills_dir: Path = Path()

    # --- Query methods ---

    def get_active_skills(self) -> list[Skill]:
        """All skills where is_active=True. In flat mode, all skills."""
        ...

    def get_by_name(self, name: str) -> Optional[Skill]:
        """Look up active skill by name."""
        ...

    def get_by_domain(self, domain: str) -> list[Skill]:
        ...

    def get_by_status(self, status: str) -> list[Skill]:
        ...

    def get_all_domains(self) -> list[str]:
        """Unique domain values across all active skills, sorted."""
        ...

    def get_all_tags(self) -> list[str]:
        """Unique tags across all active skills, sorted."""
        ...

    def get_all_output_formats(self) -> list[str]:
        """Unique output_format values across all active skills, sorted."""
        ...

    def search(self, query: str) -> list[Skill]:
        """Free-text search across name + description. Case-insensitive substring match."""
        ...

    def filter(
        self,
        domains: Optional[list[str]] = None,
        output_formats: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        tiers: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        search_query: Optional[str] = None,
    ) -> list[Skill]:
        """Apply multiple filters. None means no filter on that dimension.
        All filters are AND-combined. Tags filter is OR within the list
        (skill matches if it has any of the specified tags)."""
        ...

    # --- Summary stats ---

    @property
    def total_count(self) -> int:
        return len(self.skills)

    @property
    def active_count(self) -> int:
        return len([s for s in self.skills if s.status == "active" and s.is_active])

    @property
    def draft_count(self) -> int:
        return len([s for s in self.skills if s.status == "draft" and s.is_active])

    @property
    def deprecated_count(self) -> int:
        return len([s for s in self.skills if s.status == "deprecated" and s.is_active])

    @property
    def domain_counts(self) -> dict[str, int]:
        """Count of active skills per domain."""
        ...
```

### CoverageMatrix

```python
from enum import Enum

class CellState(Enum):
    COVERED = "covered"         # 1+ active skills
    DRAFT_ONLY = "draft_only"   # Only draft skills
    EMPTY = "empty"             # No skills

@dataclass
class CoverageCell:
    """One cell in the coverage matrix."""
    domain_area: str
    task_type: str
    skills: list[Skill]                  # Skills mapped to this cell
    state: CellState
    # Future: confidence field for auto-inference

@dataclass
class CoverageMatrix:
    """The full domain_area × task_type grid."""
    rows: list[str]                      # domain_areas (from config)
    columns: list[str]                   # task_types (from config)
    cells: dict[tuple[str, str], CoverageCell]
    unmapped_skills: list[Skill]         # Skills without domain_areas/task_types tags

    @property
    def coverage_score(self) -> float:
        """(covered + draft_only) / total cells × 100"""
        total = len(self.rows) * len(self.columns)
        if total == 0:
            return 0.0
        filled = sum(
            1 for cell in self.cells.values()
            if cell.state in (CellState.COVERED, CellState.DRAFT_ONLY)
        )
        return (filled / total) * 100

    @property
    def empty_cells(self) -> list[CoverageCell]:
        """All cells with no skills — candidates for stub generation."""
        return [c for c in self.cells.values() if c.state == CellState.EMPTY]

    def get_cell(self, domain_area: str, task_type: str) -> Optional[CoverageCell]:
        return self.cells.get((domain_area, task_type))
```

**Matrix building algorithm:**
1. Load `rows` and `columns` from `coverage_config.yaml`
2. Initialize all cells as EMPTY
3. For each active skill with `domain_areas` and `task_types` set:
   - For each (domain_area, task_type) combination from the skill's tags:
     - If both values exist in the config's rows/columns, add the skill to that cell
4. Set cell state: COVERED if any skill is active, DRAFT_ONLY if all skills are draft, EMPTY otherwise
5. Collect skills that have no `domain_areas` or `task_types` into `unmapped_skills`

### CoverageHistory

```python
@dataclass
class CoverageHistoryEntry:
    date: str                            # YYYY-MM-DD
    score: float
    total_cells: int
    covered_cells: int
    draft_cells: int
    empty_cells: int
    total_skills: int

@dataclass
class CoverageHistory:
    entries: list[CoverageHistoryEntry] = field(default_factory=list)

    def record(self, matrix: CoverageMatrix, total_skills: int) -> bool:
        """Record current score. Returns True if recorded (score changed or new day).
        Replaces entry if same day. Does nothing if score unchanged from latest."""
        ...

    def latest_score(self) -> Optional[float]:
        ...

    def delta_since_last(self, current: float) -> Optional[float]:
        """Difference between current score and the previous entry."""
        ...
```

**Storage:** `data/coverage_history.json` — list of `CoverageHistoryEntry` dicts.

### OverlapResult

```python
@dataclass
class OverlapPair:
    """A pair of skills with measured similarity."""
    skill_a: Skill
    skill_b: Skill
    similarity: float
    risk_level: str                      # "high" | "moderate" | "low"
    text_a: str                          # The text that was compared (description + when_to_use)
    text_b: str

@dataclass
class OverlapReport:
    """All pairwise overlaps above the moderate threshold."""
    pairs: list[OverlapPair]             # Sorted by similarity descending
    high_threshold: float
    moderate_threshold: float

    @property
    def high_risk_pairs(self) -> list[OverlapPair]:
        return [p for p in self.pairs if p.risk_level == "high"]

    @property
    def moderate_risk_pairs(self) -> list[OverlapPair]:
        return [p for p in self.pairs if p.risk_level == "moderate"]
```

### QuerySimulationResult

```python
@dataclass
class ScoredSkill:
    """A skill with a similarity score to a query."""
    skill: Skill
    score: float

@dataclass
class QuerySimulationResult:
    """Result of simulating a query against all skills."""
    query: str
    ranked_skills: list[ScoredSkill]     # Sorted by score descending
    is_ambiguous: bool                   # True if top two are within 0.05
```

### EmbeddingCache

```python
@dataclass
class EmbeddingCacheEntry:
    content_hash: str                    # SHA-256 of the text that was embedded
    embedding: list[float]               # The embedding vector
    skill_name: str                      # For debugging/display

@dataclass
class EmbeddingCache:
    entries: dict[str, EmbeddingCacheEntry]   # Keyed by content_hash
    model_name: str                           # If model changes, cache is invalidated

    def get(self, content_hash: str) -> Optional[list[float]]:
        entry = self.entries.get(content_hash)
        return entry.embedding if entry else None

    def put(self, content_hash: str, embedding: list[float], skill_name: str) -> None:
        ...

    def needs_recompute(self, content_hash: str) -> bool:
        return content_hash not in self.entries
```

**Storage:** `data/embedding_cache.json`. On load, if the stored `model_name` differs from
the configured model, the entire cache is invalidated.

### GapAnalysis Models

```python
@dataclass
class QueryLogEntry:
    """One entry from the agent's query log."""
    timestamp: str
    query: str
    skill_loaded: Optional[str]
    skill_candidates: list[str]

@dataclass
class QueryCluster:
    """A group of similar unmatched queries."""
    representative_query: str            # Most central query in the cluster
    queries: list[str]
    count: int
    suggested_skill_name: str
    suggested_description: str
    suggested_domain_areas: list[str]
    suggested_task_types: list[str]

@dataclass
class DeadSkill:
    """A skill that was never loaded despite sufficient query volume."""
    skill: Skill
    suggestion: str                      # "improve description" | "deprecate" | "merge with X"

@dataclass
class GapReport:
    """Complete gap analysis output."""
    unmatched_query_count: int
    total_query_count: int
    clusters: list[QueryCluster]         # Sorted by count descending
    coverage_gaps: list[CoverageCell]    # Empty cells from coverage map
    dead_skills: list[DeadSkill]
    has_query_log: bool                  # False = only coverage gaps available
    has_manual_queries: bool
```

---

## Module Interfaces

### config.py

```python
@dataclass
class SkillKitConfig:
    skills_dir: Path
    coverage_config_path: Path
    query_log_path: Optional[Path]
    data_dir: Path
    embedding_model: str
    overlap_high: float
    overlap_moderate: float
    cluster_threshold: float

def load_config(config_path: Optional[Path] = None) -> SkillKitConfig:
    """Load from skillkit.yaml, or create with defaults.

    Search order:
    1. Explicit path if provided
    2. ./skillkit.yaml
    3. Generate defaults (skills_dir=./skills, etc.)

    Side effects on first run:
    - Creates skillkit.yaml with defaults if not found
    - Creates skills/ directory if not found
    - Copies example skills into skills/ if directory is empty
    - Creates data/ directory if not found
    """
    ...

def load_coverage_config(path: Path, registry: SkillRegistry) -> tuple[list[str], list[str]]:
    """Load domain_areas and task_types from coverage_config.yaml.

    If file doesn't exist, auto-generate:
    - domain_areas = unique domain values from registry skills
    - task_types = default set: [Analyze, Compare, Classify, Summarize,
                                  Generate, Recommend, Monitor, Debug]
    Write generated config to path.

    Returns (domain_areas, task_types).
    """
    ...

def ensure_data_dir(config: SkillKitConfig) -> None:
    """Create data/ directory and empty JSON files if they don't exist."""
    ...
```

### skill_parser.py

```python
def parse_skill_file(path: Path) -> Optional[Skill]:
    """Parse a single .md file into a Skill. Returns None if file is invalid
    (missing required fields, malformed frontmatter). Logs warnings for issues.

    Parsing steps:
    1. Read file content
    2. Split on '---' delimiters to extract YAML frontmatter
    3. Parse YAML with PyYAML (yaml.safe_load)
    4. Validate required fields (name, description)
    5. Extract body (everything after second '---')
    6. Extract 'When to Use' section from body
    7. Compute word count
    8. Get last_modified from filesystem
    9. Build Skill object with defaults for missing optional fields
    """
    ...

def load_registry(config: SkillKitConfig) -> SkillRegistry:
    """Scan skills_dir, parse all .md files, resolve overrides.

    Steps:
    1. Detect mode: if skills_dir has default/, org/, or user/ subdirs → tiered; else → flat
    2. Scan for all .md files (recursive in flat mode, per-tier in tiered mode)
    3. Parse each file into a Skill
    4. In tiered mode: set tier field, resolve overrides (user > org > default),
       mark shadowed skills with is_active=False and populate shadows field
    5. Return SkillRegistry
    """
    ...

def _detect_mode(skills_dir: Path) -> str:
    """Returns 'flat' or 'tiered'."""
    tier_dirs = {"default", "org", "user"}
    subdirs = {d.name for d in skills_dir.iterdir() if d.is_dir()}
    return "tiered" if subdirs & tier_dirs else "flat"

def _resolve_overrides(skills: list[Skill]) -> list[Skill]:
    """For tiered mode: group by name, mark lower-tier duplicates as shadowed.
    Priority: user > org > default."""
    ...

def _extract_when_to_use(body: str) -> str:
    """Extract text from '## When to Use' section. Returns empty string if not found."""
    ...
```

### coverage.py

```python
def build_coverage_matrix(
    registry: SkillRegistry,
    domain_areas: list[str],
    task_types: list[str],
) -> CoverageMatrix:
    """Build the coverage grid from active skills with manual tags.

    Only skills with both domain_areas and task_types frontmatter are placed.
    Skills missing either field go into unmapped_skills.
    """
    ...

def load_coverage_history(data_dir: Path) -> CoverageHistory:
    """Load from data/coverage_history.json. Returns empty history if file missing."""
    ...

def save_coverage_history(history: CoverageHistory, data_dir: Path) -> None:
    """Write to data/coverage_history.json."""
    ...

def record_coverage_snapshot(
    matrix: CoverageMatrix,
    registry: SkillRegistry,
    data_dir: Path,
) -> Optional[float]:
    """Record current coverage score if changed. Returns delta or None."""
    ...
```

### overlap.py

```python
def check_analysis_available() -> bool:
    """Returns True if sentence-transformers and numpy are importable."""
    ...

def compute_embeddings(
    skills: list[Skill],
    model_name: str,
    cache: EmbeddingCache,
) -> dict[str, list[float]]:
    """Compute or retrieve cached embeddings for each skill.

    Text per skill = description + " " + when_to_use
    Key = SHA-256 of that text.

    Returns dict mapping skill.name → embedding vector.
    Raises ImportError if analysis deps not available.
    """
    ...

def compute_pairwise_similarity(
    embeddings: dict[str, list[float]],
) -> list[tuple[str, str, float]]:
    """Cosine similarity for all skill pairs.
    Returns list of (name_a, name_b, similarity) sorted by similarity desc.
    """
    ...

def build_overlap_report(
    registry: SkillRegistry,
    config: SkillKitConfig,
) -> OverlapReport:
    """Full overlap analysis pipeline.

    Steps:
    1. Load or initialize embedding cache
    2. Compute embeddings for all active skills
    3. Pairwise cosine similarity
    4. Filter to pairs above moderate threshold
    5. Classify risk levels
    6. Save updated cache
    7. Return OverlapReport
    """
    ...

def simulate_query(
    query: str,
    registry: SkillRegistry,
    config: SkillKitConfig,
) -> QuerySimulationResult:
    """Embed the query, rank all active skills by similarity.

    Does NOT use the cache for the query itself (queries aren't persisted).
    Does use the cache for skill embeddings.
    """
    ...

def load_embedding_cache(data_dir: Path, model_name: str) -> EmbeddingCache:
    """Load cache from data/embedding_cache.json. Returns empty cache if
    file missing or model_name doesn't match stored model."""
    ...

def save_embedding_cache(cache: EmbeddingCache, data_dir: Path) -> None:
    ...
```

### gap_analysis.py

```python
def load_query_log(path: Optional[Path]) -> Optional[list[QueryLogEntry]]:
    """Load and parse query log. Returns None if path is None or file missing."""
    ...

def load_manual_queries(data_dir: Path) -> list[str]:
    """Load from data/manual_queries.json. Returns empty list if missing."""
    ...

def save_manual_queries(queries: list[str], data_dir: Path) -> None:
    ...

def get_unmatched_queries(
    log: Optional[list[QueryLogEntry]],
    manual_queries: list[str],
) -> list[str]:
    """Extract unmatched queries from log + all manual queries."""
    ...

def cluster_queries(
    queries: list[str],
    threshold: float,
    model_name: str,
) -> list[QueryCluster]:
    """Group similar queries by embedding similarity.

    Algorithm:
    1. Embed all queries
    2. Agglomerative clustering with cosine distance, threshold
    3. For each cluster: pick most central query as representative
    4. Generate suggested skill name and description from cluster content
    5. Sort by cluster size descending

    Requires analysis deps. Returns empty list if not available.
    """
    ...

def detect_dead_skills(
    registry: SkillRegistry,
    log: list[QueryLogEntry],
    min_log_size: int = 50,
) -> list[DeadSkill]:
    """Find active skills never loaded in the query log.

    Only runs if log has >= min_log_size entries.
    """
    ...

def build_gap_report(
    registry: SkillRegistry,
    matrix: CoverageMatrix,
    config: SkillKitConfig,
) -> GapReport:
    """Full gap analysis pipeline."""
    ...
```

### stub_generator.py

```python
def generate_stub(
    name: str,
    description: str = "",
    domain: str = "general",
    domain_areas: Optional[list[str]] = None,
    task_types: Optional[list[str]] = None,
) -> str:
    """Generate the full markdown content for a new skill stub.
    Returns the file content as a string (does not write to disk)."""
    ...

def write_stub(
    content: str,
    name: str,
    skills_dir: Path,
    mode: str,
) -> Path:
    """Write stub to disk with collision detection.

    - Flat mode: writes to skills_dir/{name}.md
    - Tiered mode: writes to skills_dir/default/{name}.md

    Raises FileExistsError if file already exists.
    Returns the path of the created file.
    """
    ...

def generate_name_from_coverage(task_type: str, domain_area: str) -> str:
    """Generate skill name from coverage map coordinates.
    Example: ('Analyze', 'Data Analysis') → 'analyze_data_analysis'
    """
    return f"{task_type}_{domain_area}".lower().replace(" ", "_").replace("&", "and")
```

### ui_components.py

```python
def render_stat_cards(registry: SkillRegistry) -> None:
    """Render the top-bar summary stats: total, active, draft, deprecated counts."""
    ...

def render_skill_table(
    skills: list[Skill],
    show_tier: bool = False,
) -> None:
    """Render the filterable, sortable skill table with expandable rows.
    show_tier controls whether the tier column and shadow indicators appear."""
    ...

def render_coverage_grid(matrix: CoverageMatrix) -> Optional[tuple[str, str]]:
    """Render the coverage heatmap as a grid of styled containers.

    Returns (domain_area, task_type) if user clicked a cell, None otherwise.
    Uses st.session_state to track selected cell.

    Color scheme:
    - COVERED: #2ecc71 (green) with skill count badge
    - DRAFT_ONLY: #f39c12 (amber) with 'draft' indicator
    - EMPTY: #e74c3c (red/coral)
    """
    ...

def render_coverage_score(
    score: float,
    delta: Optional[float],
    history: CoverageHistory,
) -> None:
    """Render coverage score with delta indicator and mini sparkline.
    Sparkline uses st.line_chart with history entries."""
    ...

def render_overlap_table(report: OverlapReport) -> None:
    """Render the overlap pairs table with risk level coloring
    and expandable detail showing the compared text."""
    ...

def render_query_simulator(config: SkillKitConfig, registry: SkillRegistry) -> None:
    """Text input + ranked results list. Highlights ambiguous top results.
    This is rendered ABOVE the overlap table — it's the primary tool."""
    ...

def render_gap_clusters(clusters: list[QueryCluster]) -> Optional[str]:
    """Render query clusters with 'Create stub' buttons.
    Returns the cluster's suggested_skill_name if user clicked create."""
    ...

def render_draft_queue(registry: SkillRegistry) -> None:
    """Table of draft skills: name, description, domain_areas, task_types, created date."""
    ...

def render_analysis_unavailable_message() -> None:
    """Show friendly message when analysis deps are missing.
    Includes the pip install command to add them."""
    ...

def render_welcome_page(config: SkillKitConfig) -> None:
    """Shown when no skills exist. Quickstart guide + create first skill button."""
    ...
```

### app.py

```python
"""
SkillKit — AI Agent Skills Manager

Main Streamlit application. Page routing and layout only.
Business logic lives in other modules.
"""

def main():
    """Entry point for both `streamlit run` and the `skillkit` CLI command.

    Page structure:
    1. Load config (with first-run setup side effects)
    2. Load skill registry
    3. Sidebar navigation: Catalog | Coverage Map | Overlap Detection |
                           Gap Analysis | Draft Queue | Settings
    4. Route to selected page
    5. Each page calls module functions + ui_components renderers

    Sidebar also contains:
    - Skills directory path display (+ change button that updates skillkit.yaml)
    - "Create New Skill" button (always visible, opens stub form)
    - Quick stats: total skills, coverage score
    """
    ...

# Page functions (each is a self-contained Streamlit page)

def page_catalog(registry, config):
    """Feature 1: Catalog view with filters, search, expandable skills."""
    ...

def page_coverage(registry, config):
    """Feature 2: Coverage map grid, score, cell interactions."""
    ...

def page_overlap(registry, config):
    """Feature 3: Query simulator (top), overlap report (below).
    Shows analysis_unavailable_message if deps missing."""
    ...

def page_gap_analysis(registry, config):
    """Feature 4: Coverage gaps (always), query clusters + dead skills
    (if analysis deps + query log available), manual query entry."""
    ...

def page_draft_queue(registry, config):
    """Feature 5 companion: Draft skills prioritized by gap coverage."""
    ...

def page_settings(config):
    """View/edit skillkit.yaml, coverage_config.yaml.
    Skills directory path with change option.
    Embedding cache stats and clear button."""
    ...
```

---

## App Navigation and Page Layout

### Sidebar (persistent across all pages)

```
┌──────────────────────┐
│  🔧 SkillKit         │
│                      │
│  Skills: ./skills    │
│  [Change]            │
│                      │
│  ── Navigation ──    │
│  📋 Catalog          │
│  🗺️ Coverage Map     │
│  🔍 Overlap Detection│
│  📊 Gap Analysis     │
│  📝 Draft Queue      │
│  ⚙️  Settings        │
│                      │
│  ── Quick Stats ──   │
│  12 skills           │
│  Coverage: 67%       │
│                      │
│  [+ New Skill]       │
└──────────────────────┘
```

### Catalog Page Layout

```
┌────────────────────────────────────────────────┐
│  Active: 9  │  Draft: 2  │  Deprecated: 1     │
├────────────────────────────────────────────────┤
│  🔍 Search skills...                           │
│                                                │
│  Filters:                                      │
│  Domain: [All ▾]  Format: [All ▾]             │
│  Status: ☑ Active ☑ Draft ☐ Deprecated        │
│  Tags: [multi-select]                          │
├────────────────────────────────────────────────┤
│  Name         │ Domain │ Format │ Status │ ... │
│  ─────────────┼────────┼────────┼────────┼──── │
│  ▶ handle_... │ cs     │ text   │ active │     │
│  ▶ classify.. │ cs     │ class  │ active │     │
│  ▶ diagnose.. │ devops │ report │ draft  │     │
│  ...                                           │
└────────────────────────────────────────────────┘

Expanded row:
┌────────────────────────────────────────────────┐
│  ▼ handle_refund                               │
│  Domain: customer_support  Format: text        │
│  Tags: refund, billing     Author: jsmith      │
│  Words: 342   Modified: 2026-03-01             │
│  [Open in editor]                              │
│  ┌──────────────────────────────────────────┐  │
│  │  # Handle Refund                        │  │
│  │                                          │  │
│  │  ## When to Use                          │  │
│  │  Customer requests a refund or return... │  │
│  │  ...                                     │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

### Coverage Map Page Layout

```
┌────────────────────────────────────────────────┐
│  Coverage Score: 67%  ▲+8% since last          │
│  [sparkline chart]                             │
│  N skills not mapped (missing tags)            │
├────────────────────────────────────────────────┤
│           │Analyze│Compare│Classify│Summarize│…│
│  ─────────┼───────┼───────┼────────┼─────────┤ │
│  CS       │ ██ 2  │ ░░    │  ██ 1  │  ▒▒ 1  │ │
│  DevOps   │ ██ 1  │ ░░    │  ██ 1  │  ░░    │ │
│  Research │ ██ 1  │ ██ 1  │  ░░    │  ██ 1  │ │
│  ...      │       │       │        │         │ │
├────────────────────────────────────────────────┤
│  ██ = covered (green)                          │
│  ▒▒ = draft only (amber)                      │
│  ░░ = empty (click to create stub)             │
├────────────────────────────────────────────────┤
│  Selected: DevOps × Compare (empty)            │
│  [Create stub skill for this gap]              │
│  OR                                            │
│  Selected: CS × Analyze (2 skills)             │
│  • handle_refund — Handle customer refunds...  │
│  • classify_inquiry — Classify incoming...     │
└────────────────────────────────────────────────┘
```

### Overlap Detection Page Layout

```
┌────────────────────────────────────────────────┐
│  ── Query Simulator ──                         │
│  [Type a test query to see which skills match] │
│                                                │
│  Results:                                      │
│  1. handle_refund (0.87) ████████░░            │
│  2. escalate_ticket (0.84) ███████░░░          │
│  ⚠️ Ambiguous! Top two within 0.05             │
│  3. classify_inquiry (0.61) ██████░░░░         │
├────────────────────────────────────────────────┤
│  ── Overlap Report ──                          │
│  High risk: 1 pair  │  Moderate: 3 pairs       │
│                                                │
│  ▶ handle_refund ↔ escalate_ticket  0.86 🔴   │
│  ▶ diagnose_outage ↔ analyze_logs   0.78 🟡   │
│  ▶ summarize_paper ↔ extract_meth.  0.73 🟡   │
│  ...                                           │
└────────────────────────────────────────────────┘
```

---

## Editor Integration (v1.0)

The spec mentions v1.01 for editor launching. Include a basic version in v1.0:

When a skill is expanded in the catalog view, show an "Open in editor" button. This
calls `subprocess.Popen` with the user's default editor:

```python
import subprocess, os, sys

def open_in_editor(file_path: Path) -> None:
    """Open a skill file in the user's preferred editor.

    Tries in order:
    1. $EDITOR environment variable
    2. $VISUAL environment variable
    3. Platform default: 'code' (VS Code) on all platforms, then
       'open' (macOS), 'xdg-open' (Linux), 'start' (Windows)
    """
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        subprocess.Popen([editor, str(file_path)])
        return

    # Try VS Code first (most common for this audience)
    try:
        subprocess.Popen(["code", str(file_path)])
        return
    except FileNotFoundError:
        pass

    # Platform defaults
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(file_path)])
    elif sys.platform == "linux":
        subprocess.Popen(["xdg-open", str(file_path)])
    elif sys.platform == "win32":
        os.startfile(str(file_path))
```

---

## Example Skill Design

Each domain has 4 skills designed to demonstrate specific features.

### Customer Support Domain

| Skill | Status | Overlap Role | Coverage Tags |
|-------|--------|-------------|---------------|
| handle_refund | active | Overlaps with escalate_ticket (both trigger on "refund" queries — demonstrates genuine redundancy) | domain_areas: [Customer Service], task_types: [Analyze, Recommend] |
| escalate_ticket | active | Overlaps with handle_refund | domain_areas: [Customer Service], task_types: [Classify, Recommend] |
| classify_inquiry | active | Distinct | domain_areas: [Customer Service], task_types: [Classify] |
| summarize_interaction | draft | N/A | domain_areas: [Customer Service], task_types: [Summarize] |

**Overlap story:** handle_refund and escalate_ticket both mention refund scenarios in
their "When to Use" sections, but handle_refund is for straightforward refunds while
escalate_ticket is for cases requiring manager approval. Their descriptions are similar
enough to trigger moderate-to-high overlap (~0.80-0.88), demonstrating a real-world
problem: the agent might pick the wrong one for borderline cases. The fix is to add
clearer differentiating keywords.

### DevOps Domain

| Skill | Status | Overlap Role | Coverage Tags |
|-------|--------|-------------|---------------|
| diagnose_outage | active | Overlaps with analyze_logs (similar trigger: "what happened?") | domain_areas: [Incident Response], task_types: [Analyze, Debug] |
| analyze_logs | active | Overlaps with diagnose_outage | domain_areas: [Monitoring], task_types: [Analyze] |
| classify_alert | active | Distinct | domain_areas: [Monitoring], task_types: [Classify] |
| generate_postmortem | deprecated | N/A | domain_areas: [Incident Response], task_types: [Generate, Summarize] |

**Overlap story:** diagnose_outage and analyze_logs overlap because both trigger on
"production issue" queries. But diagnose_outage is a full incident response workflow while
analyze_logs is focused on log search and pattern extraction. This demonstrates the
"similar but distinct" pattern — they need better trigger keywords, not merging.

### Research Domain

| Skill | Status | Overlap Role | Coverage Tags |
|-------|--------|-------------|---------------|
| summarize_paper | active | Low overlap | domain_areas: [Research], task_types: [Summarize] |
| compare_studies | active | Low overlap | domain_areas: [Research], task_types: [Compare, Analyze] |
| extract_methodology | active | Sneaky overlap with summarize_paper (both read papers, different purpose) | domain_areas: [Research], task_types: [Analyze] |
| assess_evidence_quality | draft | N/A | domain_areas: [Research], task_types: [Classify, Analyze] |

**Overlap story:** summarize_paper and extract_methodology look different in their names
but have moderate overlap (~0.72-0.78) because they both operate on academic papers. This
demonstrates the "sneaky overlap" pattern — skills that seem distinct but trigger on
similar queries because they share input context.

---

## Configuration Defaults

### skillkit.yaml (auto-generated)

```yaml
skills_dir: ./skills
coverage_config: ./coverage_config.yaml
query_log: null
embedding_model: all-MiniLM-L6-v2
overlap_high: 0.85
overlap_moderate: 0.70
cluster_threshold: 0.75
```

### coverage_config.yaml (auto-generated from example skills)

When generated from the three example domains:

```yaml
domain_areas:
  - Customer Service
  - Incident Response
  - Monitoring
  - Research

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

---

## Implementation Order (Revised from Spec)

Build in this sequence. Changes from the original spec are marked.

### Step 1: Packaging + config.py + skill_parser.py

**Changed:** Packaging (pyproject.toml, `skillkit` entry point, package structure) is
created here, not step 11. All code goes inside `skillkit/` from the start.

Deliverables:
- `pyproject.toml` with `[project.scripts] skillkit = "skillkit.app:main"`
- `skillkit/__init__.py` with version
- `skillkit/config.py` — SkillKitConfig, load_config, load_coverage_config
- `skillkit/skill_parser.py` — parse_skill_file, load_registry, override resolution
- `tests/test_config.py` and `tests/test_skill_parser.py`

Test: `python -c "from skillkit.skill_parser import load_registry; ..."` works and
correctly parses example skills with override detection.

### Step 2: Example skill sets

**Changed:** Moved before app.py so the demo content exists when we start building the UI.

Deliverables:
- 12 skill files across 3 domains (see Example Skill Design above)
- Each skill has complete content (not just frontmatter stubs)
- Overlapping pairs have carefully written "When to Use" sections that create measurable
  similarity
- At least 200-400 words per skill body for realistic word counts

Test: Parser correctly loads all 12, identifies tiers/domains/statuses.

### Step 3: app.py + ui_components.py + Feature 1 (Catalog)

Deliverables:
- `skillkit/app.py` — page routing, sidebar, main entry point
- `skillkit/ui_components.py` — stat cards, skill table, expandable rows
- Full catalog page with all filters, sort, search, expanded skill view
- "Open in editor" button on expanded skills
- Settings page with skills directory path + change option

Test: `skillkit` command launches dashboard showing all 12 example skills with working
filters.

### Step 4: coverage.py + Feature 2 (Coverage Map)

Deliverables:
- `skillkit/coverage.py` — build_coverage_matrix, CoverageHistory, scoring
- Coverage map page with grid, score, delta, sparkline
- Cell click → detail view (skills in cell or "empty" with create button)
- Unmapped skills count and list
- coverage_config.yaml auto-generation

Test: Grid renders correctly for example skills. Empty cells are clickable. Score
calculates correctly.

### Step 5: stub_generator.py + Feature 5 (Stub Generation)

**Changed:** Moved before overlap detection. Stub generation is needed by the coverage
map (click empty cell → create stub) and should work before the analysis features.

Deliverables:
- `skillkit/stub_generator.py` — generate_stub, write_stub, name generation
- Integration with coverage map (click empty cell → pre-filled stub form)
- Sidebar "New Skill" button → manual stub form
- Collision detection and warnings
- Draft queue page (basic version — just lists draft skills)

Test: Create stub from coverage map gap. File appears in correct location with correct
frontmatter. Collision detection prevents overwrite.

### Step 6: overlap.py + Feature 3 (Overlap Detection)

Deliverables:
- `skillkit/overlap.py` — embeddings, caching, similarity, query simulator
- Overlap page with query simulator (top) and overlap report (below)
- Graceful fallback when analysis deps not installed
- Embedding cache working correctly (warm cache < 1s for 12 skills)
- `tests/test_overlap.py` with known-similar and known-different pairs

Test: Query simulator ranks skills correctly. Known overlapping pairs are flagged.
Cache hit/miss works. Missing deps show install message, not crash.

### Step 7: gap_analysis.py + Feature 4 (Gap Analysis)

Deliverables:
- `skillkit/gap_analysis.py` — query log parsing, clustering, dead skills
- Gap analysis page with coverage gaps (always), query clusters (if available)
- Manual query entry with persistence to `data/manual_queries.json`
- "Create stub" buttons on clusters and gaps
- Dead skill detection (if query log large enough)
- Setup guide when no query log exists

Test: Coverage gaps display correctly from matrix. Manual queries persist across sessions.
With synthetic query log, clusters form and suggest skills.

### Step 8: First-run experience polish

Deliverables:
- Welcome page when no skills exist
- Auto-detection of skills directory
- Auto-generation of all config files
- Example skills copy when skills dir is empty
- Smooth transition from "exploring examples" to "using my own skills"
- Test the full zero-config path: fresh directory → `skillkit` → working dashboard

### Step 9: README.md + final packaging

Deliverables:
- README with quickstart, screenshots, configuration docs
- `requirements.txt` (core) and optional deps documented
- LICENSE (MIT)
- CLAUDE.md for development sessions
- Verify `pip install .` and `pip install .[analysis]` both work
- Verify `skillkit` CLI entry point works

---

## Dependencies

### Core (required)

```
streamlit>=1.28.0
PyYAML>=6.0
pandas>=2.0
markdown>=3.5
```

### Analysis (optional)

```
sentence-transformers>=2.2.0
numpy>=1.24.0
```

### Development

```
pytest>=7.0
```

### pyproject.toml extras

```toml
[project.optional-dependencies]
analysis = ["sentence-transformers>=2.2.0", "numpy>=1.24.0"]
dev = ["pytest>=7.0"]
```

---

## Error Handling Patterns

### Missing optional dependencies

```python
# In overlap.py, gap_analysis.py
if not check_analysis_available():
    render_analysis_unavailable_message()
    return
```

### Malformed skill files

```python
# In skill_parser.py
# Log warning, skip file, continue parsing others
# Never crash on a single bad file
import logging
logger = logging.getLogger("skillkit")
logger.warning(f"Skipping {path}: missing required field 'name'")
```

### Missing config files

```python
# In config.py
# Auto-generate with defaults, log info message
# Never require the user to create config manually
```

### File write collisions (stub generation)

```python
# In stub_generator.py
# Check before writing, surface error in UI via st.error()
# Never silently overwrite
if target_path.exists():
    raise FileExistsError(f"Skill file already exists: {target_path}")
```

---

## Testing Strategy

### Testing Philosophy

**What to test:**
- Every public function's contract: given these inputs, assert these outputs
- Edge cases and error handling: malformed input, missing files, empty collections
- Cross-module integration: real user scenarios that touch multiple modules
- Graceful degradation: missing deps, missing configs, missing files
- Round-trip correctness: generate stub → parse it → get the same data back

**What NOT to test:**
- Streamlit rendering. No UI tests. `ui_components.py` functions are tested manually.
  Unit tests cover the data transformations those rendering functions depend on.
- The embedding model itself. We don't test whether all-MiniLM-L6-v2 produces good
  embeddings in general. We test that our code correctly computes, caches, compares,
  and classifies the vectors the model returns.
- File system permissions. Tests assume they can read/write to temp directories.
- Performance. Performance targets are verified manually during development, not in CI.
  (Exception: one smoke test that parsing 12 example skills completes in < 5 seconds.)

**Out of scope:** Symlinks, concurrent file access, non-UTF-8 file encodings beyond
what Python handles by default.

### Test Speed Tiers

- **Core tests** (`test_config.py`, `test_skill_parser.py`, `test_coverage.py`,
  `test_stub_generator.py`, `test_gap_analysis.py`): No external dependencies beyond
  PyYAML. Run in < 2 seconds total. Run on every change.
- **Analysis tests** (`test_overlap.py`, analysis-dependent cases in
  `test_gap_analysis.py`): Require sentence-transformers + numpy. Slow on cold
  cache (model load + embedding). Marked with `@pytest.mark.analysis`. Skipped
  automatically when deps are missing.
- **Integration tests** (`test_integration.py`): Exercise cross-module paths.
  Core integration tests run fast. Analysis integration tests are marked.

### How to Run

```bash
# All core tests (fast, no analysis deps needed)
pytest tests/ -m "not analysis"

# All tests including analysis
pytest tests/

# Single module
pytest tests/test_skill_parser.py -v

# Integration only
pytest tests/test_integration.py -v
```

---

## Shared Fixtures (tests/conftest.py)

```python
import pytest
import json
import shutil
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def tmp_skills_dir(tmp_path):
    """Empty temporary skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Empty temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def example_skills_dir(tmp_path):
    """Copy example skills into a temp directory for isolated testing.
    Returns path to the temp skills dir containing all 12 example skills in flat mode."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for domain_dir in EXAMPLES_DIR.iterdir():
        if domain_dir.is_dir():
            for skill_file in domain_dir.glob("*.md"):
                shutil.copy(skill_file, skills_dir / skill_file.name)
    return skills_dir


@pytest.fixture
def tiered_skills_dir(tmp_path):
    """Create a tiered directory with controlled override scenarios.

    Structure:
      default/base_skill.md          → active (only in default)
      default/overridden_skill.md    → shadowed by org
      default/fully_overridden.md    → shadowed by user (through org)
      default/draft_skill.md         → active draft (only in default)
      org/overridden_skill.md        → active (shadows default)
      org/fully_overridden.md        → shadowed by user
      org/org_only.md                → active (only in org)
      user/fully_overridden.md       → active (shadows org + default)
      user/user_only.md              → active (only in user)

    Expected active skills: base_skill, overridden_skill (org), fully_overridden (user),
                            draft_skill, org_only, user_only = 6 active
    Total files: 9
    """
    skills_dir = tmp_path / "skills"
    for tier in ["default", "org", "user"]:
        (skills_dir / tier).mkdir(parents=True)

    def write_skill(tier, name, description, status="active"):
        content = f"---\nname: {name}\ndescription: \"{description}\"\nstatus: {status}\n---\n\n# {name}\n\n## When to Use\nTest skill in {tier} tier.\n"
        (skills_dir / tier / f"{name}.md").write_text(content)

    write_skill("default", "base_skill", "A skill only in default tier")
    write_skill("default", "overridden_skill", "Default version of overridden skill")
    write_skill("default", "fully_overridden", "Default version of fully overridden")
    write_skill("default", "draft_skill", "A draft skill in default", status="draft")
    write_skill("org", "overridden_skill", "Org version of overridden skill")
    write_skill("org", "fully_overridden", "Org version of fully overridden")
    write_skill("org", "org_only", "A skill only in org tier")
    write_skill("user", "fully_overridden", "User version of fully overridden")
    write_skill("user", "user_only", "A skill only in user tier")

    return skills_dir


@pytest.fixture
def minimal_skill_content():
    """Minimum valid skill file content."""
    return "---\nname: test_skill\ndescription: \"A test skill for unit testing.\"\n---\n\n# Test Skill\n\nBody content here.\n"


@pytest.fixture
def full_skill_content():
    """Skill file with all frontmatter fields populated."""
    return """---
name: full_test_skill
description: "A fully populated test skill."
output_format: structured_report
domain: testing
status: active
domain_areas:
  - Testing
  - Quality
task_types:
  - Analyze
  - Classify
version: "1.0"
author: test_author
tags:
  - unit-test
  - fixture
---

# Full Test Skill

## When to Use
When running unit tests that need a complete skill fixture with all fields populated.

## Steps
1. Load the skill
2. Verify all fields

## Output Format
Structured test report.

## Common Pitfalls
Missing fields in frontmatter.
"""


@pytest.fixture
def small_query_log(tmp_path):
    """Query log with < 50 entries. Dead skill detection should NOT activate."""
    log_path = tmp_path / "query_log.json"
    entries = [
        {"timestamp": "2026-03-01T10:00:00", "query": "How do I get a refund?",
         "skill_loaded": "handle_refund", "skill_candidates": ["handle_refund"]},
        {"timestamp": "2026-03-01T10:05:00", "query": "What caused the outage?",
         "skill_loaded": None, "skill_candidates": []},
        {"timestamp": "2026-03-01T10:10:00", "query": "Summarize this paper",
         "skill_loaded": "summarize_paper", "skill_candidates": ["summarize_paper"]},
    ]
    log_path.write_text(json.dumps(entries))
    return log_path


@pytest.fixture
def large_query_log(tmp_path):
    """Query log with 60+ entries for dead skill detection testing.

    Loads handle_refund, classify_inquiry, summarize_paper, and diagnose_outage.
    NEVER loads: escalate_ticket, analyze_logs, extract_methodology, compare_studies,
                 classify_alert, generate_postmortem, assess_evidence_quality,
                 summarize_interaction.
    Also includes 3 unmatched queries.
    """
    log_path = tmp_path / "query_log.json"
    loaded_skills = ["handle_refund", "classify_inquiry", "summarize_paper", "diagnose_outage"]
    entries = []

    # 3 unmatched queries
    for q in ["What's our SLA rate?", "Translate to Spanish", "Run the deploy pipeline"]:
        entries.append({"timestamp": "2026-03-01T10:00:00", "query": q,
                        "skill_loaded": None, "skill_candidates": []})

    # 57 matched queries spread across 4 skills
    for i in range(57):
        skill = loaded_skills[i % len(loaded_skills)]
        entries.append({"timestamp": f"2026-03-01T11:{i:02d}:00",
                        "query": f"Query for {skill} #{i}",
                        "skill_loaded": skill, "skill_candidates": [skill]})

    log_path.write_text(json.dumps(entries))
    return log_path


# --- Marker registration and auto-skip ---

def pytest_configure(config):
    config.addinivalue_line("markers", "analysis: requires sentence-transformers and numpy")

def pytest_collection_modifyitems(config, items):
    try:
        import sentence_transformers
        import numpy
    except ImportError:
        skip_analysis = pytest.mark.skip(reason="analysis dependencies not installed")
        for item in items:
            if "analysis" in item.keywords:
                item.add_marker(skip_analysis)
```

---

## Test Specifications by Module

Each test case has an ID (e.g., TC-SP01) for traceability. The ID prefix maps to the
module: C = config, SP = skill_parser, CV = coverage, OV = overlap, GA = gap_analysis,
SG = stub_generator, INT = integration.

### test_config.py

```
TC-C01  Load existing skillkit.yaml with all fields set
        → All fields in SkillKitConfig match YAML values exactly

TC-C02  Load skillkit.yaml with only skills_dir set
        → Missing fields get default values (overlap_high=0.85,
          overlap_moderate=0.70, embedding_model="all-MiniLM-L6-v2", etc.)

TC-C03  No skillkit.yaml exists
        → Auto-generates file with defaults
        → Returns config with default values
        → File exists on disk after call

TC-C04  skills_dir as relative path ("./skills")
        → Resolved relative to config file's parent directory, not cwd

TC-C05  skills_dir as absolute path
        → Used as-is, no resolution

TC-C06  skills_dir doesn't exist on disk
        → Created by load_config
        → No error raised

TC-C07  data_dir doesn't exist
        → ensure_data_dir creates it with empty JSON files

TC-C08  Invalid YAML in skillkit.yaml (tab characters, unclosed bracket)
        → Raises clear error (not a raw yaml.scanner.ScannerError)
        → Error message includes the file path

TC-C09  coverage_config auto-generation from 12 example skills
        → domain_areas = sorted unique domain values from skills
        → task_types = default set of 8 types
        → File written to disk and is valid YAML

TC-C10  coverage_config auto-generation with zero skills
        → domain_areas = empty list
        → task_types = default set of 8 types
        → File still written (not an error condition)

TC-C11  Load existing coverage_config.yaml
        → Returns exact domain_areas and task_types from file

TC-C12  coverage_config.yaml with empty domain_areas list
        → Returns empty rows, default columns
        → No crash (coverage map will simply be empty)

TC-C13  coverage_config.yaml with empty task_types list
        → Returns rows from file, empty columns
        → No crash

TC-C14  query_log path set to file that doesn't exist
        → Config loads successfully (log is optional)
        → query_log_path is set in config (existence checked at read time, not config time)
```

### test_skill_parser.py

#### Frontmatter Parsing

```
TC-SP01  Parse minimal skill (name + description only)
         → Skill object has correct name, description
         → All optional fields have defaults (domain="general", status="active",
           output_format="text", domain_areas=[], task_types=[], tags=[])
         → word_count > 0
         → body is non-empty string

TC-SP02  Parse skill with all frontmatter fields (use full_skill_content fixture)
         → Every field populated correctly including version, author
         → domain_areas and task_types are lists of strings
         → tags is a list of strings

TC-SP03  Missing 'name' field in frontmatter
         → Returns None (file skipped)
         → Warning logged containing the file path (verify with caplog fixture)

TC-SP04  Missing 'description' field in frontmatter
         → Returns None
         → Warning logged containing the file path

TC-SP05  Empty string name (name: "")
         → Returns None (treated as missing — empty name is not usable)

TC-SP06  Empty string description (description: "")
         → Returns None (treated as missing)

TC-SP07  Malformed YAML: unclosed quote in description
         → Returns None
         → Warning logged (not an unhandled exception)

TC-SP08  Malformed YAML: tab indentation instead of spaces
         → Returns None
         → Warning logged

TC-SP09  Empty file (zero bytes)
         → Returns None

TC-SP10  File with only frontmatter delimiters, no body
         Input: "---\nname: x\ndescription: \"y\"\n---\n"
         → Valid skill with empty body and word_count = 0

TC-SP11  File with no frontmatter delimiters (plain markdown)
         → Returns None (not a skill file)

TC-SP12  File with single --- delimiter (no closing ---)
         → Returns None

TC-SP13  Frontmatter with unknown/extra fields (e.g., "priority: high")
         → Parsed successfully, unknown fields silently ignored
         → No warning (forward compatibility with future fields)

TC-SP14  status field with unknown value (e.g., "beta")
         → Defaults to "active"
         → Warning logged

TC-SP15  domain_areas provided as a scalar string instead of a list
         Input: "domain_areas: Testing" (no list syntax)
         → Coerced to single-element list ["Testing"]
         → No crash

TC-SP16  tags provided as a single string
         → Same coercion as TC-SP15: wrapped into list

TC-SP17  Skill with UTF-8 characters in name and description
         Input: name: "análisis_datos", description: "Análisis de données"
         → Parsed correctly, characters preserved in Skill object

TC-SP18  Skill file with Windows line endings (\r\n)
         → Parsed correctly, body doesn't contain stray \r characters

TC-SP19  Skill file with trailing whitespace in frontmatter values
         → Values are stripped of leading/trailing whitespace
```

#### When to Use Extraction

```
TC-SP20  Body has "## When to Use" section followed by another ## section
         → Extracts text between headings, stripped of leading/trailing whitespace
         → Does NOT include the "## When to Use" heading itself
         → Does NOT include the following ## heading

TC-SP21  Body has "## When to Use" as the last section (no following ##)
         → Extracts all remaining text from heading to end of body

TC-SP22  Body has no "## When to Use" section
         → when_to_use = "" (empty string)

TC-SP23  Body has "## When to use" (lowercase 'u')
         → Case-insensitive match, extracted correctly

TC-SP24  Body has "## When To Use" (title case)
         → Case-insensitive match, extracted correctly

TC-SP25  Body has "### When to Use" (h3 instead of h2)
         → NOT matched (only ## level headings count)
         → when_to_use = ""

TC-SP26  Body has multiple "## When to Use" sections
         → First one is extracted (warn, don't crash)
```

#### Directory Detection and Registry Loading

```
TC-SP30  Flat directory with .md files at root level
         → mode = "flat"
         → All .md files parsed into registry

TC-SP31  Flat directory with non-tier subdirectories
         (e.g., skills/customer_support/, skills/devops/)
         → mode = "flat"
         → Recursively finds and parses .md files in subdirectories

TC-SP32  Tiered directory with default/, org/, user/ subdirs
         → mode = "tiered"
         → Each skill has tier field set

TC-SP33  Directory with only default/ subdir (no org/ or user/)
         → mode = "tiered"
         → All skills have tier = "default"

TC-SP34  Empty skills directory (no files at all)
         → Empty registry, mode = "flat"
         → No crash, no warning

TC-SP35  Directory with non-.md files (e.g., .txt, .yaml, .py, README)
         → Non-.md files silently ignored
         → Only .md files parsed

TC-SP36  Directory with mix of valid and invalid .md files
         → Valid files parsed into registry
         → Invalid files skipped with warnings
         → Registry contains only the valid skills
         → Verify: registry.total_count equals number of valid files

TC-SP37  Load all 12 example skills
         → Registry has 12 skills
         → 3 distinct domains present
         → At least 1 draft skill, at least 1 deprecated skill
         → All skills have non-empty body and word_count > 0
```

#### Override Resolution (Tiered Mode)

```
TC-SP40  Skill exists only in default tier
         → is_active = True, tier = "default", shadows = []

TC-SP41  Same skill name in default and org
         → org version: is_active = True, tier = "org", shadows = ["default"]
         → default version: is_active = False

TC-SP42  Same skill name in all three tiers
         → user version: is_active = True, tier = "user", shadows = ["org", "default"]
         → org version: is_active = False
         → default version: is_active = False

TC-SP43  Same skill name in default and user (skipping org)
         → user version: is_active = True, shadows = ["default"]
         → default version: is_active = False

TC-SP44  Different skills in different tiers (no name collisions)
         → All skills are is_active = True

TC-SP45  get_active_skills() in tiered mode (use tiered_skills_dir fixture)
         → Returns only is_active=True skills
         → Count equals 6 (base_skill, overridden_skill[org], fully_overridden[user],
           draft_skill, org_only, user_only)

TC-SP46  get_by_name() returns active version only
         → get_by_name("overridden_skill") returns the org version
         → get_by_name("fully_overridden") returns the user version
```

#### Registry Query Methods

```
TC-SP50  filter(domains=["testing"]) → returns only skills with domain="testing"

TC-SP51  filter(domains=["testing"], statuses=["active"])
         → AND logic: skills must match domain AND status

TC-SP52  filter(tags=["tag1", "tag2"])
         → OR logic within tags: skill matches if it has ANY of the listed tags

TC-SP53  filter(search_query="refund")
         → Case-insensitive substring match across name + description
         → Matches "handle_refund" (name) and "Process refund requests" (description)

TC-SP54  filter() with all parameters None → returns all active skills

TC-SP55  search("") (empty string) → returns all active skills

TC-SP56  search("xyznonexistent") → returns empty list

TC-SP57  get_all_domains() → sorted unique values, no duplicates

TC-SP58  get_all_tags() → sorted, flattened from all skills' tag lists, no duplicates

TC-SP59  get_all_output_formats() → sorted unique values
```

### test_coverage.py

#### Design Clarification: Deprecated Skills in Coverage

Deprecated skills with `is_active=True` (not shadowed) are treated the same as active
skills for cell state purposes. A cell with only deprecated skills is `COVERED`, not a
special state. The visual indicator for deprecated status is handled in the UI layer,
not the data model. Rationale: deprecated skills still work — they're just scheduled
for eventual removal.

#### Matrix Building

```
TC-CV01  Build matrix from skills with both domain_areas and task_types tags
         → Skills appear in correct cells
         → Each (domain_area, task_type) combination has the skill

TC-CV02  Skill with 2 domain_areas and 3 task_types
         → Appears in 6 cells (cartesian product)

TC-CV03  Skill with domain_areas but empty task_types list
         → Goes into unmapped_skills, not placed on grid

TC-CV04  Skill with task_types but empty domain_areas list
         → Goes into unmapped_skills

TC-CV05  Skill with neither domain_areas nor task_types
         → Goes into unmapped_skills

TC-CV06  Skill with domain_area value not in config's row list
         → That tag combination silently ignored (no new row created)
         → Skill still placed in cells where its other tags DO match config

TC-CV07  Skill with task_type value not in config's column list
         → Same behavior: silently ignored for non-matching columns

TC-CV08  Cell with only status=active skills → CellState.COVERED
TC-CV09  Cell with only status=draft skills → CellState.DRAFT_ONLY
TC-CV10  Cell with no skills → CellState.EMPTY
TC-CV11  Cell with mix of active and draft → CellState.COVERED (active takes precedence)
TC-CV12  Cell with only deprecated skills → CellState.COVERED (see clarification above)
TC-CV13  Cell with deprecated + draft → CellState.COVERED (deprecated counts as covered)

TC-CV14  get_cell(domain_area, task_type) for existing cell → returns CoverageCell
TC-CV15  get_cell() for non-existent combination → returns None

TC-CV16  empty_cells property → list of all EMPTY cells only
         → Does not include COVERED or DRAFT_ONLY cells
```

#### Coverage Score

```
TC-CV20  All cells covered → score = 100.0
TC-CV21  No cells covered → score = 0.0
TC-CV22  Half covered, half empty → score = 50.0
TC-CV23  Mix of COVERED and DRAFT_ONLY (no EMPTY) → score = 100.0
         Per spec formula: (green + yellow) / total × 100
TC-CV24  Empty matrix (zero rows or zero columns) → score = 0.0, no ZeroDivisionError
TC-CV25  Deterministic: same inputs → identical score across multiple calls
```

#### Coverage History

```
TC-CV30  Record first entry → entry created with correct fields, delta = None
TC-CV31  Record entry when score changed from last → new entry appended
TC-CV32  Record entry when score unchanged → no new entry, returns None
TC-CV33  Record twice on same day → second replaces first (one entry per day max)
TC-CV34  delta_since_last with two entries → correct difference (new - old)
TC-CV35  Load history from valid JSON file → correct entries
TC-CV36  Load history from missing file → empty history, no error
TC-CV37  Load history from malformed JSON → empty history, warning logged
TC-CV38  Save and reload round-trip → entries identical after reload
         → Dates, scores, counts all preserved
```

### test_overlap.py

All tests in this file are marked `@pytest.mark.analysis`.

**Note on model-dependent assertions:** Tests TC-OV22, TC-OV23, TC-OV40 assert similarity
ranges that depend on the all-MiniLM-L6-v2 model. These are calibration tests — they
verify that the example skills are well-designed for demo purposes. If the embedding model
changes, these thresholds should be recalibrated, not the code. Use tolerance bands
(±0.10) rather than exact thresholds.

#### Embedding Computation

```
TC-OV01  Compute embeddings for list of skills
         → Returns dict with one entry per skill name
         → Each embedding is a list of floats
         → Embedding dimension = 384 (for all-MiniLM-L6-v2)

TC-OV02  Embedding text is description + " " + when_to_use
         → Verify by computing SHA-256 of that concatenation and checking it matches
           the cache key used

TC-OV03  Skill with empty when_to_use
         → Embedding computed from description only (description + " ")
         → No crash, returns valid embedding
```

#### Caching

```
TC-OV10  Cold cache: all skills computed fresh
         → Cache populated with all entries after call
         → Cache model_name field matches configured model

TC-OV11  Warm cache: all content unchanged
         → Returns same embeddings as cold cache produced
         → Verify no model inference occurs (mock the model or check timing:
           warm load should be 100x+ faster than cold)

TC-OV12  Partial cache: some skills cached, one new skill added
         → Only new skill triggers embedding computation
         → Previously cached skills return identical embeddings

TC-OV13  Content changed: skill description edited → different SHA-256 hash
         → Old cache entry unused
         → New embedding computed and cached under new hash

TC-OV14  Model name changed in config (e.g., "all-MiniLM-L6-v2" → "other-model")
         → Entire cache invalidated on load (model mismatch)
         → All embeddings recomputed
         → New cache has updated model_name

TC-OV15  Cache save and reload round-trip
         → Embeddings numerically identical after JSON round-trip
         → No floating point drift beyond JSON serialization precision

TC-OV16  Cache file doesn't exist → starts with empty cache, no error
TC-OV17  Cache file is malformed JSON → starts with empty cache, warning logged
```

#### Pairwise Similarity

```
TC-OV20  Two identical text strings → similarity > 0.99
TC-OV21  Two completely unrelated strings ("quantum physics" vs "chocolate cake recipe")
         → similarity < 0.30

TC-OV22  [Calibration] handle_refund ↔ escalate_ticket → similarity in range [0.65, 0.95]
         (designed overlapping pair — tolerance band accounts for model variation)
TC-OV23  [Calibration] handle_refund ↔ summarize_paper → similarity < 0.55
         (designed distinct pair)

TC-OV24  Single skill in registry → empty pairs list, no crash
TC-OV25  Two skills → exactly one pair
TC-OV26  N skills → exactly N*(N-1)/2 pairs
TC-OV27  Pairs returned sorted by similarity descending
```

#### Risk Classification

```
TC-OV30  similarity = 0.90 (> overlap_high 0.85) → risk_level = "high"
TC-OV31  similarity = 0.75 (between thresholds) → risk_level = "moderate"
TC-OV32  similarity = 0.50 (< overlap_moderate 0.70) → risk_level = "low"
TC-OV33  similarity = 0.85 exactly → risk_level = "high" (threshold is inclusive)
TC-OV34  similarity = 0.70 exactly → risk_level = "moderate" (threshold is inclusive)
```

#### Overlap Report

```
TC-OV40  [Calibration] Report with 12 example skills
         → At least 1 pair flagged as moderate or high
         → Pairs sorted by similarity descending
         → Each pair has text_a and text_b populated (non-empty)

TC-OV41  Report filters out low-risk pairs from .pairs list
         → All pairs in report.pairs have similarity >= moderate threshold

TC-OV42  high_risk_pairs returns only risk_level="high" subset
TC-OV43  moderate_risk_pairs returns only risk_level="moderate" subset

TC-OV44  Report with zero pairs above threshold (very distinct skills)
         → report.pairs is empty list
         → high_risk_pairs and moderate_risk_pairs both empty
         → No crash
```

#### Query Simulation

```
TC-OV50  Query closely matching a specific skill's description
         → That skill ranks first (or in top 2) in results
         → ranked_skills is non-empty

TC-OV51  Ambiguous query (top two skills within 0.05 of each other)
         → is_ambiguous = True
         (May need to construct a deliberately ambiguous query against example skills)

TC-OV52  Clear query (top skill well ahead of second by > 0.10)
         → is_ambiguous = False

TC-OV53  Empty query string
         → Returns result without crashing (empty ranked_skills or all low scores)

TC-OV54  Query against empty registry
         → ranked_skills is empty list
         → is_ambiguous = False
         → No crash
```

#### Graceful Degradation

```
TC-OV60  check_analysis_available() when deps ARE installed → returns True
         (This test only runs when analysis marker is not skipped)

TC-OV61  check_analysis_available() when deps are missing → returns False
         Use unittest.mock.patch to simulate ImportError on sentence_transformers
         This test is NOT marked @analysis (it tests the fallback path)
```

### test_gap_analysis.py

#### Query Log Parsing

```
TC-GA01  Parse valid query log (use small_query_log fixture)
         → Correct count of total entries
         → Fields parsed correctly (timestamp, query, skill_loaded, skill_candidates)

TC-GA02  Query log file path is None → load_query_log returns None

TC-GA03  Query log file doesn't exist on disk → load_query_log returns None, no crash

TC-GA04  Query log is empty JSON array "[]" → returns empty list

TC-GA05  Query log entry missing 'query' field → entry skipped, others parsed
         → Warning logged for malformed entry

TC-GA06  Query log is not valid JSON → returns None, warning logged

TC-GA07  get_unmatched_queries: entries with skill_loaded=None included
         → entries with skill_loaded set excluded
         → Count matches expected unmatched entries from fixture
```

#### Manual Queries

```
TC-GA10  Save manual queries to data dir → file created at data/manual_queries.json
TC-GA11  Load manual queries → matches what was saved
TC-GA12  Load manual queries when file doesn't exist → empty list, no error
TC-GA13  Merge: manual queries combined with unmatched log queries
         → Combined list contains entries from both sources
         → Duplicates preserved (same query in both sources counts twice for frequency)
TC-GA14  Manual queries alone (no log file) → works as sole input for gap report
TC-GA15  Save empty list → valid JSON file written, reload returns empty list
```

#### Dead Skill Detection

```
TC-GA20  Large log (60 entries), some skills never loaded
         → Unloaded skills appear in dead skills list (use large_query_log fixture)
         → Loaded skills (handle_refund, classify_inquiry, etc.) do NOT appear

TC-GA21  Large log where ALL active skills are loaded at least once
         → Empty dead skills list

TC-GA22  Small log (< 50 entries, use small_query_log fixture)
         → Dead skill detection does not run
         → Returns empty list regardless of which skills appear in log

TC-GA23  Deprecated skill never loaded in large log
         → Still flagged as dead (deprecated ≠ exempt from detection)

TC-GA24  Shadowed skill (is_active=False in tiered mode) never loaded
         → NOT flagged (only active skills are checked)
```

#### Coverage Gaps

```
TC-GA30  Empty cells from coverage matrix listed in gap report
TC-GA31  Gap prioritization: gaps in rows/columns with more existing coverage rank higher
         → A gap in a row with 3 covered cells ranks above a gap in a row with 0
```

#### Query Clustering (requires analysis deps)

```
TC-GA40  @pytest.mark.analysis
         3 semantically similar queries → grouped into 1 cluster
         → count = 3
         → representative_query is one of the input queries
         → suggested_skill_name is non-empty string

TC-GA41  @pytest.mark.analysis
         3 unrelated queries → separate clusters (up to 3)

TC-GA42  @pytest.mark.analysis
         Empty query list → empty clusters list, no crash
```

#### Gap Report Assembly

```
TC-GA50  Build gap report with large log + coverage matrix + manual queries
         → has_query_log = True
         → has_manual_queries = True
         → unmatched_query_count > 0
         → coverage_gaps populated from matrix empty cells
         → dead_skills populated (if large enough log)

TC-GA51  Build gap report with no log, no manual queries
         → has_query_log = False
         → has_manual_queries = False
         → Only coverage_gaps populated
         → clusters list is empty
         → dead_skills list is empty
```

### test_stub_generator.py

#### Template Generation

```
TC-SG01  Generate stub with name, description, domain
         → Output string starts with "---"
         → YAML frontmatter parseable and contains all provided fields
         → status = "draft" (always for stubs)
         → Body contains ## When to Use, ## Steps, ## Output Format, ## Common Pitfalls
         → All TODO sections have TODO placeholder text

TC-SG02  Generate stub with domain_areas and task_types
         → Frontmatter includes domain_areas as YAML list
         → Frontmatter includes task_types as YAML list

TC-SG03  Generate stub with minimal input (name only, empty description)
         → description in frontmatter starts with "TODO:"
         → domain defaults to "general"
         → Still valid when parsed

TC-SG04  Round-trip: generate stub → write to file → parse with parse_skill_file
         → Parsed Skill has matching name, description, domain
         → status = "draft"
         → domain_areas and task_types match if provided
         → This is a CRITICAL test. It validates that stub_generator produces files
           that skill_parser can read without errors. Both modules must agree on format.

TC-SG05  Generate stub with all optional fields → all appear in frontmatter correctly
```

#### Name Generation

```
TC-SG10  generate_name_from_coverage("Analyze", "Data Analysis")
         → "analyze_data_analysis"

TC-SG11  generate_name_from_coverage("Debug", "Code & Development")
         → "debug_code_and_development"

TC-SG12  generate_name_from_coverage("Summarize", "Research")
         → "summarize_research"

TC-SG13  Input with multiple consecutive spaces → collapsed to single underscore

TC-SG14  Input with leading/trailing whitespace → trimmed before conversion

TC-SG15  Input with characters unsafe for filenames (e.g., "/", ":")
         → Removed or replaced (output is safe for use as a filename)
```

#### File Writing

```
TC-SG20  Write stub in flat mode
         → File created at skills_dir/{name}.md
         → File content matches generated template

TC-SG21  Write stub in tiered mode
         → File created at skills_dir/default/{name}.md

TC-SG22  Write stub when file already exists
         → Raises FileExistsError
         → Original file content unchanged (read before and after, compare)

TC-SG23  Write stub when skills_dir/default/ doesn't exist yet (tiered mode)
         → default/ directory auto-created
         → File written successfully

TC-SG24  Written stub file is parseable
         → parse_skill_file on the written path returns valid Skill
         → Skill.status = "draft"

TC-SG25  write_stub returns correct Path object
         → Returned path .exists() is True
         → Returned path matches expected location for the mode
```

### test_integration.py

These tests exercise workflows that cross module boundaries. They use the real
module functions (not mocks) to verify the system works end-to-end.

#### First-Run Scenarios

```
TC-INT01  Fresh empty directory → full bootstrap
          Steps:
            1. tmp_path with no files
            2. load_config(tmp_path / "skillkit.yaml")
          Assert:
            → skillkit.yaml created on disk with defaults
            → skills/ directory created
            → Example skill files present in skills/
            → load_registry succeeds with example skills
            → build_coverage_matrix returns valid (non-empty) matrix
            → No exceptions in the entire chain

TC-INT02  Directory with existing skills, no config files
          Steps:
            1. Copy example skills to tmp_path/skills/
            2. load_config (no skillkit.yaml present)
          Assert:
            → skillkit.yaml auto-created, skills_dir = ./skills
            → coverage_config.yaml auto-generated
            → domain_areas in coverage config match skill domains
            → load_registry → correct skill count

TC-INT03  Tiered directory auto-detection and override resolution
          Steps:
            1. Use tiered_skills_dir fixture
            2. load_config with skills_dir pointing to fixture
            3. load_registry
          Assert:
            → mode = "tiered"
            → get_active_skills() count = 6 (per fixture doc)
            → get_by_name("fully_overridden").tier = "user"
            → get_by_name("overridden_skill").tier = "org"
```

#### Coverage Map → Stub → Reload Cycle

```
TC-INT10  Full cycle: find gap → create stub → verify gap filled
          Steps:
            1. Load registry from example_skills_dir
            2. Load coverage config, build matrix
            3. Count empty cells (N)
            4. Pick one empty cell, note its domain_area and task_type
            5. generate_name_from_coverage → generate_stub → write_stub
            6. Reload registry from same directory
            7. Rebuild matrix
          Assert:
            → New skill appears in registry with status="draft"
            → Empty cell count = N - 1
            → The previously empty cell is now DRAFT_ONLY
            → coverage_score increased (or equal, if matrix is very large)

TC-INT11  Stub collision: create same stub twice
          Steps:
            1. write_stub for "analyze_research"
            2. write_stub for "analyze_research" again
          Assert:
            → Second call raises FileExistsError
            → First file unchanged on disk (compare content before/after)
```

#### Gap Analysis End-to-End

```
TC-INT20  Manual query entry persists and appears in gap report
          Steps:
            1. Load registry
            2. save_manual_queries(["Deploy to staging", "Run CI pipeline"], data_dir)
            3. Build gap report (no query log)
          Assert:
            → has_manual_queries = True
            → unmatched_query_count = 2
            → has_query_log = False
            → coverage_gaps populated (from matrix)

TC-INT21  Full gap report with large query log
          Steps:
            1. Load registry from example skills
            2. Build coverage matrix
            3. Build gap report with large_query_log fixture
          Assert:
            → 3 unmatched queries found
            → Dead skills detected: skills not in the loaded set are flagged
            → Coverage gaps from matrix included
            → Clusters present if analysis deps available (or empty if not)
```

#### Overlap Detection End-to-End

```
TC-INT30  @pytest.mark.analysis
          Full pipeline: cold cache → warm cache
          Steps:
            1. Load registry from 12 example skills
            2. Build overlap report (cold cache, empty data_dir)
            3. Build overlap report again (same data_dir = warm cache)
          Assert:
            → At least 1 pair flagged moderate or high in both runs
            → Cache file exists in data_dir after first run
            → Second run produces same pair list as first run
            → Second run measurably faster (or mock model to verify no inference)

TC-INT31  @pytest.mark.analysis
          Query simulator against example skills
          Steps:
            1. Load registry from example skills
            2. simulate_query("customer wants their money back")
            3. simulate_query("analyze the server logs from last night")
          Assert:
            → Query 1: customer_support domain skills in top 3
            → Query 2: devops domain skills in top 3
            → Both return non-empty ranked lists
```

#### Registry Reflects Filesystem Changes

```
TC-INT40  Add a skill file to disk → reload → new skill visible
          Steps:
            1. Load registry from example_skills_dir (count = N)
            2. Write a new valid .md file directly to skills dir
            3. Reload registry
          Assert:
            → Registry count = N + 1
            → New skill findable by name via get_by_name

TC-INT41  Modify skill frontmatter on disk → reload → change reflected
          Steps:
            1. Load registry, get skill's domain (e.g., "research")
            2. Rewrite that skill file with domain = "modified_domain"
            3. Reload registry
          Assert:
            → Skill's domain = "modified_domain"
            → get_by_domain("modified_domain") includes it
            → get_by_domain("research") excludes it
```

---

## Test Count Summary

| File | Core Tests | Analysis Tests | Total |
|------|-----------|---------------|-------|
| test_config.py | 14 | 0 | 14 |
| test_skill_parser.py | 37 | 0 | 37 |
| test_coverage.py | 22 | 0 | 22 |
| test_overlap.py | 1 (TC-OV61) | 27 | 28 |
| test_gap_analysis.py | 17 | 3 | 20 |
| test_stub_generator.py | 14 | 0 | 14 |
| test_integration.py | 8 | 2 | 10 |
| **Total** | **113** | **32** | **145** |

Core tests (113) run in < 5 seconds with zero external dependencies.
Analysis tests (32) require sentence-transformers and add ~15-30 seconds on cold cache.

---

## Risk Coverage Matrix

Every high-risk failure mode is mapped to the specific test(s) that catch it.

| Risk | Severity | Tests |
|------|----------|-------|
| Malformed skill file crashes the app | High | TC-SP03 – SP12, TC-SP36 |
| Override resolution produces wrong active skill | High | TC-SP40 – SP46, TC-INT03 |
| Coverage score calculation wrong | Medium | TC-CV20 – CV25 |
| Coverage score corrupts or duplicates on save | Medium | TC-CV30 – CV38 |
| Embedding cache ignores content changes | High | TC-OV13 |
| Embedding cache ignores model changes | High | TC-OV14 |
| Missing analysis deps crash the app | High | TC-OV60 – OV61, auto-skip in conftest |
| Stub generator produces unparseable YAML | High | TC-SG04, TC-SG24 |
| Stub overwrites existing skill file | High | TC-SG22, TC-INT11 |
| First-run with no config crashes | High | TC-INT01 |
| First-run with existing skills ignores them | Medium | TC-INT02 |
| Gap analysis crashes without query log | Medium | TC-GA02 – GA03, TC-GA51 |
| Dead skill detection runs on too-small log | Low | TC-GA22 |
| Filter logic wrong (AND/OR confusion) | Medium | TC-SP51 – SP52 |
| Search case-sensitive when it shouldn't be | Low | TC-SP53 |
| Empty matrix causes division by zero | Medium | TC-CV24 |
| Coverage config with empty lists crashes | Low | TC-C12 – C13 |
| Round-trip stub → parse → different data | High | TC-SG04 |
| Name generation unsafe for filesystem | Medium | TC-SG15 |
| Tiered directory not detected | High | TC-SP32 – SP33, TC-INT03 |
| When to Use extraction picks wrong section | Medium | TC-SP20 – SP26 |

---

## Performance Targets

| Operation | Target | Approach |
|-----------|--------|----------|
| App launch (12 skills) | < 1s | Frontmatter parsing only, no embeddings |
| App launch (50 skills) | < 3s | Same |
| App launch (200 skills) | < 10s | Same |
| Coverage map render | < 0.5s | Pure data structure iteration |
| Overlap detection (12 skills, cold cache) | < 15s | Model load + embedding |
| Overlap detection (12 skills, warm cache) | < 1s | Cache lookup only |
| Overlap detection (50 skills, warm cache) | < 1s | N² similarity is fast on cached vectors |
| Query simulation (warm cache) | < 2s | One embedding + N similarities |
| Stub generation | < 0.1s | Template string formatting |

---

## Caching Details

### Embedding cache format (data/embedding_cache.json)

```json
{
  "model": "all-MiniLM-L6-v2",
  "entries": {
    "a1b2c3d4...": {
      "skill_name": "handle_refund",
      "embedding": [0.0123, -0.0456, ...],
      "content_hash": "a1b2c3d4..."
    }
  }
}
```

- Key is SHA-256 of (description + " " + when_to_use) text
- If `model` field doesn't match current config, entire cache is dropped
- Embeddings are stored as JSON arrays of floats (not binary) for debuggability
- Cache file size for 50 skills with 384-dim embeddings: ~1.5MB (acceptable for JSON)

### Coverage history format (data/coverage_history.json)

```json
{
  "entries": [
    {
      "date": "2026-03-10",
      "score": 67.5,
      "total_cells": 48,
      "covered_cells": 28,
      "draft_cells": 4,
      "empty_cells": 16,
      "total_skills": 12
    }
  ]
}
```

---

## Key Invariants

These must always be true. If any are violated, stop and debug.

1. **SkillKit never modifies existing .md files.** Only writes new stubs and data/ files.
2. **A skill with only name + description is valid.** All other fields have defaults.
3. **Missing analysis deps never crash the app.** Pages show install instructions instead.
4. **Missing config files are auto-generated.** The app runs with zero user configuration.
5. **In tiered mode, exactly one version of each skill name is active.** user > org > default.
6. **Coverage score is deterministic.** Same skills + same config = same score.
7. **Embedding cache is keyed by content, not filename.** Renaming a file doesn't invalidate its embedding if the content hasn't changed.
8. **Stub generation never overwrites.** Collision = error surfaced to user.
