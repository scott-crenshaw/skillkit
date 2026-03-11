"""Gap analysis: query log parsing, clustering, dead skill detection."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import SkillKitConfig
from .coverage import CoverageCell, CoverageMatrix
from .overlap import check_analysis_available
from .skill_parser import Skill, SkillRegistry

logger = logging.getLogger("skillkit")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

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
    representative_query: str
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
    suggestion: str  # "improve description" | "deprecate" | "merge with X"


@dataclass
class GapReport:
    """Complete gap analysis output."""
    unmatched_query_count: int
    total_query_count: int
    clusters: list[QueryCluster] = field(default_factory=list)
    coverage_gaps: list[CoverageCell] = field(default_factory=list)
    dead_skills: list[DeadSkill] = field(default_factory=list)
    has_query_log: bool = False
    has_manual_queries: bool = False


# ---------------------------------------------------------------------------
# Query log parsing
# ---------------------------------------------------------------------------

def load_query_log(path: Optional[Path]) -> Optional[list[QueryLogEntry]]:
    """Load and parse query log. Returns None if path is None or file missing."""
    if path is None:
        return None
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not parse query log %s: %s", path, exc)
        return None

    if not isinstance(raw, list):
        logger.warning("Query log at %s is not a JSON array", path)
        return None

    entries: list[QueryLogEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict entry in query log")
            continue
        if "query" not in item:
            logger.warning("Skipping query log entry missing 'query' field: %s", item)
            continue
        entries.append(QueryLogEntry(
            timestamp=item.get("timestamp", ""),
            query=item["query"],
            skill_loaded=item.get("skill_loaded"),
            skill_candidates=item.get("skill_candidates", []),
        ))

    return entries


# ---------------------------------------------------------------------------
# Manual queries
# ---------------------------------------------------------------------------

def load_manual_queries(data_dir: Path) -> list[str]:
    """Load from data/manual_queries.json. Returns empty list if missing."""
    path = data_dir / "manual_queries.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load manual queries: %s", exc)
        return []
    if not isinstance(raw, list):
        return []
    return [q for q in raw if isinstance(q, str)]


def save_manual_queries(queries: list[str], data_dir: Path) -> None:
    """Persist manual queries to data/manual_queries.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "manual_queries.json"
    path.write_text(json.dumps(queries), encoding="utf-8")


# ---------------------------------------------------------------------------
# Unmatched query extraction
# ---------------------------------------------------------------------------

def get_unmatched_queries(
    log: Optional[list[QueryLogEntry]],
    manual_queries: list[str],
) -> list[str]:
    """Extract unmatched queries from log + all manual queries.

    Unmatched = log entries where skill_loaded is None.
    Manual queries are always included (they represent known gaps).
    Duplicates preserved — same query in both sources counts twice.
    """
    result: list[str] = []
    if log is not None:
        for entry in log:
            if entry.skill_loaded is None:
                result.append(entry.query)
    result.extend(manual_queries)
    return result


# ---------------------------------------------------------------------------
# Dead skill detection
# ---------------------------------------------------------------------------

def detect_dead_skills(
    registry: SkillRegistry,
    log: list[QueryLogEntry],
    min_log_size: int = 50,
) -> list[DeadSkill]:
    """Find active skills never loaded in the query log.

    Only runs if log has >= min_log_size entries.
    """
    if len(log) < min_log_size:
        return []

    loaded_names: set[str] = set()
    for entry in log:
        if entry.skill_loaded is not None:
            loaded_names.add(entry.skill_loaded)

    active_skills = registry.get_active_skills()
    dead: list[DeadSkill] = []
    for skill in active_skills:
        if skill.name not in loaded_names:
            suggestion = _suggest_dead_action(skill, loaded_names)
            dead.append(DeadSkill(skill=skill, suggestion=suggestion))

    return dead


def _suggest_dead_action(skill: Skill, loaded_names: set[str]) -> str:
    """Generate a suggestion for a dead skill."""
    # If description is very short, suggest improving it
    if len(skill.description) < 30:
        return "improve description"
    # If skill is deprecated, suggest full deprecation
    if skill.status == "deprecated":
        return "deprecate"
    # Default: suggest improving description
    return "improve description"


# ---------------------------------------------------------------------------
# Query clustering (requires analysis deps)
# ---------------------------------------------------------------------------

def _generate_skill_name(queries: list[str]) -> str:
    """Generate a snake_case skill name from a cluster of queries."""
    # Use the shortest query as a basis
    shortest = min(queries, key=len)
    # Clean and convert to snake_case
    name = shortest.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    # Truncate to reasonable length
    parts = name.split("_")[:5]
    return "_".join(parts) or "unnamed_skill"


def _generate_description(queries: list[str]) -> str:
    """Generate a description from cluster queries."""
    if len(queries) == 1:
        return f"Handle queries like: {queries[0]}"
    return f"Handle queries like: {queries[0]} and {len(queries) - 1} similar"


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
    if not queries:
        return []

    if not check_analysis_available():
        return []

    import numpy as np
    from sklearn.cluster import AgglomerativeClustering

    from .overlap import _get_model

    model = _get_model(model_name)
    embeddings = model.encode(queries, convert_to_numpy=True)

    # Normalize for cosine distance
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normalized = embeddings / norms

    # Cosine distance matrix
    sim_matrix = normalized @ normalized.T
    distance_matrix = 1 - sim_matrix
    np.fill_diagonal(distance_matrix, 0)
    # Clip small negative values from floating point
    distance_matrix = np.clip(distance_matrix, 0, 2)

    if len(queries) == 1:
        labels = [0]
    else:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            metric="precomputed",
            linkage="average",
        )
        labels = clustering.fit_predict(distance_matrix)

    # Group queries by cluster label
    cluster_map: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        cluster_map.setdefault(label, []).append(idx)

    clusters: list[QueryCluster] = []
    for label, indices in cluster_map.items():
        cluster_queries_list = [queries[i] for i in indices]
        cluster_embeddings = normalized[indices]

        # Find most central query (highest average similarity to others)
        if len(indices) == 1:
            rep_idx = 0
        else:
            cluster_sim = cluster_embeddings @ cluster_embeddings.T
            avg_sim = cluster_sim.mean(axis=1)
            rep_idx = int(np.argmax(avg_sim))

        representative = cluster_queries_list[rep_idx]
        suggested_name = _generate_skill_name(cluster_queries_list)
        suggested_desc = _generate_description(cluster_queries_list)

        clusters.append(QueryCluster(
            representative_query=representative,
            queries=cluster_queries_list,
            count=len(cluster_queries_list),
            suggested_skill_name=suggested_name,
            suggested_description=suggested_desc,
            suggested_domain_areas=[],
            suggested_task_types=[],
        ))

    # Sort by cluster size descending
    clusters.sort(key=lambda c: c.count, reverse=True)
    return clusters


# ---------------------------------------------------------------------------
# Coverage gap prioritization
# ---------------------------------------------------------------------------

def _prioritize_gaps(
    gaps: list[CoverageCell],
    matrix: CoverageMatrix,
) -> list[CoverageCell]:
    """Sort gaps so rows/columns with more existing coverage rank higher.

    A gap in a row with 3 covered cells ranks above a gap in a row with 0.
    """
    def coverage_score(cell: CoverageCell) -> int:
        row_coverage = sum(
            1 for col in matrix.columns
            if matrix.get_cell(cell.domain_area, col) is not None
            and matrix.get_cell(cell.domain_area, col).state != CellState.EMPTY
        )
        col_coverage = sum(
            1 for row in matrix.rows
            if matrix.get_cell(row, cell.task_type) is not None
            and matrix.get_cell(row, cell.task_type).state != CellState.EMPTY
        )
        return row_coverage + col_coverage

    from .coverage import CellState
    return sorted(gaps, key=coverage_score, reverse=True)


# ---------------------------------------------------------------------------
# Gap report assembly
# ---------------------------------------------------------------------------

def build_gap_report(
    registry: SkillRegistry,
    matrix: CoverageMatrix,
    config: SkillKitConfig,
) -> GapReport:
    """Full gap analysis pipeline."""
    # Load query sources
    log = load_query_log(config.query_log_path)
    manual = load_manual_queries(config.data_dir)

    has_query_log = log is not None and len(log) > 0
    has_manual = len(manual) > 0

    # Unmatched queries
    unmatched = get_unmatched_queries(log, manual)
    total_count = (len(log) if log else 0) + len(manual)

    # Coverage gaps (always available)
    coverage_gaps = _prioritize_gaps(matrix.empty_cells, matrix)

    # Query clustering (if deps + queries available)
    clusters: list[QueryCluster] = []
    if unmatched and check_analysis_available():
        clusters = cluster_queries(
            unmatched, config.cluster_threshold, config.embedding_model
        )

    # Dead skills (if log large enough)
    dead: list[DeadSkill] = []
    if log is not None:
        dead = detect_dead_skills(registry, log)

    return GapReport(
        unmatched_query_count=len(unmatched),
        total_query_count=total_count,
        clusters=clusters,
        coverage_gaps=coverage_gaps,
        dead_skills=dead,
        has_query_log=has_query_log,
        has_manual_queries=has_manual,
    )
