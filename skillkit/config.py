"""Configuration loading, defaults, and first-run setup."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .skill_parser import SkillRegistry

import yaml

logger = logging.getLogger("skillkit")

# Default task_types used when auto-generating coverage_config.yaml
DEFAULT_TASK_TYPES = [
    "Analyze",
    "Compare",
    "Classify",
    "Summarize",
    "Generate",
    "Recommend",
    "Monitor",
    "Debug",
]

_DEFAULTS = {
    "skills_dir": "./skills",
    "coverage_config": "./coverage_config.yaml",
    "query_log": None,
    "embedding_model": "all-MiniLM-L6-v2",
    "overlap_high": 0.85,
    "overlap_moderate": 0.70,
    "cluster_threshold": 0.75,
}


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


class ConfigError(Exception):
    """Raised when a config file cannot be parsed."""


def load_config(config_path: Optional[Path] = None) -> SkillKitConfig:
    """Load from skillkit.yaml, or create with defaults.

    Search order:
    1. Explicit path if provided
    2. ./skillkit.yaml
    3. Generate defaults (skills_dir=./skills, etc.)

    Side effects on first run:
    - Creates skillkit.yaml with defaults if not found
    - Creates skills/ directory if not found
    - Creates data/ directory if not found
    """
    if config_path is None:
        config_path = Path("skillkit.yaml")

    config_path = Path(config_path)
    base_dir = config_path.parent

    if config_path.exists():
        raw_text = config_path.read_text(encoding="utf-8")
        try:
            raw = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise ConfigError(
                f"Invalid YAML in {config_path}: {exc}"
            ) from exc
        if raw is None:
            raw = {}
    else:
        raw = dict(_DEFAULTS)
        config_path.write_text(
            yaml.dump(raw, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Created default config at %s", config_path)

    # Resolve skills_dir
    skills_dir_str = raw.get("skills_dir", _DEFAULTS["skills_dir"])
    skills_dir = Path(skills_dir_str)
    if not skills_dir.is_absolute():
        skills_dir = (base_dir / skills_dir).resolve()

    # Resolve coverage config path
    cov_str = raw.get("coverage_config", _DEFAULTS["coverage_config"])
    cov_path = Path(cov_str)
    if not cov_path.is_absolute():
        cov_path = (base_dir / cov_path).resolve()

    # Resolve query log path
    ql = raw.get("query_log", _DEFAULTS["query_log"])
    query_log_path: Optional[Path] = None
    if ql is not None:
        query_log_path = Path(ql)
        if not query_log_path.is_absolute():
            query_log_path = (base_dir / query_log_path).resolve()

    # Data dir
    data_dir = (base_dir / "data").resolve()

    # Ensure directories exist
    created_new = not skills_dir.exists()
    skills_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Copy example skills only if directory was just created
    if created_new:
        _copy_examples_if_empty(skills_dir)

    return SkillKitConfig(
        skills_dir=skills_dir,
        coverage_config_path=cov_path,
        query_log_path=query_log_path,
        data_dir=data_dir,
        embedding_model=raw.get("embedding_model", _DEFAULTS["embedding_model"]),
        overlap_high=float(raw.get("overlap_high", _DEFAULTS["overlap_high"])),
        overlap_moderate=float(raw.get("overlap_moderate", _DEFAULTS["overlap_moderate"])),
        cluster_threshold=float(raw.get("cluster_threshold", _DEFAULTS["cluster_threshold"])),
    )


def _copy_examples_if_empty(skills_dir: Path) -> None:
    """Copy bundled example skills into skills_dir if it contains no .md files."""
    existing_md = list(skills_dir.rglob("*.md"))
    if existing_md:
        return

    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    if not examples_dir.exists():
        return

    copied = 0
    for domain_dir in sorted(examples_dir.iterdir()):
        if domain_dir.is_dir():
            for skill_file in sorted(domain_dir.glob("*.md")):
                shutil.copy2(skill_file, skills_dir / skill_file.name)
                copied += 1

    if copied:
        logger.info("Copied %d example skills into %s", copied, skills_dir)


def load_coverage_config(
    path: Path, registry: SkillRegistry
) -> tuple[list[str], list[str]]:
    """Load domain_areas and task_types from coverage_config.yaml.

    If file doesn't exist, auto-generate:
    - domain_areas = sorted unique domain values from registry skills
    - task_types = default set of 8 types
    Write generated config to path.

    The registry parameter should be a SkillRegistry (imported lazily to
    avoid circular imports).

    Returns (domain_areas, task_types).
    """
    if path.exists():
        raw_text = path.read_text(encoding="utf-8")
        raw = yaml.safe_load(raw_text)
        if raw is None:
            raw = {}
        domain_areas = raw.get("domain_areas", [])
        task_types = raw.get("task_types", DEFAULT_TASK_TYPES)
        if domain_areas is None:
            domain_areas = []
        if task_types is None:
            task_types = DEFAULT_TASK_TYPES
        return domain_areas, task_types

    # Auto-generate from registry
    active_skills = registry.get_active_skills()
    domains = sorted({s.domain for s in active_skills})
    generated = {
        "domain_areas": domains,
        "task_types": list(DEFAULT_TASK_TYPES),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(generated, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    logger.info("Generated coverage config at %s", path)
    return domains, list(DEFAULT_TASK_TYPES)


def ensure_data_dir(config: SkillKitConfig) -> None:
    """Create data/ directory and empty JSON files if they don't exist."""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("coverage_history.json", "embedding_cache.json", "manual_queries.json"):
        fp = config.data_dir / filename
        if not fp.exists():
            fp.write_text("[]" if filename != "embedding_cache.json" else "{}", encoding="utf-8")
