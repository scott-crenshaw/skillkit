Read DESIGN.md for all data models, module interfaces, test specifications,
and implementation order. This file is a quick reference. DESIGN.md is the
source of truth for architecture decisions.

# SkillKit Development Guide

## What This Is
A Streamlit dashboard for managing AI agent skill files. Skills are markdown
files with YAML frontmatter that encode domain expertise for AI agents.

## Key Architecture Decisions
- Dashboard is READ-ONLY on existing skill files (only writes new stubs)
- Supports flat directory or three-tier hierarchy (default/ < org/ < user/)
- Overlap detection uses sentence-transformers (default: all-MiniLM-L6-v2)
- Coverage map dimensions are user-configurable via coverage_config.yaml
- Embeddings are cached by SHA-256 content hash
- All features degrade gracefully when optional data (query log, coverage config) is missing
- Analysis features (overlap, query sim, clustering) are optional — `pip install skillkit[analysis]`

## Tech Stack
- Streamlit for UI
- PyYAML for frontmatter parsing
- sentence-transformers for embeddings (optional)
- numpy for cosine similarity (optional)
- pandas for data tables
- markdown for rendering skill body content

## Module Responsibilities
- app.py: Page routing and Streamlit layout only — no business logic
- skill_parser.py: All file I/O and frontmatter parsing
- coverage.py: Matrix building, auto-inference, coverage scoring
- overlap.py: Embedding computation, caching, similarity calculations
- gap_analysis.py: Query log processing, clustering, dead skill detection
- stub_generator.py: Template rendering and file creation
- config.py: Configuration loading with defaults, first-run setup
- ui_components.py: Reusable Streamlit rendering helpers

## File Conventions
- Skill files: markdown with YAML frontmatter (--- delimited)
- Status field: active | draft | deprecated
- All config in skillkit.yaml (auto-generated with defaults if missing)
- Generated data in data/ directory (embedding cache, coverage history, manual queries)

## Testing
- Each module has a corresponding test file in tests/
- Run: `pytest tests/`
- Example skill sets in examples/ are used as test fixtures
- Tests requiring sentence-transformers/numpy are marked `@pytest.mark.analysis`
- Analysis tests auto-skip if deps not installed

## Stop and Re-Plan If
- You're about to modify an existing skill file that isn't a newly generated stub
- You're adding a dependency not in pyproject.toml
- Any single page takes > 3 seconds to render with 50 skills
- You're hardcoding domain-specific content (all domain knowledge lives in skill files and config, never in code)
