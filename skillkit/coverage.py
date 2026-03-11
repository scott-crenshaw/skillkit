"""Coverage matrix building, scoring, and history tracking."""

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

from .skill_parser import Skill, SkillRegistry

logger = logging.getLogger("skillkit")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class CellState(Enum):
    COVERED = "covered"
    DRAFT_ONLY = "draft_only"
    EMPTY = "empty"


@dataclass
class CoverageCell:
    """One cell in the coverage matrix."""
    domain_area: str
    task_type: str
    skills: list[Skill] = field(default_factory=list)
    state: CellState = CellState.EMPTY


@dataclass
class CoverageMatrix:
    """The full domain_area x task_type grid."""
    rows: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    cells: dict[tuple[str, str], CoverageCell] = field(default_factory=dict)
    unmapped_skills: list[Skill] = field(default_factory=list)

    @property
    def coverage_score(self) -> float:
        """(covered + draft_only) / total cells x 100"""
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
        """All cells with no skills."""
        return [c for c in self.cells.values() if c.state == CellState.EMPTY]

    def get_cell(self, domain_area: str, task_type: str) -> Optional[CoverageCell]:
        return self.cells.get((domain_area, task_type))


@dataclass
class CoverageHistoryEntry:
    date: str
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
        score = matrix.coverage_score
        total_cells = len(matrix.rows) * len(matrix.columns)
        covered = sum(1 for c in matrix.cells.values() if c.state == CellState.COVERED)
        draft = sum(1 for c in matrix.cells.values() if c.state == CellState.DRAFT_ONLY)
        empty = sum(1 for c in matrix.cells.values() if c.state == CellState.EMPTY)
        today = date.today().isoformat()

        # If latest entry has same score, skip
        if self.entries and self.entries[-1].score == score:
            return False

        entry = CoverageHistoryEntry(
            date=today,
            score=score,
            total_cells=total_cells,
            covered_cells=covered,
            draft_cells=draft,
            empty_cells=empty,
            total_skills=total_skills,
        )

        # Replace same-day entry
        if self.entries and self.entries[-1].date == today:
            self.entries[-1] = entry
        else:
            self.entries.append(entry)
        return True

    def latest_score(self) -> Optional[float]:
        return self.entries[-1].score if self.entries else None

    def delta_since_last(self, current: float) -> Optional[float]:
        """Difference between current score and the previous entry."""
        if not self.entries:
            return None
        return current - self.entries[-1].score


# ---------------------------------------------------------------------------
# Matrix building
# ---------------------------------------------------------------------------

def _determine_cell_state(skills: list[Skill]) -> CellState:
    """Determine cell state from the skills in it.

    - COVERED if any skill has status 'active' or 'deprecated'
    - DRAFT_ONLY if all skills are draft
    - EMPTY if no skills
    """
    if not skills:
        return CellState.EMPTY
    if any(s.status in ("active", "deprecated") for s in skills):
        return CellState.COVERED
    return CellState.DRAFT_ONLY


def build_coverage_matrix(
    registry: SkillRegistry,
    domain_areas: list[str],
    task_types: list[str],
) -> CoverageMatrix:
    """Build the coverage grid from active skills with manual tags."""
    row_set = set(domain_areas)
    col_set = set(task_types)

    # Initialize all cells as empty
    cells: dict[tuple[str, str], CoverageCell] = {}
    for da in domain_areas:
        for tt in task_types:
            cells[(da, tt)] = CoverageCell(domain_area=da, task_type=tt)

    unmapped: list[Skill] = []

    for skill in registry.get_active_skills():
        if not skill.domain_areas or not skill.task_types:
            unmapped.append(skill)
            continue

        placed = False
        for da in skill.domain_areas:
            if da not in row_set:
                continue
            for tt in skill.task_types:
                if tt not in col_set:
                    continue
                cells[(da, tt)].skills.append(skill)
                placed = True

        if not placed:
            unmapped.append(skill)

    # Set cell states
    for cell in cells.values():
        cell.state = _determine_cell_state(cell.skills)

    return CoverageMatrix(
        rows=list(domain_areas),
        columns=list(task_types),
        cells=cells,
        unmapped_skills=unmapped,
    )


# ---------------------------------------------------------------------------
# History persistence
# ---------------------------------------------------------------------------

def load_coverage_history(data_dir: Path) -> CoverageHistory:
    """Load from data/coverage_history.json. Returns empty history if missing."""
    path = data_dir / "coverage_history.json"
    if not path.exists():
        return CoverageHistory()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load coverage history from %s: %s", path, exc)
        return CoverageHistory()

    if not isinstance(raw, list):
        logger.warning("Coverage history at %s is not a list, starting fresh", path)
        return CoverageHistory()

    entries = []
    for item in raw:
        try:
            entries.append(CoverageHistoryEntry(
                date=item["date"],
                score=float(item["score"]),
                total_cells=int(item["total_cells"]),
                covered_cells=int(item["covered_cells"]),
                draft_cells=int(item["draft_cells"]),
                empty_cells=int(item["empty_cells"]),
                total_skills=int(item["total_skills"]),
            ))
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping malformed history entry: %s", exc)
    return CoverageHistory(entries=entries)


def save_coverage_history(history: CoverageHistory, data_dir: Path) -> None:
    """Write to data/coverage_history.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "coverage_history.json"
    data = [
        {
            "date": e.date,
            "score": e.score,
            "total_cells": e.total_cells,
            "covered_cells": e.covered_cells,
            "draft_cells": e.draft_cells,
            "empty_cells": e.empty_cells,
            "total_skills": e.total_skills,
        }
        for e in history.entries
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_coverage_snapshot(
    matrix: CoverageMatrix,
    registry: SkillRegistry,
    data_dir: Path,
) -> Optional[float]:
    """Record current coverage score if changed. Returns delta or None."""
    history = load_coverage_history(data_dir)
    current_score = matrix.coverage_score
    delta = history.delta_since_last(current_score)
    recorded = history.record(matrix, registry.total_count)
    if recorded:
        save_coverage_history(history, data_dir)
        return delta
    return None
