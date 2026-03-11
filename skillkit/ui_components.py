"""Reusable Streamlit rendering helpers for SkillKit UI."""

import os
import subprocess
import sys
from pathlib import Path

import markdown
import streamlit as st

import pandas as pd

from .skill_parser import Skill, SkillRegistry


# ---------------------------------------------------------------------------
# Editor integration
# ---------------------------------------------------------------------------

def open_in_editor(file_path: Path) -> None:
    """Open a skill file in the user's preferred editor.

    Tries in order:
    1. $EDITOR environment variable
    2. $VISUAL environment variable
    3. Platform default: 'code' (VS Code) on all platforms, then
       'open' (macOS), 'xdg-open' (Linux), 'start' (Windows)
    """
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        subprocess.Popen([editor, str(file_path)])
        return

    # Try VS Code first
    try:
        subprocess.Popen(["code", str(file_path)])
        return
    except FileNotFoundError:
        pass

    # Platform defaults
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(file_path)])
    elif sys.platform == "linux":
        subprocess.Popen(["xdg-open", str(file_path)])
    elif sys.platform == "win32":
        os.startfile(str(file_path))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Stat cards
# ---------------------------------------------------------------------------

def render_stat_cards(registry: SkillRegistry) -> None:
    """Render the top-bar summary stats: total, active, draft, deprecated."""
    cols = st.columns(4)
    with cols[0]:
        st.metric("Total Skills", registry.total_count)
    with cols[1]:
        st.metric("Active", registry.active_count)
    with cols[2]:
        st.metric("Draft", registry.draft_count)
    with cols[3]:
        st.metric("Deprecated", registry.deprecated_count)


# ---------------------------------------------------------------------------
# Skill table with expandable rows
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "active": "#2ecc71",
    "draft": "#f39c12",
    "deprecated": "#e74c3c",
}


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get(status, "#95a5a6")
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:4px;font-size:0.85em;">{status}</span>'
    )


def render_skill_table(
    skills: list[Skill],
    sort_by: str = "name",
    sort_ascending: bool = True,
    show_tier: bool = False,
) -> None:
    """Render the skill catalog as expandable rows with metadata and content."""
    if not skills:
        st.info("No skills match your current filters.")
        return

    # Sort
    key_map = {
        "name": lambda s: s.name.lower(),
        "domain": lambda s: s.domain.lower(),
        "word_count": lambda s: s.word_count,
        "last_modified": lambda s: s.last_modified or __import__("datetime").datetime.min,
        "status": lambda s: s.status,
        "output_format": lambda s: s.output_format.lower(),
    }
    key_fn = key_map.get(sort_by, key_map["name"])
    sorted_skills = sorted(skills, key=key_fn, reverse=not sort_ascending)

    # Table header
    header_cols = st.columns([3, 2, 2, 1.5, 1.5])
    header_cols[0].markdown("**Name**")
    header_cols[1].markdown("**Domain**")
    header_cols[2].markdown("**Format**")
    header_cols[3].markdown("**Words**")
    header_cols[4].markdown("**Status**")

    st.divider()

    # Each skill as an expandable row
    for skill in sorted_skills:
        with st.expander(f"{skill.name}", expanded=False):
            # Metadata row
            meta_cols = st.columns([2, 2, 2, 2])
            meta_cols[0].markdown(f"**Domain:** {skill.domain}")
            meta_cols[1].markdown(f"**Format:** {skill.output_format}")
            meta_cols[2].markdown(f"**Words:** {skill.word_count}")
            modified_str = (
                skill.last_modified.strftime("%Y-%m-%d")
                if skill.last_modified
                else "Unknown"
            )
            meta_cols[3].markdown(f"**Modified:** {modified_str}")

            # Second metadata row
            meta2_cols = st.columns([2, 2, 2, 2])
            tags_str = ", ".join(skill.tags) if skill.tags else "—"
            meta2_cols[0].markdown(f"**Tags:** {tags_str}")
            meta2_cols[1].markdown(f"**Author:** {skill.author or '—'}")
            meta2_cols[2].markdown(
                f"**Status:** {_status_badge(skill.status)}",
                unsafe_allow_html=True,
            )
            if show_tier and skill.tier:
                meta2_cols[3].markdown(f"**Tier:** {skill.tier}")
                if skill.shadows:
                    meta2_cols[3].caption(f"Shadows: {', '.join(skill.shadows)}")

            # Open in editor button
            if st.button(
                "Open in editor",
                key=f"edit_{skill.name}_{id(skill)}",
            ):
                open_in_editor(skill.file_path)
                st.toast(f"Opening {skill.file_path.name} in editor...")

            # Rendered markdown body
            st.divider()
            if skill.body:
                rendered = markdown.markdown(
                    skill.body,
                    extensions=["fenced_code", "tables"],
                )
                st.markdown(rendered, unsafe_allow_html=True)
            else:
                st.caption("No body content.")


# ---------------------------------------------------------------------------
# Coverage map rendering
# ---------------------------------------------------------------------------

_CELL_COLORS = {
    "covered": "#2ecc71",
    "draft_only": "#f39c12",
    "empty": "#e74c3c",
}


def render_coverage_grid(matrix) -> None:
    """Render the coverage heatmap as a grid of styled containers.

    Uses st.session_state['selected_cell'] to track clicks.
    The matrix parameter is a CoverageMatrix (imported lazily to avoid
    circular imports at module level).
    """
    from .coverage import CellState

    if not matrix.rows or not matrix.columns:
        st.info("Coverage matrix is empty. Add domain_areas and task_types to coverage_config.yaml.")
        return

    # Header row
    header_cols = st.columns([2] + [1] * len(matrix.columns))
    header_cols[0].markdown("**Domain / Task**")
    for i, col_name in enumerate(matrix.columns):
        header_cols[i + 1].markdown(f"**{col_name}**")

    # Grid rows
    for row_name in matrix.rows:
        row_cols = st.columns([2] + [1] * len(matrix.columns))
        row_cols[0].markdown(f"**{row_name}**")

        for j, col_name in enumerate(matrix.columns):
            cell = matrix.get_cell(row_name, col_name)
            if cell is None:
                continue

            color = _CELL_COLORS.get(cell.state.value, "#95a5a6")
            skill_count = len(cell.skills)

            with row_cols[j + 1]:
                if cell.state == CellState.COVERED:
                    label = f"{skill_count}"
                elif cell.state == CellState.DRAFT_ONLY:
                    label = f"{skill_count}d"
                else:
                    label = "—"

                st.markdown(
                    f'<div style="background:{color};color:white;padding:6px;'
                    f'border-radius:4px;text-align:center;font-weight:bold;'
                    f'font-size:0.9em;margin:1px 0;">{label}</div>',
                    unsafe_allow_html=True,
                )

                if st.button(
                    "Detail",
                    key=f"cell_{row_name}_{col_name}",
                    use_container_width=True,
                ):
                    st.session_state["selected_cell"] = (row_name, col_name)

    # Legend
    st.markdown(
        '<div style="margin-top:12px;font-size:0.85em;">'
        '<span style="background:#2ecc71;color:white;padding:2px 8px;border-radius:4px;">N</span> covered '
        '<span style="background:#f39c12;color:white;padding:2px 8px;border-radius:4px;">Nd</span> draft only '
        '<span style="background:#e74c3c;color:white;padding:2px 8px;border-radius:4px;">—</span> empty'
        '</div>',
        unsafe_allow_html=True,
    )

    # Selected cell detail
    selected = st.session_state.get("selected_cell")
    if selected:
        da, tt = selected
        cell = matrix.get_cell(da, tt)
        if cell:
            st.divider()
            st.subheader(f"{da} × {tt}")
            if cell.skills:
                st.caption(f"{len(cell.skills)} skill(s) — {cell.state.value}")
                for s in cell.skills:
                    st.markdown(f"- **{s.name}** — {s.description[:80]}...")
            else:
                st.warning("No skills cover this cell.")
                st.caption("Click **+ New Skill** in the sidebar to create one for this gap.")


def render_coverage_score(
    score: float,
    delta: float | None,
    history,
) -> None:
    """Render coverage score with delta indicator and mini sparkline."""
    # Score metric with delta
    delta_str = f"{delta:+.1f}%" if delta is not None else None
    st.metric("Coverage Score", f"{score:.1f}%", delta=delta_str)

    # Sparkline from history entries
    if history.entries and len(history.entries) >= 2:
        chart_data = pd.DataFrame({
            "date": [e.date for e in history.entries],
            "score": [e.score for e in history.entries],
        })
        chart_data["date"] = pd.to_datetime(chart_data["date"])
        chart_data = chart_data.set_index("date")
        st.line_chart(chart_data, height=120)


# ---------------------------------------------------------------------------
# Draft queue
# ---------------------------------------------------------------------------

def render_draft_queue(registry: SkillRegistry) -> None:
    """Table of draft skills: name, description, domain_areas, task_types, modified."""
    drafts = registry.get_by_status("draft")
    if not drafts:
        st.info("No draft skills found. Create one with **+ New Skill** or from the Coverage Map.")
        return

    st.caption(f"{len(drafts)} draft skill(s)")

    for skill in sorted(drafts, key=lambda s: s.name.lower()):
        with st.expander(skill.name):
            cols = st.columns([2, 2, 2])
            cols[0].markdown(f"**Description:** {skill.description}")
            da_str = ", ".join(skill.domain_areas) if skill.domain_areas else "—"
            cols[1].markdown(f"**Domain areas:** {da_str}")
            tt_str = ", ".join(skill.task_types) if skill.task_types else "—"
            cols[2].markdown(f"**Task types:** {tt_str}")

            modified_str = (
                skill.last_modified.strftime("%Y-%m-%d")
                if skill.last_modified
                else "Unknown"
            )
            st.caption(f"Modified: {modified_str} | Words: {skill.word_count}")


# ---------------------------------------------------------------------------
# Overlap / query simulation rendering
# ---------------------------------------------------------------------------

_RISK_COLORS = {
    "high": "\U0001f534",     # red circle
    "moderate": "\U0001f7e1",  # yellow circle
}


def render_query_simulator(config, registry) -> None:
    """Text input + ranked results list. Highlights ambiguous top results.
    Rendered ABOVE the overlap table — it's the primary tool."""
    st.subheader("Query Simulator")
    query = st.text_input(
        "Test query",
        placeholder="Type a test query to see which skills match...",
        key="query_sim_input",
    )

    if not query:
        st.caption("Enter a query above to see how skills rank.")
        return

    from .overlap import simulate_query, check_analysis_available
    if not check_analysis_available():
        render_analysis_unavailable_message()
        return

    result = simulate_query(query, registry, config)

    if not result.ranked_skills:
        st.info("No skills to rank.")
        return

    if result.is_ambiguous:
        st.warning("**Ambiguous!** Top two skills are within 0.05 similarity.")

    for i, scored in enumerate(result.ranked_skills[:10]):
        score = scored.score
        bar_width = max(0, min(100, int(score * 100)))
        name = scored.skill.name
        indicator = " \u26a0\ufe0f" if i < 2 and result.is_ambiguous else ""
        st.markdown(
            f"**{i+1}. {name}** ({score:.2f}){indicator}"
        )
        st.progress(bar_width / 100)


def render_overlap_table(report) -> None:
    """Render the overlap pairs table with risk level coloring."""
    from .overlap import OverlapReport  # type hint only

    if not report.pairs:
        st.info("No overlapping skill pairs detected above the moderate threshold.")
        return

    high_count = len(report.high_risk_pairs)
    mod_count = len(report.moderate_risk_pairs)
    st.markdown(f"**High risk:** {high_count} pair(s)  |  **Moderate:** {mod_count} pair(s)")

    for pair in report.pairs:
        icon = _RISK_COLORS.get(pair.risk_level, "")
        with st.expander(
            f"{pair.skill_a.name} \u2194 {pair.skill_b.name}  "
            f"{pair.similarity:.2f} {icon}"
        ):
            cols = st.columns(2)
            with cols[0]:
                st.markdown(f"**{pair.skill_a.name}**")
                st.caption(pair.text_a[:300])
            with cols[1]:
                st.markdown(f"**{pair.skill_b.name}**")
                st.caption(pair.text_b[:300])


# ---------------------------------------------------------------------------
# Analysis unavailable message
# ---------------------------------------------------------------------------

def render_analysis_unavailable_message() -> None:
    """Show friendly message when analysis deps are missing."""
    st.warning(
        "**Analysis features require additional dependencies.**\n\n"
        "Install them with:\n\n"
        "```\npip install skillkit[analysis]\n```\n\n"
        "This adds `sentence-transformers` and `numpy` for overlap "
        "detection, query simulation, and query clustering."
    )


def render_welcome_page() -> None:
    """Shown when no skills exist."""
    st.title("Welcome to SkillKit!")
    st.markdown(
        "No skill files found. To get started:\n\n"
        "1. Add `.md` skill files to your skills directory, or\n"
        "2. Click **+ New Skill** in the sidebar to create your first skill."
    )
