import json
import shutil

import pytest
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
    Returns path to the temp skills dir containing all example skills in flat mode."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    if EXAMPLES_DIR.exists():
        for domain_dir in EXAMPLES_DIR.iterdir():
            if domain_dir.is_dir():
                for skill_file in domain_dir.glob("*.md"):
                    shutil.copy(skill_file, skills_dir / skill_file.name)
    return skills_dir


@pytest.fixture
def tiered_skills_dir(tmp_path):
    """Create a tiered directory with controlled override scenarios.

    Expected active skills: base_skill, overridden_skill (org), fully_overridden (user),
                            draft_skill, org_only, user_only = 6 active
    Total files: 9
    """
    skills_dir = tmp_path / "skills"
    for tier in ["default", "org", "user"]:
        (skills_dir / tier).mkdir(parents=True)

    def write_skill(tier, name, description, status="active"):
        content = (
            f"---\nname: {name}\ndescription: \"{description}\"\n"
            f"status: {status}\n---\n\n# {name}\n\n"
            f"## When to Use\nTest skill in {tier} tier.\n"
        )
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
    return '---\nname: test_skill\ndescription: "A test skill for unit testing."\n---\n\n# Test Skill\n\nBody content here.\n'


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
    """Query log with < 50 entries."""
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
    """Query log with 60+ entries for dead skill detection testing."""
    log_path = tmp_path / "query_log.json"
    loaded_skills = ["handle_refund", "classify_inquiry", "summarize_paper", "diagnose_outage"]
    entries = []

    for q in ["What's our SLA rate?", "Translate to Spanish", "Run the deploy pipeline"]:
        entries.append({"timestamp": "2026-03-01T10:00:00", "query": q,
                        "skill_loaded": None, "skill_candidates": []})

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
        import sentence_transformers  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        skip_analysis = pytest.mark.skip(reason="analysis dependencies not installed")
        for item in items:
            if "analysis" in item.keywords:
                item.add_marker(skip_analysis)
