# SkillKit — Manage Your AI Agent's Skills

SkillKit is a visual dashboard for managing AI agent skill files. If you're
building agents that use markdown-based skills (the pattern used by Claude Code,
Anthropic's Agent Skills spec, and production agent systems), SkillKit helps
you see what your agent can do, find gaps, detect overlapping skills, and
scaffold new ones.

## Quickstart

```bash
pip install skillkit
cd your-project
skillkit
```

That's it. SkillKit auto-detects your skills directory and generates a
default configuration. If you don't have skills yet, it creates an example
set to explore.

## What It Does

- **Catalog View** — Browse, search, and filter all your skills with expandable detail rows
- **Coverage Map** — Interactive heatmap showing what your agent can do and where the gaps are
- **Overlap Detection** — Find skills that might confuse your agent on similar queries
- **Gap Analysis** — Identify what your agent can't do, prioritized by user demand
- **Stub Generation** — Click a gap to create a new skill template, ready to fill in
- **Draft Queue** — Track in-progress skills in one place

## Skill File Format

Any markdown file with YAML frontmatter works:

```markdown
---
name: summarize_document
description: "Summarize a document with key findings and conclusions."
domain: research
status: active
domain_areas:
  - Research
task_types:
  - Summarize
---

# Summarize Document

## When to Use
When a user asks for a summary of a research paper, report, or long document.

## Steps
1. Read the full document
2. Identify key findings
3. Write a structured summary

## Output Format
Structured summary with sections for key findings, methodology, and conclusions.
```

See the `examples/` directory for complete skill files across multiple domains.

## Configuration

SkillKit works with zero configuration. For customization, create a
`skillkit.yaml` in your project root:

```yaml
skills_dir: ./skills
coverage_config: ./coverage_config.yaml
query_log: ./data/query_log.json    # optional — enables query clustering
embedding_model: all-MiniLM-L6-v2
overlap_high: 0.85
overlap_moderate: 0.70
cluster_threshold: 0.75
```

All paths are relative to the config file location.

## Optional Analysis Features

Overlap detection, query simulation, and query clustering require additional
dependencies:

```bash
pip install "skillkit[analysis]"
```

This adds `sentence-transformers` and `numpy`. Without these, SkillKit works
fully for catalog browsing, coverage mapping, stub generation, and draft
management. Analysis features show a helpful install message when accessed.

## Directory Modes

SkillKit supports two directory layouts:

**Flat** (default) — all `.md` files in one directory:
```
skills/
  handle_refund.md
  diagnose_outage.md
  summarize_paper.md
```

**Tiered** — three-tier hierarchy with override resolution (`user/ > org/ > default/`):
```
skills/
  default/
    handle_refund.md
  org/
    handle_refund.md    # overrides default
  user/
    handle_refund.md    # overrides both
```

SkillKit auto-detects the mode based on directory structure.

## Why Skills Matter

> "The model is not the product. The skills are the product."
> — Nicolas Bustamante, *Lessons from Building AI Agents*

Skills encode domain expertise as structured instructions. They give agents
consistency, accuracy, and capabilities beyond what the base model provides.
But without visibility into your skill catalog, you get gaps, overlaps, and
drift. SkillKit fixes that.

## Development

```bash
git clone <repo-url>
cd skillkit
pip install -e ".[analysis,dev]"
pytest tests/
```

## License

MIT
