"""Stub file creation, collision detection, and name generation."""

import re
from pathlib import Path
from typing import Optional

import yaml


def generate_stub(
    name: str,
    description: str = "",
    domain: str = "general",
    domain_areas: Optional[list[str]] = None,
    task_types: Optional[list[str]] = None,
) -> str:
    """Generate the full markdown content for a new skill stub.
    Returns the file content as a string (does not write to disk)."""
    fm: dict = {
        "name": name,
        "description": description if description else f"TODO: Describe {name}",
        "domain": domain,
        "status": "draft",
    }
    if domain_areas:
        fm["domain_areas"] = domain_areas
    if task_types:
        fm["task_types"] = task_types

    frontmatter = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    title = name.replace("_", " ").title()

    body = (
        f"# {title}\n"
        "\n"
        "## When to Use\n"
        "TODO: Describe when this skill should be activated.\n"
        "\n"
        "## Steps\n"
        "1. TODO: Add steps.\n"
        "\n"
        "## Output Format\n"
        "TODO: Describe the expected output format.\n"
        "\n"
        "## Common Pitfalls\n"
        "- TODO: List common pitfalls.\n"
    )

    return f"---\n{frontmatter}---\n\n{body}"


def write_stub(
    content: str,
    name: str,
    skills_dir: Path,
    mode: str,
) -> Path:
    """Write stub to disk with collision detection.

    - Flat mode: writes to skills_dir/{name}.md
    - Tiered mode: writes to skills_dir/default/{name}.md

    Raises FileExistsError if file already exists.
    Returns the path of the created file.
    """
    if mode == "tiered":
        target_dir = skills_dir / "default"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{name}.md"
    else:
        target = skills_dir / f"{name}.md"

    if target.exists():
        raise FileExistsError(f"Skill file already exists: {target}")

    target.write_text(content, encoding="utf-8")
    return target


def generate_name_from_coverage(task_type: str, domain_area: str) -> str:
    """Generate skill name from coverage map coordinates.
    Example: ('Analyze', 'Data Analysis') -> 'analyze_data_analysis'
    """
    raw = f"{task_type.strip()}_{domain_area.strip()}"
    # Lowercase, replace spaces and & with underscore/and
    result = raw.lower().replace("&", "and").replace("/", "_").replace(" ", "_")
    # Collapse multiple underscores
    result = re.sub(r"_+", "_", result)
    # Remove characters unsafe for filenames
    result = re.sub(r"[^\w]", "", result)
    return result
