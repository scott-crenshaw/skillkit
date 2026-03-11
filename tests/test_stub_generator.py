"""Tests for skillkit/stub_generator.py — TC-SG01 through TC-SG25."""

import yaml
import pytest
from pathlib import Path

from skillkit.stub_generator import generate_stub, write_stub, generate_name_from_coverage
from skillkit.skill_parser import parse_skill_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> dict:
    """Extract and parse YAML frontmatter from stub content."""
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Content should have --- delimiters"
    return yaml.safe_load(parts[1])


# ===========================================================================
# Template Generation (TC-SG01 – TC-SG05)
# ===========================================================================

# TC-SG01  Generate stub with name, description, domain
def test_sg01_basic_stub():
    content = generate_stub(
        name="test_skill",
        description="A test skill",
        domain="testing",
    )

    assert content.startswith("---")
    fm = _parse_frontmatter(content)
    assert fm["name"] == "test_skill"
    assert fm["description"] == "A test skill"
    assert fm["domain"] == "testing"
    assert fm["status"] == "draft"

    assert "## When to Use" in content
    assert "## Steps" in content
    assert "## Output Format" in content
    assert "## Common Pitfalls" in content
    assert "TODO" in content


# TC-SG02  Generate stub with domain_areas and task_types
def test_sg02_with_coverage_tags():
    content = generate_stub(
        name="tagged_skill",
        description="A tagged skill",
        domain_areas=["Research", "Analysis"],
        task_types=["Summarize", "Compare"],
    )

    fm = _parse_frontmatter(content)
    assert fm["domain_areas"] == ["Research", "Analysis"]
    assert fm["task_types"] == ["Summarize", "Compare"]


# TC-SG03  Minimal input (name only, empty description)
def test_sg03_minimal():
    content = generate_stub(name="minimal_skill")

    fm = _parse_frontmatter(content)
    assert fm["name"] == "minimal_skill"
    assert "TODO" in fm["description"]
    assert fm["domain"] == "general"

    # Should still be parseable
    assert content.startswith("---")
    assert "---" in content[3:]


# TC-SG04  CRITICAL: Round-trip generate → write → parse
def test_sg04_round_trip(tmp_skills_dir):
    content = generate_stub(
        name="round_trip",
        description="Round trip test skill",
        domain="testing",
        domain_areas=["Testing", "QA"],
        task_types=["Analyze", "Classify"],
    )

    path = tmp_skills_dir / "round_trip.md"
    path.write_text(content, encoding="utf-8")

    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "round_trip"
    assert skill.description == "Round trip test skill"
    assert skill.domain == "testing"
    assert skill.status == "draft"
    assert skill.domain_areas == ["Testing", "QA"]
    assert skill.task_types == ["Analyze", "Classify"]
    assert skill.word_count > 0
    assert "## When to Use" in content


# TC-SG05  All optional fields
def test_sg05_all_fields():
    content = generate_stub(
        name="full_stub",
        description="Full stub with all fields",
        domain="full_domain",
        domain_areas=["Area1"],
        task_types=["Type1"],
    )

    fm = _parse_frontmatter(content)
    assert fm["name"] == "full_stub"
    assert fm["description"] == "Full stub with all fields"
    assert fm["domain"] == "full_domain"
    assert fm["status"] == "draft"
    assert fm["domain_areas"] == ["Area1"]
    assert fm["task_types"] == ["Type1"]


# ===========================================================================
# Name Generation (TC-SG10 – TC-SG15)
# ===========================================================================

# TC-SG10
def test_sg10_basic_name():
    assert generate_name_from_coverage("Analyze", "Data Analysis") == "analyze_data_analysis"


# TC-SG11
def test_sg11_ampersand():
    assert generate_name_from_coverage("Debug", "Code & Development") == "debug_code_and_development"


# TC-SG12
def test_sg12_simple():
    assert generate_name_from_coverage("Summarize", "Research") == "summarize_research"


# TC-SG13  Multiple consecutive spaces → single underscore
def test_sg13_multiple_spaces():
    result = generate_name_from_coverage("Analyze", "Data   Analysis")
    assert "__" not in result
    assert result == "analyze_data_analysis"


# TC-SG14  Leading/trailing whitespace → trimmed
def test_sg14_whitespace():
    result = generate_name_from_coverage("  Analyze  ", "  Research  ")
    assert result == "analyze_research"


# TC-SG15  Unsafe filename characters removed
def test_sg15_unsafe_chars():
    result = generate_name_from_coverage("Analyze", "Data/Analysis:v2")
    assert "/" not in result
    assert ":" not in result
    # Should still be a reasonable name
    assert result.isidentifier() or result.replace("_", "").isalnum()


# ===========================================================================
# File Writing (TC-SG20 – TC-SG25)
# ===========================================================================

# TC-SG20  Write in flat mode
def test_sg20_flat_mode(tmp_skills_dir):
    content = generate_stub(name="flat_skill", description="Flat mode test")
    path = write_stub(content, "flat_skill", tmp_skills_dir, "flat")

    assert path == tmp_skills_dir / "flat_skill.md"
    assert path.exists()
    assert path.read_text(encoding="utf-8") == content


# TC-SG21  Write in tiered mode
def test_sg21_tiered_mode(tmp_skills_dir):
    content = generate_stub(name="tiered_skill", description="Tiered mode test")
    path = write_stub(content, "tiered_skill", tmp_skills_dir, "tiered")

    assert path == tmp_skills_dir / "default" / "tiered_skill.md"
    assert path.exists()


# TC-SG22  Collision detection
def test_sg22_collision(tmp_skills_dir):
    content = generate_stub(name="existing_skill", description="First version")
    write_stub(content, "existing_skill", tmp_skills_dir, "flat")

    original_content = (tmp_skills_dir / "existing_skill.md").read_text()

    content2 = generate_stub(name="existing_skill", description="Second version")
    with pytest.raises(FileExistsError):
        write_stub(content2, "existing_skill", tmp_skills_dir, "flat")

    # Original unchanged
    assert (tmp_skills_dir / "existing_skill.md").read_text() == original_content


# TC-SG23  Tiered mode auto-creates default/ dir
def test_sg23_auto_create_default(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    # default/ does NOT exist yet
    assert not (skills_dir / "default").exists()

    content = generate_stub(name="auto_dir_skill", description="Test")
    path = write_stub(content, "auto_dir_skill", skills_dir, "tiered")

    assert (skills_dir / "default").is_dir()
    assert path.exists()


# TC-SG24  Written stub is parseable
def test_sg24_parseable(tmp_skills_dir):
    content = generate_stub(
        name="parseable_stub",
        description="This stub should parse",
        domain="testing",
        domain_areas=["QA"],
        task_types=["Analyze"],
    )
    path = write_stub(content, "parseable_stub", tmp_skills_dir, "flat")

    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "parseable_stub"
    assert skill.status == "draft"
    assert skill.domain_areas == ["QA"]
    assert skill.task_types == ["Analyze"]


# TC-SG25  write_stub returns correct Path
def test_sg25_return_path(tmp_skills_dir):
    content = generate_stub(name="path_check", description="Check path")

    # Flat
    path_flat = write_stub(content, "path_check", tmp_skills_dir, "flat")
    assert path_flat.exists()
    assert path_flat == tmp_skills_dir / "path_check.md"
