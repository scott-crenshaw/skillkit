"""Skill file parsing, registry, and override resolution."""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .config import SkillKitConfig

logger = logging.getLogger("skillkit")

VALID_STATUSES = {"active", "draft", "deprecated"}
TIER_PRIORITY = {"user": 0, "org": 1, "default": 2}


@dataclass
class Skill:
    """A single parsed skill file."""

    # === Required (from frontmatter) ===
    name: str = ""
    description: str = ""

    # === Optional (from frontmatter, with defaults) ===
    output_format: str = "text"
    domain: str = "general"
    status: str = "active"
    domain_areas: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    version: Optional[str] = None
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    # === Computed (from file metadata and parsing) ===
    file_path: Path = field(default_factory=Path)
    body: str = ""
    word_count: int = 0
    last_modified: Optional[datetime] = None
    when_to_use: str = ""

    # === Tiered mode only ===
    tier: Optional[str] = None
    is_active: bool = True
    shadows: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.name


def _coerce_to_list(value: object) -> list[str]:
    """Coerce a scalar string or None to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _extract_when_to_use(body: str) -> str:
    """Extract text from '## When to Use' section. Case-insensitive.
    Returns empty string if not found."""
    pattern = re.compile(
        r"^##\s+when\s+to\s+use\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(body)
    if match is None:
        return ""
    start = match.end()
    # Find next ## heading
    next_heading = re.search(r"^##\s", body[start:], re.MULTILINE)
    if next_heading:
        text = body[start : start + next_heading.start()]
    else:
        text = body[start:]
    return text.strip()


def parse_skill_file(path: Path) -> Optional[Skill]:
    """Parse a single .md file into a Skill. Returns None if invalid."""
    try:
        raw_content = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None

    # Normalize Windows line endings
    raw_content = raw_content.replace("\r\n", "\n").replace("\r", "\n")

    if not raw_content.strip():
        logger.warning("Skipping %s: empty file", path)
        return None

    # Split frontmatter
    parts = raw_content.split("---", 2)
    if len(parts) < 3:
        logger.warning("Skipping %s: no valid frontmatter delimiters", path)
        return None

    yaml_text = parts[1]
    body = parts[2].strip() if len(parts) > 2 else ""

    # Parse YAML
    try:
        fm = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        logger.warning("Skipping %s: malformed YAML: %s", path, exc)
        return None

    if not isinstance(fm, dict):
        logger.warning("Skipping %s: frontmatter is not a mapping", path)
        return None

    # Validate required fields
    name = fm.get("name")
    if isinstance(name, str):
        name = name.strip()
    if not name:
        logger.warning("Skipping %s: missing or empty 'name' field", path)
        return None

    description = fm.get("description")
    if isinstance(description, str):
        description = description.strip()
    if not description:
        logger.warning("Skipping %s: missing or empty 'description' field", path)
        return None

    # Status validation
    status = str(fm.get("status", "active")).strip()
    if status not in VALID_STATUSES:
        logger.warning(
            "Skill %s in %s: unknown status '%s', defaulting to 'active'",
            name, path, status,
        )
        status = "active"

    # Optional fields with coercion
    output_format = str(fm.get("output_format", "text")).strip()
    domain = str(fm.get("domain", "general")).strip()
    domain_areas = _coerce_to_list(fm.get("domain_areas"))
    task_types_list = _coerce_to_list(fm.get("task_types"))
    tags = _coerce_to_list(fm.get("tags"))
    version = fm.get("version")
    if version is not None:
        version = str(version).strip()
    author = fm.get("author")
    if author is not None:
        author = str(author).strip()

    when_to_use = _extract_when_to_use(body)
    word_count = len(body.split()) if body else 0

    # Last modified from filesystem
    try:
        mtime = os.path.getmtime(path)
        last_modified = datetime.fromtimestamp(mtime)
    except OSError:
        last_modified = None

    return Skill(
        name=name,
        description=description,
        output_format=output_format,
        domain=domain,
        status=status,
        domain_areas=domain_areas,
        task_types=task_types_list,
        version=version,
        author=author,
        tags=tags,
        file_path=path,
        body=body,
        word_count=word_count,
        last_modified=last_modified,
        when_to_use=when_to_use,
    )


@dataclass
class SkillRegistry:
    """Collection of all parsed skills with query methods."""

    skills: list[Skill] = field(default_factory=list)
    mode: str = "flat"
    skills_dir: Path = field(default_factory=Path)

    def get_active_skills(self) -> list[Skill]:
        return [s for s in self.skills if s.is_active]

    def get_by_name(self, name: str) -> Optional[Skill]:
        for s in self.skills:
            if s.name == name and s.is_active:
                return s
        return None

    def get_by_domain(self, domain: str) -> list[Skill]:
        return [s for s in self.skills if s.domain == domain and s.is_active]

    def get_by_status(self, status: str) -> list[Skill]:
        return [s for s in self.skills if s.status == status and s.is_active]

    def get_all_domains(self) -> list[str]:
        return sorted({s.domain for s in self.skills if s.is_active})

    def get_all_tags(self) -> list[str]:
        tags: set[str] = set()
        for s in self.skills:
            if s.is_active:
                tags.update(s.tags)
        return sorted(tags)

    def get_all_output_formats(self) -> list[str]:
        return sorted({s.output_format for s in self.skills if s.is_active})

    def search(self, query: str) -> list[Skill]:
        if not query:
            return self.get_active_skills()
        q = query.lower()
        return [
            s for s in self.skills
            if s.is_active and (q in s.name.lower() or q in s.description.lower())
        ]

    def filter(
        self,
        domains: Optional[list[str]] = None,
        output_formats: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        tiers: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        search_query: Optional[str] = None,
    ) -> list[Skill]:
        results = self.get_active_skills()

        if domains is not None:
            results = [s for s in results if s.domain in domains]
        if output_formats is not None:
            results = [s for s in results if s.output_format in output_formats]
        if statuses is not None:
            results = [s for s in results if s.status in statuses]
        if tiers is not None:
            results = [s for s in results if s.tier in tiers]
        if tags is not None:
            results = [s for s in results if any(t in tags for t in s.tags)]
        if search_query:
            q = search_query.lower()
            results = [
                s for s in results
                if q in s.name.lower() or q in s.description.lower()
            ]
        return results

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
        counts: dict[str, int] = {}
        for s in self.skills:
            if s.is_active:
                counts[s.domain] = counts.get(s.domain, 0) + 1
        return counts


def _detect_mode(skills_dir: Path) -> str:
    """Returns 'flat' or 'tiered'."""
    tier_dirs = {"default", "org", "user"}
    try:
        subdirs = {d.name for d in skills_dir.iterdir() if d.is_dir()}
    except OSError:
        return "flat"
    return "tiered" if subdirs & tier_dirs else "flat"


def _resolve_overrides(skills: list[Skill]) -> list[Skill]:
    """For tiered mode: group by name, mark lower-tier duplicates as shadowed."""
    by_name: dict[str, list[Skill]] = {}
    for s in skills:
        by_name.setdefault(s.name, []).append(s)

    for name, group in by_name.items():
        if len(group) <= 1:
            continue
        # Sort by tier priority (user=0, org=1, default=2)
        group.sort(key=lambda s: TIER_PRIORITY.get(s.tier or "default", 99))
        winner = group[0]
        shadowed_tiers = [s.tier for s in group[1:] if s.tier]
        winner.shadows = shadowed_tiers
        for s in group[1:]:
            s.is_active = False

    return skills


def load_registry(config: SkillKitConfig) -> SkillRegistry:
    """Scan skills_dir, parse all .md files, resolve overrides."""
    skills_dir = config.skills_dir
    mode = _detect_mode(skills_dir)
    skills: list[Skill] = []

    if mode == "tiered":
        for tier_name in ("default", "org", "user"):
            tier_dir = skills_dir / tier_name
            if not tier_dir.is_dir():
                continue
            for md_file in tier_dir.glob("*.md"):
                skill = parse_skill_file(md_file)
                if skill is not None:
                    skill.tier = tier_name
                    skills.append(skill)
        skills = _resolve_overrides(skills)
    else:
        for md_file in skills_dir.rglob("*.md"):
            skill = parse_skill_file(md_file)
            if skill is not None:
                skills.append(skill)

    return SkillRegistry(skills=skills, mode=mode, skills_dir=skills_dir)
