"""Integration tests — TC-INT01 through TC-INT41."""

import json
import shutil

import pytest
from pathlib import Path

from skillkit.config import load_config, load_coverage_config
from skillkit.coverage import build_coverage_matrix, CellState
from skillkit.gap_analysis import (
    build_gap_report,
    load_manual_queries,
    save_manual_queries,
    load_query_log,
)
from skillkit.skill_parser import load_registry, parse_skill_file
from skillkit.stub_generator import generate_name_from_coverage, generate_stub, write_stub


EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# ===========================================================================
# First-Run Scenarios (TC-INT01 – TC-INT03)
# ===========================================================================

# TC-INT01
def test_int01_fresh_empty_dir(tmp_path):
    """Fresh empty directory → full bootstrap with example skills."""
    config_path = tmp_path / "skillkit.yaml"

    # No files exist
    assert not config_path.exists()
    assert not (tmp_path / "skills").exists()

    config = load_config(config_path)

    # skillkit.yaml created
    assert config_path.exists()

    # skills/ directory created with example skills
    assert config.skills_dir.exists()
    skill_files = list(config.skills_dir.glob("*.md"))
    assert len(skill_files) > 0, "Example skills should be copied"

    # Registry loads successfully
    registry = load_registry(config)
    assert registry.total_count > 0

    # Coverage matrix works
    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )
    matrix = build_coverage_matrix(registry, domain_areas, task_types)
    assert len(matrix.rows) > 0 or len(matrix.columns) > 0


# TC-INT02
def test_int02_existing_skills_no_config(tmp_path):
    """Directory with existing skills, no config files → auto-generates."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Copy example skills (flat)
    for domain_dir in EXAMPLES_DIR.iterdir():
        if domain_dir.is_dir():
            for skill_file in domain_dir.glob("*.md"):
                shutil.copy(skill_file, skills_dir / skill_file.name)

    skill_count = len(list(skills_dir.glob("*.md")))
    assert skill_count > 0

    config_path = tmp_path / "skillkit.yaml"
    assert not config_path.exists()

    config = load_config(config_path)

    # skillkit.yaml auto-created
    assert config_path.exists()

    # Registry picks up existing skills
    registry = load_registry(config)
    assert registry.total_count == skill_count

    # coverage_config.yaml auto-generated
    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )
    assert config.coverage_config_path.exists()
    # domain_areas should match skill domains
    skill_domains = sorted({s.domain for s in registry.get_active_skills()})
    assert domain_areas == skill_domains


# TC-INT03
def test_int03_tiered_auto_detection(tiered_skills_dir, tmp_path):
    """Tiered directory auto-detection and override resolution."""
    config_path = tmp_path / "skillkit.yaml"
    # Write config pointing to tiered dir
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(tiered_skills_dir)},
        default_flow_style=False,
    ))

    config = load_config(config_path)
    registry = load_registry(config)

    assert registry.mode == "tiered"
    assert len(registry.get_active_skills()) == 6

    # Override resolution
    fully = registry.get_by_name("fully_overridden")
    assert fully is not None
    assert fully.tier == "user"

    overridden = registry.get_by_name("overridden_skill")
    assert overridden is not None
    assert overridden.tier == "org"


# ===========================================================================
# Coverage → Stub Cycle (TC-INT10 – TC-INT11)
# ===========================================================================

# TC-INT10
def test_int10_gap_stub_cycle(example_skills_dir, tmp_path):
    """Find gap → create stub → verify gap filled."""
    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))

    config = load_config(config_path)
    registry = load_registry(config)

    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )
    matrix = build_coverage_matrix(registry, domain_areas, task_types)

    empty_before = len(matrix.empty_cells)
    assert empty_before > 0, "Need at least one gap for this test"
    score_before = matrix.coverage_score

    # Pick first empty cell
    gap = matrix.empty_cells[0]
    da, tt = gap.domain_area, gap.task_type

    # Create stub
    name = generate_name_from_coverage(tt, da)
    content = generate_stub(
        name=name,
        description=f"Stub for {tt} in {da}",
        domain="general",
        domain_areas=[da],
        task_types=[tt],
    )
    write_stub(content, name, config.skills_dir, registry.mode)

    # Reload
    registry2 = load_registry(config)
    new_skill = registry2.get_by_name(name)
    assert new_skill is not None
    assert new_skill.status == "draft"

    # Rebuild matrix
    matrix2 = build_coverage_matrix(registry2, domain_areas, task_types)
    empty_after = len(matrix2.empty_cells)
    assert empty_after == empty_before - 1

    cell = matrix2.get_cell(da, tt)
    assert cell is not None
    assert cell.state == CellState.DRAFT_ONLY

    assert matrix2.coverage_score >= score_before


# TC-INT11
def test_int11_stub_collision(example_skills_dir, tmp_path):
    """Stub collision: create same stub twice."""
    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry = load_registry(config)

    content = generate_stub(name="analyze_research", description="Test stub")
    path = write_stub(content, "analyze_research", config.skills_dir, registry.mode)
    original = path.read_text(encoding="utf-8")

    content2 = generate_stub(name="analyze_research", description="Duplicate")
    with pytest.raises(FileExistsError):
        write_stub(content2, "analyze_research", config.skills_dir, registry.mode)

    # Original unchanged
    assert path.read_text(encoding="utf-8") == original


# ===========================================================================
# Gap Analysis End-to-End (TC-INT20 – TC-INT21)
# ===========================================================================

# TC-INT20
def test_int20_manual_queries_in_report(example_skills_dir, tmp_path):
    """Manual query entry persists and appears in gap report."""
    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry = load_registry(config)

    # Save manual queries
    save_manual_queries(
        ["Deploy to staging", "Run CI pipeline"], config.data_dir
    )

    # Build gap report (no query log)
    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )
    matrix = build_coverage_matrix(registry, domain_areas, task_types)
    report = build_gap_report(registry, matrix, config)

    assert report.has_manual_queries is True
    assert report.unmatched_query_count == 2
    assert report.has_query_log is False
    assert len(report.coverage_gaps) >= 0  # may or may not have gaps


# TC-INT21
def test_int21_full_report_with_log(example_skills_dir, large_query_log, tmp_path):
    """Full gap report with large query log."""
    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir), "query_log": str(large_query_log)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry = load_registry(config)

    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )
    matrix = build_coverage_matrix(registry, domain_areas, task_types)
    report = build_gap_report(registry, matrix, config)

    assert report.has_query_log is True
    # 3 unmatched in the large_query_log fixture
    assert report.unmatched_query_count == 3
    # Dead skills: skills in example set not in the loaded set
    # loaded_skills = handle_refund, classify_inquiry, summarize_paper, diagnose_outage
    # example skills include others like escalate_ticket, analyze_logs, etc.
    assert len(report.dead_skills) > 0
    # Coverage gaps from matrix
    assert len(report.coverage_gaps) >= 0


# ===========================================================================
# Overlap Detection End-to-End (TC-INT30 – TC-INT31)
# ===========================================================================

# TC-INT30
@pytest.mark.analysis
def test_int30_cold_warm_cache(example_skills_dir, tmp_path):
    """Full overlap pipeline: cold cache → warm cache."""
    from skillkit.overlap import build_overlap_report

    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry = load_registry(config)

    # Cold cache
    cache_path = config.data_dir / "embedding_cache.json"
    assert not cache_path.exists() or json.loads(cache_path.read_text()).get("entries", {}) == {}

    report1 = build_overlap_report(registry, config)
    assert cache_path.exists()
    cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(cache_data.get("entries", {})) > 0

    # At least 1 pair flagged
    assert len(report1.pairs) >= 1

    # Warm cache
    report2 = build_overlap_report(registry, config)
    assert len(report2.pairs) >= 1

    # Same results
    pairs1 = {(p.skill_a.name, p.skill_b.name, round(p.similarity, 4)) for p in report1.pairs}
    pairs2 = {(p.skill_a.name, p.skill_b.name, round(p.similarity, 4)) for p in report2.pairs}
    assert pairs1 == pairs2


# TC-INT31
@pytest.mark.analysis
def test_int31_query_simulator(example_skills_dir, tmp_path):
    """Query simulator against example skills."""
    from skillkit.overlap import simulate_query

    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry = load_registry(config)

    # Query 1: customer support
    result1 = simulate_query("customer wants their money back", registry, config)
    assert len(result1.ranked_skills) > 0
    top3_names_1 = [s.skill.name for s in result1.ranked_skills[:3]]
    top3_domains_1 = [s.skill.domain for s in result1.ranked_skills[:3]]
    assert "customer_support" in top3_domains_1

    # Query 2: devops
    result2 = simulate_query("analyze the server logs from last night", registry, config)
    assert len(result2.ranked_skills) > 0
    top3_domains_2 = [s.skill.domain for s in result2.ranked_skills[:3]]
    assert "devops" in top3_domains_2


# ===========================================================================
# Registry Reflects Filesystem Changes (TC-INT40 – TC-INT41)
# ===========================================================================

# TC-INT40
def test_int40_add_skill_reload(example_skills_dir, tmp_path):
    """Add a skill file → reload → new skill visible."""
    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry1 = load_registry(config)
    count_before = registry1.total_count

    # Write a new skill file
    new_skill = (
        '---\nname: brand_new_skill\ndescription: "A brand new skill"\n'
        'status: active\ndomain: testing\n---\n\n# Brand New\n\nBody.\n'
    )
    (example_skills_dir / "brand_new_skill.md").write_text(new_skill)

    registry2 = load_registry(config)
    assert registry2.total_count == count_before + 1
    assert registry2.get_by_name("brand_new_skill") is not None


# TC-INT41
def test_int41_modify_skill_reload(example_skills_dir, tmp_path):
    """Modify skill frontmatter → reload → change reflected."""
    config_path = tmp_path / "skillkit.yaml"
    import yaml
    config_path.write_text(yaml.dump(
        {"skills_dir": str(example_skills_dir)},
        default_flow_style=False,
    ))
    config = load_config(config_path)
    registry1 = load_registry(config)

    # Find a research skill
    research_skills = registry1.get_by_domain("research")
    assert len(research_skills) > 0
    target = research_skills[0]
    target_name = target.name

    # Read and modify the file
    file_path = target.file_path
    original = file_path.read_text(encoding="utf-8")
    modified = original.replace("domain: research", "domain: modified_domain")
    file_path.write_text(modified, encoding="utf-8")

    # Reload
    registry2 = load_registry(config)
    skill = registry2.get_by_name(target_name)
    assert skill is not None
    assert skill.domain == "modified_domain"
    assert skill in registry2.get_by_domain("modified_domain")
    assert skill not in registry2.get_by_domain("research")
