"""Tests for skillkit/config.py — TC-C01 through TC-C14."""

import yaml
import pytest
from pathlib import Path

from skillkit.config import (
    SkillKitConfig,
    ConfigError,
    load_config,
    load_coverage_config,
    ensure_data_dir,
    DEFAULT_TASK_TYPES,
)
from skillkit.skill_parser import SkillRegistry, Skill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def _make_registry(domains: list[str]) -> SkillRegistry:
    """Build a minimal registry with skills having the given domains."""
    skills = [
        Skill(name=f"skill_{d}", description=f"Desc for {d}", domain=d)
        for d in domains
    ]
    return SkillRegistry(skills=skills)


# ---------------------------------------------------------------------------
# TC-C01  Load existing skillkit.yaml with all fields set
# ---------------------------------------------------------------------------

def test_c01_load_all_fields(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    _write_yaml(config_file, {
        "skills_dir": "./my_skills",
        "coverage_config": "./cov.yaml",
        "query_log": "./queries.json",
        "embedding_model": "custom-model",
        "overlap_high": 0.90,
        "overlap_moderate": 0.60,
        "cluster_threshold": 0.80,
    })

    cfg = load_config(config_file)

    assert cfg.skills_dir == (tmp_path / "my_skills").resolve()
    assert cfg.coverage_config_path == (tmp_path / "cov.yaml").resolve()
    assert cfg.query_log_path == (tmp_path / "queries.json").resolve()
    assert cfg.embedding_model == "custom-model"
    assert cfg.overlap_high == 0.90
    assert cfg.overlap_moderate == 0.60
    assert cfg.cluster_threshold == 0.80


# ---------------------------------------------------------------------------
# TC-C02  Load skillkit.yaml with only skills_dir set
# ---------------------------------------------------------------------------

def test_c02_partial_config(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    _write_yaml(config_file, {"skills_dir": "./skills"})

    cfg = load_config(config_file)

    assert cfg.embedding_model == "all-MiniLM-L6-v2"
    assert cfg.overlap_high == 0.85
    assert cfg.overlap_moderate == 0.70
    assert cfg.cluster_threshold == 0.75
    assert cfg.query_log_path is None


# ---------------------------------------------------------------------------
# TC-C03  No skillkit.yaml exists → auto-generates with defaults
# ---------------------------------------------------------------------------

def test_c03_auto_generate(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    assert not config_file.exists()

    cfg = load_config(config_file)

    assert config_file.exists()
    assert cfg.overlap_high == 0.85
    assert cfg.skills_dir.exists()

    # Verify YAML on disk is valid
    on_disk = yaml.safe_load(config_file.read_text())
    assert on_disk["skills_dir"] == "./skills"


# ---------------------------------------------------------------------------
# TC-C04  skills_dir as relative path → resolved relative to config parent
# ---------------------------------------------------------------------------

def test_c04_relative_skills_dir(tmp_path):
    config_file = tmp_path / "subdir" / "skillkit.yaml"
    config_file.parent.mkdir()
    _write_yaml(config_file, {"skills_dir": "../my_skills"})

    cfg = load_config(config_file)

    expected = (tmp_path / "subdir" / ".." / "my_skills").resolve()
    assert cfg.skills_dir == expected


# ---------------------------------------------------------------------------
# TC-C05  skills_dir as absolute path → used as-is
# ---------------------------------------------------------------------------

def test_c05_absolute_skills_dir(tmp_path):
    abs_dir = tmp_path / "abs_skills"
    config_file = tmp_path / "skillkit.yaml"
    _write_yaml(config_file, {"skills_dir": str(abs_dir)})

    cfg = load_config(config_file)

    assert cfg.skills_dir == abs_dir


# ---------------------------------------------------------------------------
# TC-C06  skills_dir doesn't exist → created by load_config
# ---------------------------------------------------------------------------

def test_c06_creates_skills_dir(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    _write_yaml(config_file, {"skills_dir": "./new_skills"})

    expected = (tmp_path / "new_skills").resolve()
    assert not expected.exists()

    cfg = load_config(config_file)

    assert expected.exists()
    assert expected.is_dir()


# ---------------------------------------------------------------------------
# TC-C07  data_dir doesn't exist → ensure_data_dir creates it
# ---------------------------------------------------------------------------

def test_c07_ensure_data_dir(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    _write_yaml(config_file, {"skills_dir": "./skills"})
    cfg = load_config(config_file)

    data_dir = cfg.data_dir
    # Remove data dir to test creation
    import shutil
    if data_dir.exists():
        shutil.rmtree(data_dir)
    assert not data_dir.exists()

    ensure_data_dir(cfg)

    assert data_dir.exists()
    assert (data_dir / "coverage_history.json").exists()
    assert (data_dir / "embedding_cache.json").exists()
    assert (data_dir / "manual_queries.json").exists()


# ---------------------------------------------------------------------------
# TC-C08  Invalid YAML → ConfigError with file path
# ---------------------------------------------------------------------------

def test_c08_invalid_yaml(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    config_file.write_text("skills_dir: [unclosed\n\thas tabs", encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_file)

    assert str(config_file) in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-C09  coverage_config auto-generation from skills
# ---------------------------------------------------------------------------

def test_c09_coverage_auto_gen(tmp_path):
    cov_path = tmp_path / "coverage_config.yaml"
    registry = _make_registry(["devops", "customer_support", "research"])

    domain_areas, task_types = load_coverage_config(cov_path, registry)

    assert domain_areas == ["customer_support", "devops", "research"]
    assert task_types == DEFAULT_TASK_TYPES
    assert cov_path.exists()

    # Verify file is valid YAML
    on_disk = yaml.safe_load(cov_path.read_text())
    assert on_disk["domain_areas"] == ["customer_support", "devops", "research"]


# ---------------------------------------------------------------------------
# TC-C10  coverage_config auto-generation with zero skills
# ---------------------------------------------------------------------------

def test_c10_coverage_auto_gen_empty(tmp_path):
    cov_path = tmp_path / "coverage_config.yaml"
    registry = SkillRegistry(skills=[])

    domain_areas, task_types = load_coverage_config(cov_path, registry)

    assert domain_areas == []
    assert task_types == DEFAULT_TASK_TYPES
    assert cov_path.exists()


# ---------------------------------------------------------------------------
# TC-C11  Load existing coverage_config.yaml
# ---------------------------------------------------------------------------

def test_c11_load_existing_coverage(tmp_path):
    cov_path = tmp_path / "coverage_config.yaml"
    _write_yaml(cov_path, {
        "domain_areas": ["Alpha", "Beta"],
        "task_types": ["Summarize", "Debug"],
    })

    domain_areas, task_types = load_coverage_config(cov_path, SkillRegistry())

    assert domain_areas == ["Alpha", "Beta"]
    assert task_types == ["Summarize", "Debug"]


# ---------------------------------------------------------------------------
# TC-C12  coverage_config.yaml with empty domain_areas list
# ---------------------------------------------------------------------------

def test_c12_empty_domain_areas(tmp_path):
    cov_path = tmp_path / "coverage_config.yaml"
    _write_yaml(cov_path, {
        "domain_areas": [],
        "task_types": ["Analyze"],
    })

    domain_areas, task_types = load_coverage_config(cov_path, SkillRegistry())

    assert domain_areas == []
    assert task_types == ["Analyze"]


# ---------------------------------------------------------------------------
# TC-C13  coverage_config.yaml with empty task_types list
# ---------------------------------------------------------------------------

def test_c13_empty_task_types(tmp_path):
    cov_path = tmp_path / "coverage_config.yaml"
    _write_yaml(cov_path, {
        "domain_areas": ["A", "B"],
        "task_types": [],
    })

    domain_areas, task_types = load_coverage_config(cov_path, SkillRegistry())

    assert domain_areas == ["A", "B"]
    assert task_types == []


# ---------------------------------------------------------------------------
# TC-C14  query_log path to non-existent file → config loads successfully
# ---------------------------------------------------------------------------

def test_c14_missing_query_log(tmp_path):
    config_file = tmp_path / "skillkit.yaml"
    _write_yaml(config_file, {
        "skills_dir": "./skills",
        "query_log": "./does_not_exist.json",
    })

    cfg = load_config(config_file)

    assert cfg.query_log_path is not None
    assert not cfg.query_log_path.exists()
