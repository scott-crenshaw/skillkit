"""Tests for skillkit/coverage.py — TC-CV01 through TC-CV38."""

import json
import logging
from pathlib import Path

import pytest

from skillkit.coverage import (
    CellState,
    CoverageCell,
    CoverageHistory,
    CoverageHistoryEntry,
    CoverageMatrix,
    build_coverage_matrix,
    load_coverage_history,
    record_coverage_snapshot,
    save_coverage_history,
)
from skillkit.skill_parser import Skill, SkillRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill(
    name: str,
    domain_areas: list[str] | None = None,
    task_types: list[str] | None = None,
    status: str = "active",
) -> Skill:
    return Skill(
        name=name,
        description=f"Description for {name}",
        domain_areas=domain_areas or [],
        task_types=task_types or [],
        status=status,
    )


def _registry(skills: list[Skill]) -> SkillRegistry:
    return SkillRegistry(skills=skills, mode="flat")


# ===========================================================================
# Matrix Building (TC-CV01 – TC-CV16)
# ===========================================================================

# TC-CV01  Skills with both tags appear in correct cells
def test_cv01_basic_placement():
    s = _skill("s1", domain_areas=["A"], task_types=["X"])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    cell = m.get_cell("A", "X")
    assert cell is not None
    assert s in cell.skills
    assert cell.state == CellState.COVERED


# TC-CV02  Skill with 2 domain_areas and 3 task_types → 6 cells
def test_cv02_cartesian_product():
    s = _skill("multi", domain_areas=["A", "B"], task_types=["X", "Y", "Z"])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A", "B"], ["X", "Y", "Z"])

    cells_with_skill = [c for c in m.cells.values() if s in c.skills]
    assert len(cells_with_skill) == 6


# TC-CV03  Skill with domain_areas but empty task_types → unmapped
def test_cv03_missing_task_types():
    s = _skill("da_only", domain_areas=["A"], task_types=[])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert s in m.unmapped_skills
    assert m.get_cell("A", "X").state == CellState.EMPTY


# TC-CV04  Skill with task_types but empty domain_areas → unmapped
def test_cv04_missing_domain_areas():
    s = _skill("tt_only", domain_areas=[], task_types=["X"])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert s in m.unmapped_skills


# TC-CV05  Skill with neither → unmapped
def test_cv05_no_tags():
    s = _skill("no_tags")
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert s in m.unmapped_skills


# TC-CV06  domain_area not in config rows → silently ignored, other placements work
def test_cv06_unknown_domain_area():
    s = _skill("partial", domain_areas=["A", "Unknown"], task_types=["X"])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert s in m.get_cell("A", "X").skills
    assert ("Unknown", "X") not in m.cells


# TC-CV07  task_type not in config columns → silently ignored
def test_cv07_unknown_task_type():
    s = _skill("partial_tt", domain_areas=["A"], task_types=["X", "Unknown"])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert s in m.get_cell("A", "X").skills
    assert ("A", "Unknown") not in m.cells


# TC-CV08  Cell with active skills → COVERED
def test_cv08_active_covered():
    s = _skill("active_s", domain_areas=["A"], task_types=["X"], status="active")
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert m.get_cell("A", "X").state == CellState.COVERED


# TC-CV09  Cell with only draft skills → DRAFT_ONLY
def test_cv09_draft_only():
    s = _skill("draft_s", domain_areas=["A"], task_types=["X"], status="draft")
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert m.get_cell("A", "X").state == CellState.DRAFT_ONLY


# TC-CV10  Cell with no skills → EMPTY
def test_cv10_empty_cell():
    reg = _registry([])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert m.get_cell("A", "X").state == CellState.EMPTY


# TC-CV11  Mix of active and draft → COVERED
def test_cv11_active_plus_draft():
    s1 = _skill("a", domain_areas=["A"], task_types=["X"], status="active")
    s2 = _skill("d", domain_areas=["A"], task_types=["X"], status="draft")
    reg = _registry([s1, s2])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert m.get_cell("A", "X").state == CellState.COVERED


# TC-CV12  Only deprecated → COVERED
def test_cv12_deprecated_covered():
    s = _skill("dep", domain_areas=["A"], task_types=["X"], status="deprecated")
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert m.get_cell("A", "X").state == CellState.COVERED


# TC-CV13  Deprecated + draft → COVERED
def test_cv13_deprecated_plus_draft():
    s1 = _skill("dep", domain_areas=["A"], task_types=["X"], status="deprecated")
    s2 = _skill("dft", domain_areas=["A"], task_types=["X"], status="draft")
    reg = _registry([s1, s2])
    m = build_coverage_matrix(reg, ["A"], ["X"])

    assert m.get_cell("A", "X").state == CellState.COVERED


# TC-CV14  get_cell for existing combination
def test_cv14_get_cell_exists():
    reg = _registry([])
    m = build_coverage_matrix(reg, ["A"], ["X"])
    assert m.get_cell("A", "X") is not None


# TC-CV15  get_cell for non-existent combination
def test_cv15_get_cell_missing():
    reg = _registry([])
    m = build_coverage_matrix(reg, ["A"], ["X"])
    assert m.get_cell("Z", "Q") is None


# TC-CV16  empty_cells only returns EMPTY
def test_cv16_empty_cells_filter():
    s = _skill("s", domain_areas=["A"], task_types=["X"], status="active")
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A", "B"], ["X"])

    empties = m.empty_cells
    assert len(empties) == 1
    assert empties[0].domain_area == "B"
    assert empties[0].state == CellState.EMPTY


# ===========================================================================
# Coverage Score (TC-CV20 – TC-CV25)
# ===========================================================================

# TC-CV20  All cells covered → 100.0
def test_cv20_all_covered():
    s1 = _skill("s1", domain_areas=["A"], task_types=["X"])
    s2 = _skill("s2", domain_areas=["B"], task_types=["X"])
    reg = _registry([s1, s2])
    m = build_coverage_matrix(reg, ["A", "B"], ["X"])

    assert m.coverage_score == 100.0


# TC-CV21  No cells covered → 0.0
def test_cv21_none_covered():
    reg = _registry([])
    m = build_coverage_matrix(reg, ["A", "B"], ["X", "Y"])

    assert m.coverage_score == 0.0


# TC-CV22  Half covered → 50.0
def test_cv22_half_covered():
    s = _skill("s1", domain_areas=["A"], task_types=["X"])
    reg = _registry([s])
    m = build_coverage_matrix(reg, ["A", "B"], ["X"])

    assert m.coverage_score == 50.0


# TC-CV23  Mix of COVERED and DRAFT_ONLY → 100.0
def test_cv23_covered_plus_draft():
    s1 = _skill("a", domain_areas=["A"], task_types=["X"], status="active")
    s2 = _skill("d", domain_areas=["B"], task_types=["X"], status="draft")
    reg = _registry([s1, s2])
    m = build_coverage_matrix(reg, ["A", "B"], ["X"])

    assert m.coverage_score == 100.0


# TC-CV24  Empty matrix → 0.0, no ZeroDivisionError
def test_cv24_empty_matrix():
    reg = _registry([])
    m1 = build_coverage_matrix(reg, [], ["X"])
    m2 = build_coverage_matrix(reg, ["A"], [])
    m3 = build_coverage_matrix(reg, [], [])

    assert m1.coverage_score == 0.0
    assert m2.coverage_score == 0.0
    assert m3.coverage_score == 0.0


# TC-CV25  Deterministic
def test_cv25_deterministic():
    s = _skill("s1", domain_areas=["A"], task_types=["X"])
    reg = _registry([s])

    scores = set()
    for _ in range(5):
        m = build_coverage_matrix(reg, ["A", "B"], ["X"])
        scores.add(m.coverage_score)

    assert len(scores) == 1


# ===========================================================================
# Coverage History (TC-CV30 – TC-CV38)
# ===========================================================================

def _make_matrix(score_cells: int, empty_cells: int) -> CoverageMatrix:
    """Helper to build a matrix with a known number of covered/empty cells."""
    rows = [f"R{i}" for i in range(score_cells + empty_cells)]
    cols = ["C"]
    skills_list = []
    for i in range(score_cells):
        s = _skill(f"s{i}", domain_areas=[f"R{i}"], task_types=["C"])
        skills_list.append(s)
    reg = _registry(skills_list)
    return build_coverage_matrix(reg, rows, cols)


# TC-CV30  First entry
def test_cv30_first_entry():
    h = CoverageHistory()
    m = _make_matrix(2, 2)
    result = h.record(m, total_skills=2)

    assert result is True
    assert len(h.entries) == 1
    assert h.entries[0].score == 50.0
    assert h.entries[0].total_cells == 4
    assert h.entries[0].covered_cells == 2
    assert h.entries[0].empty_cells == 2
    assert h.entries[0].total_skills == 2

    # Delta on first entry is None
    assert h.delta_since_last(50.0) == 0.0  # after recording, delta from self


# TC-CV31  Score changed → new entry appended
def test_cv31_score_changed(monkeypatch):
    import skillkit.coverage as cov_mod

    h = CoverageHistory()
    m1 = _make_matrix(1, 3)
    h.record(m1, total_skills=1)

    # Monkeypatch date to next day
    import datetime
    monkeypatch.setattr(
        cov_mod, "date",
        type("FakeDate", (), {"today": staticmethod(lambda: datetime.date(2026, 3, 12)),
                               "isoformat": datetime.date.isoformat})
    )
    # Actually need a proper fake
    class FakeDate:
        @staticmethod
        def today():
            return datetime.date(2026, 3, 12)

    monkeypatch.setattr(cov_mod, "date", FakeDate)

    m2 = _make_matrix(3, 1)
    result = h.record(m2, total_skills=3)

    assert result is True
    assert len(h.entries) == 2
    assert h.entries[1].score == 75.0


# TC-CV32  Score unchanged → no new entry
def test_cv32_score_unchanged():
    h = CoverageHistory()
    m = _make_matrix(2, 2)
    h.record(m, total_skills=2)

    m2 = _make_matrix(2, 2)
    result = h.record(m2, total_skills=2)

    assert result is False
    assert len(h.entries) == 1


# TC-CV33  Same day → replaces
def test_cv33_same_day_replaces():
    h = CoverageHistory()
    m1 = _make_matrix(1, 3)
    h.record(m1, total_skills=1)

    m2 = _make_matrix(3, 1)
    result = h.record(m2, total_skills=3)

    # Same day, different score: should replace
    assert result is True
    assert len(h.entries) == 1
    assert h.entries[0].score == 75.0


# TC-CV34  delta_since_last
def test_cv34_delta():
    h = CoverageHistory(entries=[
        CoverageHistoryEntry("2026-03-01", 50.0, 4, 2, 0, 2, 2),
        CoverageHistoryEntry("2026-03-02", 75.0, 4, 3, 0, 1, 3),
    ])

    assert h.delta_since_last(75.0) == 0.0
    assert h.delta_since_last(100.0) == 25.0
    assert h.delta_since_last(50.0) == -25.0


# TC-CV35  Load from valid JSON
def test_cv35_load_valid(tmp_data_dir):
    data = [
        {"date": "2026-03-01", "score": 50.0, "total_cells": 4,
         "covered_cells": 2, "draft_cells": 0, "empty_cells": 2, "total_skills": 2},
    ]
    (tmp_data_dir / "coverage_history.json").write_text(json.dumps(data))

    h = load_coverage_history(tmp_data_dir)

    assert len(h.entries) == 1
    assert h.entries[0].score == 50.0
    assert h.entries[0].date == "2026-03-01"


# TC-CV36  Missing file → empty history
def test_cv36_missing_file(tmp_data_dir):
    (tmp_data_dir / "coverage_history.json").unlink(missing_ok=True)
    h = load_coverage_history(tmp_data_dir)

    assert len(h.entries) == 0


# TC-CV37  Malformed JSON → empty history, warning
def test_cv37_malformed_json(tmp_data_dir, caplog):
    (tmp_data_dir / "coverage_history.json").write_text("not valid json{{{")

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        h = load_coverage_history(tmp_data_dir)

    assert len(h.entries) == 0
    assert "coverage history" in caplog.text.lower() or "could not load" in caplog.text.lower()


# TC-CV38  Save and reload round-trip
def test_cv38_round_trip(tmp_data_dir):
    h = CoverageHistory(entries=[
        CoverageHistoryEntry("2026-03-01", 50.0, 4, 2, 0, 2, 5),
        CoverageHistoryEntry("2026-03-02", 75.0, 4, 3, 0, 1, 8),
    ])

    save_coverage_history(h, tmp_data_dir)
    h2 = load_coverage_history(tmp_data_dir)

    assert len(h2.entries) == 2
    for orig, loaded in zip(h.entries, h2.entries):
        assert orig.date == loaded.date
        assert orig.score == loaded.score
        assert orig.total_cells == loaded.total_cells
        assert orig.covered_cells == loaded.covered_cells
        assert orig.draft_cells == loaded.draft_cells
        assert orig.empty_cells == loaded.empty_cells
        assert orig.total_skills == loaded.total_skills
