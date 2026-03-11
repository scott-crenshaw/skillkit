"""Tests for skillkit/skill_parser.py — TC-SP01 through TC-SP59."""

import logging

import pytest
from pathlib import Path

from skillkit.skill_parser import (
    Skill,
    SkillRegistry,
    parse_skill_file,
    load_registry,
    _detect_mode,
    _extract_when_to_use,
)
from skillkit.config import SkillKitConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_skill(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _make_config(skills_dir: Path, tmp_path: Path) -> SkillKitConfig:
    return SkillKitConfig(
        skills_dir=skills_dir,
        coverage_config_path=tmp_path / "coverage_config.yaml",
        query_log_path=None,
        data_dir=tmp_path / "data",
        embedding_model="all-MiniLM-L6-v2",
        overlap_high=0.85,
        overlap_moderate=0.70,
        cluster_threshold=0.75,
    )


# ===========================================================================
# Frontmatter Parsing (TC-SP01 – TC-SP19)
# ===========================================================================

# TC-SP01  Parse minimal skill
def test_sp01_minimal(tmp_skills_dir, minimal_skill_content):
    path = _write_skill(tmp_skills_dir / "test.md", minimal_skill_content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "test_skill"
    assert skill.description == "A test skill for unit testing."
    assert skill.domain == "general"
    assert skill.status == "active"
    assert skill.output_format == "text"
    assert skill.domain_areas == []
    assert skill.task_types == []
    assert skill.tags == []
    assert skill.word_count > 0
    assert skill.body != ""


# TC-SP02  Parse skill with all fields
def test_sp02_full(tmp_skills_dir, full_skill_content):
    path = _write_skill(tmp_skills_dir / "full.md", full_skill_content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "full_test_skill"
    assert skill.description == "A fully populated test skill."
    assert skill.output_format == "structured_report"
    assert skill.domain == "testing"
    assert skill.status == "active"
    assert skill.domain_areas == ["Testing", "Quality"]
    assert skill.task_types == ["Analyze", "Classify"]
    assert skill.version == "1.0"
    assert skill.author == "test_author"
    assert skill.tags == ["unit-test", "fixture"]


# TC-SP03  Missing 'name'
def test_sp03_missing_name(tmp_skills_dir, caplog):
    content = '---\ndescription: "Has no name"\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "no_name.md", content)

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        result = parse_skill_file(path)

    assert result is None
    assert str(path) in caplog.text


# TC-SP04  Missing 'description'
def test_sp04_missing_description(tmp_skills_dir, caplog):
    content = '---\nname: orphan\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "no_desc.md", content)

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        result = parse_skill_file(path)

    assert result is None
    assert str(path) in caplog.text


# TC-SP05  Empty string name
def test_sp05_empty_name(tmp_skills_dir):
    content = '---\nname: ""\ndescription: "Has empty name"\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "empty_name.md", content)
    assert parse_skill_file(path) is None


# TC-SP06  Empty string description
def test_sp06_empty_description(tmp_skills_dir):
    content = '---\nname: valid_name\ndescription: ""\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "empty_desc.md", content)
    assert parse_skill_file(path) is None


# TC-SP07  Malformed YAML: unclosed quote
def test_sp07_malformed_quote(tmp_skills_dir, caplog):
    content = '---\nname: "unclosed\ndescription: "test"\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "bad_yaml.md", content)

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        result = parse_skill_file(path)

    assert result is None


# TC-SP08  Malformed YAML: tab indentation
def test_sp08_tab_indent(tmp_skills_dir, caplog):
    content = '---\nname: tabbed\n\tdescription: "tabs"\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "tabbed.md", content)

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        result = parse_skill_file(path)

    assert result is None


# TC-SP09  Empty file
def test_sp09_empty_file(tmp_skills_dir):
    path = _write_skill(tmp_skills_dir / "empty.md", "")
    assert parse_skill_file(path) is None


# TC-SP10  Only frontmatter, no body
def test_sp10_no_body(tmp_skills_dir):
    content = '---\nname: x\ndescription: "y"\n---\n'
    path = _write_skill(tmp_skills_dir / "no_body.md", content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.body == ""
    assert skill.word_count == 0


# TC-SP11  No frontmatter delimiters
def test_sp11_no_delimiters(tmp_skills_dir):
    content = "# Just Markdown\n\nNo frontmatter here.\n"
    path = _write_skill(tmp_skills_dir / "no_fm.md", content)
    assert parse_skill_file(path) is None


# TC-SP12  Single --- delimiter
def test_sp12_single_delimiter(tmp_skills_dir):
    content = "---\nname: incomplete\n"
    path = _write_skill(tmp_skills_dir / "one_delim.md", content)
    assert parse_skill_file(path) is None


# TC-SP13  Extra/unknown fields → silently ignored
def test_sp13_extra_fields(tmp_skills_dir):
    content = '---\nname: extra\ndescription: "Has extra"\npriority: high\ncustom_field: 42\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "extra.md", content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "extra"


# TC-SP14  Unknown status value
def test_sp14_unknown_status(tmp_skills_dir, caplog):
    content = '---\nname: beta_skill\ndescription: "Beta status"\nstatus: beta\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "beta.md", content)

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        skill = parse_skill_file(path)

    assert skill is not None
    assert skill.status == "active"
    assert "beta" in caplog.text


# TC-SP15  domain_areas as scalar string → coerced to list
def test_sp15_scalar_domain_areas(tmp_skills_dir):
    content = '---\nname: scalar_da\ndescription: "Scalar domain_areas"\ndomain_areas: Testing\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "scalar_da.md", content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.domain_areas == ["Testing"]


# TC-SP16  tags as scalar string → coerced to list
def test_sp16_scalar_tags(tmp_skills_dir):
    content = '---\nname: scalar_tag\ndescription: "Scalar tags"\ntags: single-tag\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "scalar_tag.md", content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.tags == ["single-tag"]


# TC-SP17  UTF-8 characters
def test_sp17_utf8(tmp_skills_dir):
    content = '---\nname: "análisis_datos"\ndescription: "Análisis de données"\n---\n\nContenu ici.\n'
    path = _write_skill(tmp_skills_dir / "utf8.md", content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "análisis_datos"
    assert "données" in skill.description


# TC-SP18  Windows line endings
def test_sp18_crlf(tmp_skills_dir):
    content = '---\r\nname: crlf_skill\r\ndescription: "Windows endings"\r\n---\r\n\r\n# CRLF Body\r\n\r\nContent here.\r\n'
    path = tmp_skills_dir / "crlf.md"
    path.write_bytes(content.encode("utf-8"))
    skill = parse_skill_file(path)

    assert skill is not None
    assert "\r" not in skill.body
    assert skill.name == "crlf_skill"


# TC-SP19  Trailing whitespace in values
def test_sp19_trailing_whitespace(tmp_skills_dir):
    content = '---\nname: "  spaced  "\ndescription: "  desc with spaces  "\n---\n\nBody.\n'
    path = _write_skill(tmp_skills_dir / "spaced.md", content)
    skill = parse_skill_file(path)

    assert skill is not None
    assert skill.name == "spaced"
    assert skill.description == "desc with spaces"


# ===========================================================================
# When to Use Extraction (TC-SP20 – TC-SP26)
# ===========================================================================

# TC-SP20  When to Use followed by another section
def test_sp20_when_to_use_middle():
    body = "# Title\n\n## When to Use\nUse this for testing.\n\n## Steps\n1. Do stuff\n"
    result = _extract_when_to_use(body)

    assert result == "Use this for testing."
    assert "## When to Use" not in result
    assert "## Steps" not in result


# TC-SP21  When to Use as last section
def test_sp21_when_to_use_last():
    body = "# Title\n\n## Steps\n1. Do stuff\n\n## When to Use\nUse this at the end.\n"
    result = _extract_when_to_use(body)

    assert result == "Use this at the end."


# TC-SP22  No When to Use section
def test_sp22_no_when_to_use():
    body = "# Title\n\n## Steps\n1. Do stuff\n"
    assert _extract_when_to_use(body) == ""


# TC-SP23  Lowercase "when to use"
def test_sp23_lowercase():
    body = "## When to use\nLowercase heading.\n\n## Next\n"
    assert _extract_when_to_use(body) == "Lowercase heading."


# TC-SP24  Title case "When To Use"
def test_sp24_title_case():
    body = "## When To Use\nTitle case heading.\n\n## Next\n"
    assert _extract_when_to_use(body) == "Title case heading."


# TC-SP25  h3 heading (###) → NOT matched
def test_sp25_h3_not_matched():
    body = "### When to Use\nThis is h3.\n\n## Next\n"
    assert _extract_when_to_use(body) == ""


# TC-SP26  Multiple When to Use sections → first extracted
def test_sp26_multiple():
    body = "## When to Use\nFirst one.\n\n## Other\nStuff.\n\n## When to Use\nSecond one.\n"
    result = _extract_when_to_use(body)
    assert result == "First one."


# ===========================================================================
# Directory Detection and Registry Loading (TC-SP30 – TC-SP37)
# ===========================================================================

# TC-SP30  Flat directory with .md files at root
def test_sp30_flat_root(tmp_skills_dir, minimal_skill_content, tmp_path):
    _write_skill(tmp_skills_dir / "skill1.md", minimal_skill_content)
    cfg = _make_config(tmp_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.mode == "flat"
    assert reg.total_count == 1


# TC-SP31  Flat directory with non-tier subdirectories
def test_sp31_flat_subdirs(tmp_skills_dir, tmp_path):
    (tmp_skills_dir / "customer_support").mkdir()
    (tmp_skills_dir / "devops").mkdir()
    content1 = '---\nname: cs_skill\ndescription: "CS"\n---\n\nBody.\n'
    content2 = '---\nname: dev_skill\ndescription: "Dev"\n---\n\nBody.\n'
    _write_skill(tmp_skills_dir / "customer_support" / "cs.md", content1)
    _write_skill(tmp_skills_dir / "devops" / "dev.md", content2)

    cfg = _make_config(tmp_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.mode == "flat"
    assert reg.total_count == 2


# TC-SP32  Tiered directory
def test_sp32_tiered(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.mode == "tiered"
    for s in reg.skills:
        assert s.tier in ("default", "org", "user")


# TC-SP33  Only default/ subdir
def test_sp33_only_default(tmp_path):
    skills_dir = tmp_path / "skills"
    (skills_dir / "default").mkdir(parents=True)
    content = '---\nname: def_skill\ndescription: "Default only"\n---\n\nBody.\n'
    _write_skill(skills_dir / "default" / "def.md", content)

    cfg = _make_config(skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.mode == "tiered"
    assert reg.total_count == 1
    assert reg.skills[0].tier == "default"


# TC-SP34  Empty skills directory
def test_sp34_empty(tmp_skills_dir, tmp_path):
    cfg = _make_config(tmp_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.mode == "flat"
    assert reg.total_count == 0


# TC-SP35  Non-.md files ignored
def test_sp35_non_md_ignored(tmp_skills_dir, minimal_skill_content, tmp_path):
    _write_skill(tmp_skills_dir / "skill.md", minimal_skill_content)
    _write_skill(tmp_skills_dir / "readme.txt", "Not a skill")
    _write_skill(tmp_skills_dir / "config.yaml", "key: value")
    _write_skill(tmp_skills_dir / "script.py", "print('hi')")

    cfg = _make_config(tmp_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.total_count == 1


# TC-SP36  Mix of valid and invalid .md files
def test_sp36_mixed_valid_invalid(tmp_skills_dir, minimal_skill_content, tmp_path):
    _write_skill(tmp_skills_dir / "good.md", minimal_skill_content)
    _write_skill(tmp_skills_dir / "bad.md", "No frontmatter here")
    _write_skill(tmp_skills_dir / "also_bad.md", "---\nbadyaml:\n\t[broken\n---\n")

    valid_content2 = '---\nname: second\ndescription: "Second skill"\n---\n\nBody.\n'
    _write_skill(tmp_skills_dir / "good2.md", valid_content2)

    cfg = _make_config(tmp_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.total_count == 2


# TC-SP37  Load all 12 example skills (skip if examples dir missing)
def test_sp37_example_skills(example_skills_dir, tmp_path):
    # Skip if example skills don't exist yet
    md_files = list(example_skills_dir.glob("*.md"))
    if not md_files:
        pytest.skip("Example skills not yet created")

    cfg = _make_config(example_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.total_count == 12
    domains = reg.get_all_domains()
    assert len(domains) >= 3
    assert reg.draft_count >= 1
    assert reg.deprecated_count >= 1
    for s in reg.skills:
        assert s.body != ""
        assert s.word_count > 0


# ===========================================================================
# Override Resolution — Tiered Mode (TC-SP40 – TC-SP46)
# ===========================================================================

# TC-SP40  Skill only in default tier
def test_sp40_default_only(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    base = reg.get_by_name("base_skill")
    assert base is not None
    assert base.is_active is True
    assert base.tier == "default"
    assert base.shadows == []


# TC-SP41  Same name in default and org
def test_sp41_org_overrides_default(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    active = reg.get_by_name("overridden_skill")
    assert active is not None
    assert active.tier == "org"
    assert "default" in active.shadows

    # Default version should be inactive
    defaults = [s for s in reg.skills if s.name == "overridden_skill" and s.tier == "default"]
    assert len(defaults) == 1
    assert defaults[0].is_active is False


# TC-SP42  Same name in all three tiers
def test_sp42_user_overrides_all(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    active = reg.get_by_name("fully_overridden")
    assert active is not None
    assert active.tier == "user"
    assert "org" in active.shadows
    assert "default" in active.shadows

    # Org and default versions inactive
    inactive = [s for s in reg.skills if s.name == "fully_overridden" and not s.is_active]
    assert len(inactive) == 2


# TC-SP43  Same name in default and user (skip org)
def test_sp43_user_overrides_default(tmp_path):
    skills_dir = tmp_path / "skills"
    for tier in ["default", "org", "user"]:
        (skills_dir / tier).mkdir(parents=True)

    content_d = '---\nname: skip_org\ndescription: "Default version"\n---\n\nBody.\n'
    content_u = '---\nname: skip_org\ndescription: "User version"\n---\n\nBody.\n'
    _write_skill(skills_dir / "default" / "skip_org.md", content_d)
    _write_skill(skills_dir / "user" / "skip_org.md", content_u)

    cfg = _make_config(skills_dir, tmp_path)
    reg = load_registry(cfg)

    active = reg.get_by_name("skip_org")
    assert active is not None
    assert active.tier == "user"
    assert "default" in active.shadows


# TC-SP44  Different skills in different tiers
def test_sp44_no_collisions(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.get_by_name("base_skill") is not None
    assert reg.get_by_name("org_only") is not None
    assert reg.get_by_name("user_only") is not None
    # All three have is_active True
    for name in ("base_skill", "org_only", "user_only"):
        s = reg.get_by_name(name)
        assert s.is_active is True


# TC-SP45  get_active_skills() count in tiered mode
def test_sp45_active_count(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    active = reg.get_active_skills()
    assert len(active) == 6

    active_names = {s.name for s in active}
    expected = {"base_skill", "overridden_skill", "fully_overridden",
                "draft_skill", "org_only", "user_only"}
    assert active_names == expected


# TC-SP46  get_by_name returns active version only
def test_sp46_get_by_name_active(tiered_skills_dir, tmp_path):
    cfg = _make_config(tiered_skills_dir, tmp_path)
    reg = load_registry(cfg)

    assert reg.get_by_name("overridden_skill").tier == "org"
    assert reg.get_by_name("fully_overridden").tier == "user"


# ===========================================================================
# Registry Query Methods (TC-SP50 – TC-SP59)
# ===========================================================================

def _build_registry_for_queries() -> SkillRegistry:
    """Build a registry with diverse skills for query tests."""
    skills = [
        Skill(name="handle_refund", description="Process refund requests",
              domain="testing", status="active", tags=["tag1", "tag2"],
              output_format="text"),
        Skill(name="classify_inquiry", description="Classify customer inquiries",
              domain="testing", status="active", tags=["tag2", "tag3"],
              output_format="structured"),
        Skill(name="summarize_paper", description="Summarize research papers",
              domain="research", status="draft", tags=["tag4"],
              output_format="text"),
        Skill(name="deprecated_skill", description="Old deprecated skill",
              domain="legacy", status="deprecated", tags=[],
              output_format="text"),
    ]
    return SkillRegistry(skills=skills, mode="flat")


# TC-SP50  filter by domain
def test_sp50_filter_domain():
    reg = _build_registry_for_queries()
    results = reg.filter(domains=["testing"])

    assert len(results) == 2
    assert all(s.domain == "testing" for s in results)


# TC-SP51  filter by domain AND status (AND logic)
def test_sp51_filter_domain_and_status():
    reg = _build_registry_for_queries()
    results = reg.filter(domains=["testing"], statuses=["active"])

    assert len(results) == 2
    assert all(s.domain == "testing" and s.status == "active" for s in results)


# TC-SP52  filter by tags (OR logic within tags)
def test_sp52_filter_tags_or():
    reg = _build_registry_for_queries()
    results = reg.filter(tags=["tag1", "tag4"])

    names = {s.name for s in results}
    assert "handle_refund" in names      # has tag1
    assert "summarize_paper" in names    # has tag4
    assert len(results) == 2


# TC-SP53  filter by search_query (case-insensitive)
def test_sp53_filter_search():
    reg = _build_registry_for_queries()
    results = reg.filter(search_query="refund")

    names = {s.name for s in results}
    assert "handle_refund" in names   # name match
    assert len(results) >= 1


# TC-SP54  filter with all None → all active skills
def test_sp54_filter_all_none():
    reg = _build_registry_for_queries()
    results = reg.filter()

    assert len(results) == len(reg.get_active_skills())


# TC-SP55  search("") → all active skills
def test_sp55_empty_search():
    reg = _build_registry_for_queries()
    results = reg.search("")

    assert len(results) == len(reg.get_active_skills())


# TC-SP56  search nonexistent → empty
def test_sp56_no_match():
    reg = _build_registry_for_queries()
    results = reg.search("xyznonexistent")

    assert results == []


# TC-SP57  get_all_domains → sorted unique
def test_sp57_all_domains():
    reg = _build_registry_for_queries()
    domains = reg.get_all_domains()

    assert domains == sorted(set(domains))
    assert len(domains) == len(set(domains))


# TC-SP58  get_all_tags → sorted, no duplicates
def test_sp58_all_tags():
    reg = _build_registry_for_queries()
    tags = reg.get_all_tags()

    assert tags == sorted(set(tags))
    assert "tag1" in tags
    assert "tag2" in tags


# TC-SP59  get_all_output_formats → sorted unique
def test_sp59_all_output_formats():
    reg = _build_registry_for_queries()
    formats = reg.get_all_output_formats()

    assert formats == sorted(set(formats))
    assert "text" in formats
    assert "structured" in formats
