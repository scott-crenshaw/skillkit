"""Smoke tests for the app data pipeline — TC-APP01 through TC-APP07.

These verify the chain from config → registry → filtered data → UI inputs
without testing visual layout. Streamlit calls are either mocked or exercised
via AppTest where possible.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skillkit.config import SkillKitConfig, load_config, ensure_data_dir
from skillkit.skill_parser import Skill, SkillRegistry, load_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path: Path, skills_dir: Path) -> SkillKitConfig:
    """Build a config pointing at the given skills dir."""
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


# ---------------------------------------------------------------------------
# TC-APP01  App module imports without error
# ---------------------------------------------------------------------------

def test_app01_import():
    from skillkit import app  # noqa: F401
    from skillkit import ui_components  # noqa: F401


# ---------------------------------------------------------------------------
# TC-APP02  Full data pipeline: config → registry → structures
# ---------------------------------------------------------------------------

def test_app02_full_pipeline(example_skills_dir, tmp_path):
    cfg = _make_config(tmp_path, example_skills_dir)
    ensure_data_dir(cfg)
    reg = load_registry(cfg)

    assert reg.total_count == 12
    assert reg.active_count >= 9
    assert reg.draft_count >= 1
    assert reg.deprecated_count >= 1
    assert len(reg.get_all_domains()) >= 3
    assert len(reg.get_all_tags()) > 0
    assert len(reg.get_all_output_formats()) > 0


# ---------------------------------------------------------------------------
# TC-APP03  render_stat_cards with valid registry (mock st.*)
# ---------------------------------------------------------------------------

def test_app03_stat_cards(example_skills_dir, tmp_path):
    cfg = _make_config(tmp_path, example_skills_dir)
    reg = load_registry(cfg)

    with patch("skillkit.ui_components.st") as mock_st:
        mock_cols = [MagicMock() for _ in range(4)]
        mock_st.columns.return_value = mock_cols
        for c in mock_cols:
            c.__enter__ = MagicMock(return_value=c)
            c.__exit__ = MagicMock(return_value=False)

        from skillkit.ui_components import render_stat_cards
        render_stat_cards(reg)

        mock_st.columns.assert_called_once_with(4)
        # st.metric is called inside each `with cols[i]:` block
        assert mock_st.metric.call_count == 4
        labels = [call.args[0] for call in mock_st.metric.call_args_list]
        assert "Total Skills" in labels
        assert "Active" in labels


# ---------------------------------------------------------------------------
# TC-APP04  render_skill_table with valid skills (mock st.*)
# ---------------------------------------------------------------------------

def test_app04_skill_table(example_skills_dir, tmp_path):
    cfg = _make_config(tmp_path, example_skills_dir)
    reg = load_registry(cfg)
    skills = reg.get_active_skills()

    with patch("skillkit.ui_components.st") as mock_st:
        # Mock columns, expander, divider, etc.
        mock_st.columns.return_value = [MagicMock() for _ in range(5)]
        expander_ctx = MagicMock()
        expander_ctx.__enter__ = MagicMock(return_value=expander_ctx)
        expander_ctx.__exit__ = MagicMock(return_value=False)
        expander_ctx.columns.return_value = [MagicMock() for _ in range(4)]
        expander_ctx.button.return_value = False
        mock_st.expander.return_value = expander_ctx

        from skillkit.ui_components import render_skill_table
        render_skill_table(skills, sort_by="name")

        # Should have created one expander per skill
        assert mock_st.expander.call_count == len(skills)


# ---------------------------------------------------------------------------
# TC-APP05  render_skill_table with empty list → no crash
# ---------------------------------------------------------------------------

def test_app05_empty_table():
    with patch("skillkit.ui_components.st") as mock_st:
        from skillkit.ui_components import render_skill_table
        render_skill_table([], sort_by="name")

        mock_st.info.assert_called_once()


# ---------------------------------------------------------------------------
# TC-APP06  Filter pipeline: domain filter returns only matching skills
# ---------------------------------------------------------------------------

def test_app06_domain_filter(example_skills_dir, tmp_path):
    cfg = _make_config(tmp_path, example_skills_dir)
    reg = load_registry(cfg)

    devops = reg.filter(domains=["devops"])
    assert len(devops) > 0
    assert all(s.domain == "devops" for s in devops)

    cs = reg.filter(domains=["customer_support"])
    assert len(cs) > 0
    assert all(s.domain == "customer_support" for s in cs)

    # Combined count should not exceed active skills
    research = reg.filter(domains=["research"])
    assert len(devops) + len(cs) + len(research) <= len(reg.get_active_skills())


# ---------------------------------------------------------------------------
# TC-APP07  Filter pipeline: combined filters narrow correctly
# ---------------------------------------------------------------------------

def test_app07_combined_filters(example_skills_dir, tmp_path):
    cfg = _make_config(tmp_path, example_skills_dir)
    reg = load_registry(cfg)

    # Domain + status
    active_devops = reg.filter(domains=["devops"], statuses=["active"])
    all_devops = reg.filter(domains=["devops"])
    assert len(active_devops) <= len(all_devops)
    assert all(s.status == "active" and s.domain == "devops" for s in active_devops)

    # Search within domain
    refund_hits = reg.filter(domains=["customer_support"], search_query="refund")
    assert len(refund_hits) >= 1
    assert all("refund" in s.name.lower() or "refund" in s.description.lower()
               for s in refund_hits)

    # Tags filter (OR logic)
    tagged = reg.filter(tags=["incident", "academic"])
    assert len(tagged) >= 2
    assert all(any(t in ["incident", "academic"] for t in s.tags) for s in tagged)
