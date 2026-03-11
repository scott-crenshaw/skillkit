"""
SkillKit — AI Agent Skills Manager

Main Streamlit application. Page routing and layout only.
Business logic lives in other modules.

Launch with:  python -m streamlit run skillkit/app.py
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so relative imports resolve
# when Streamlit runs this file as a script rather than as a package module.
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import hashlib

import streamlit as st
import yaml

from skillkit.config import SkillKitConfig, load_config, load_coverage_config, ensure_data_dir
from skillkit.coverage import (
    build_coverage_matrix,
    load_coverage_history,
    record_coverage_snapshot,
)
from skillkit.gap_analysis import (
    build_gap_report,
    load_manual_queries,
    save_manual_queries,
)
from skillkit.skill_parser import SkillRegistry, load_registry
from skillkit.stub_generator import generate_name_from_coverage, generate_stub, write_stub
from skillkit.ui_components import (
    render_analysis_unavailable_message,
    render_coverage_grid,
    render_coverage_score,
    render_draft_queue,
    render_overlap_table,
    render_query_simulator,
    render_skill_table,
    render_stat_cards,
    render_welcome_page,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_PAGES = {
    "Catalog": "catalog",
    "Coverage Map": "coverage",
    "Overlap Detection": "overlap",
    "Gap Analysis": "gap_analysis",
    "Draft Queue": "draft_queue",
    "Settings": "settings",
}

_PAGE_ICONS = {
    "Catalog": "\U0001f4cb",           # clipboard
    "Coverage Map": "\U0001f5fa\ufe0f",  # world map
    "Overlap Detection": "\U0001f50d",  # magnifying glass
    "Gap Analysis": "\U0001f4ca",       # bar chart
    "Draft Queue": "\U0001f4dd",        # memo
    "Settings": "\u2699\ufe0f",         # gear
}


# ---------------------------------------------------------------------------
# Config + registry loading (cached per session)
# ---------------------------------------------------------------------------

def _get_config_path() -> Path:
    """Return the config path, either from session state or default."""
    return Path(st.session_state.get("config_path", "skillkit.yaml"))


@st.cache_resource(show_spinner="Loading configuration...")
def _load_config(config_path_str: str) -> SkillKitConfig:
    config = load_config(Path(config_path_str))
    ensure_data_dir(config)
    return config


def _skills_dir_hash(skills_dir: Path) -> str:
    """Fast hash from all .md file paths and their mtime timestamps."""
    h = hashlib.md5()
    for p in sorted(skills_dir.rglob("*.md")):
        h.update(str(p).encode())
        h.update(str(p.stat().st_mtime_ns).encode())
    return h.hexdigest()


@st.cache_data(show_spinner="Loading skills...")
def _load_registry_cached(_config: SkillKitConfig, _dir_hash: str) -> SkillRegistry:
    """Load registry, cached until the skills directory changes."""
    return load_registry(_config)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar(registry: SkillRegistry, config: SkillKitConfig) -> str:
    """Render sidebar and return the selected page key."""
    with st.sidebar:
        st.title("\U0001f527 SkillKit")

        # Skills directory display
        st.caption("Skills directory")
        st.code(str(config.skills_dir), language=None)

        # Change skills directory
        with st.expander("Change directory", expanded=False):
            new_dir = st.text_input(
                "New skills directory path",
                value=str(config.skills_dir),
                key="new_skills_dir",
                label_visibility="collapsed",
            )
            if st.button("Apply", key="apply_dir"):
                config_path = _get_config_path()
                if config_path.exists():
                    raw = yaml.safe_load(config_path.read_text()) or {}
                else:
                    raw = {}
                raw["skills_dir"] = new_dir
                config_path.write_text(
                    yaml.dump(raw, default_flow_style=False, sort_keys=False)
                )
                st.cache_resource.clear()
                st.rerun()

        st.divider()

        # Navigation
        st.caption("Navigation")
        page_labels = list(_PAGES.keys())
        selected_label = st.radio(
            "Go to",
            page_labels,
            format_func=lambda p: f"{_PAGE_ICONS.get(p, '')} {p}",
            label_visibility="collapsed",
            key="nav_radio",
        )

        st.divider()

        # Quick stats
        st.caption("Quick stats")
        st.markdown(f"**{registry.total_count}** skills")
        active_pct = (
            round(registry.active_count / registry.total_count * 100)
            if registry.total_count
            else 0
        )
        st.markdown(f"**{registry.active_count}** active ({active_pct}%)")

        st.divider()

        # Refresh button
        if st.button("\U0001f504 Refresh", use_container_width=True, key="refresh"):
            st.cache_data.clear()
            st.rerun()

        # New Skill button
        if st.button("\u2795 New Skill", use_container_width=True, key="new_skill"):
            st.session_state["show_stub_form"] = True

    return _PAGES[selected_label]


# ---------------------------------------------------------------------------
# Page: Catalog
# ---------------------------------------------------------------------------

def page_catalog(registry: SkillRegistry, config: SkillKitConfig) -> None:
    """Feature 1: Catalog view with filters, search, expandable skills."""
    st.title("Skill Catalog")

    # Stat cards
    render_stat_cards(registry)

    st.divider()

    # Search bar
    search_query = st.text_input(
        "Search skills",
        placeholder="Search by name or description...",
        key="catalog_search",
    )

    # Filters row
    filter_cols = st.columns([2, 2, 3])

    with filter_cols[0]:
        all_domains = ["All"] + registry.get_all_domains()
        selected_domain = st.selectbox("Domain", all_domains, key="filter_domain")

    with filter_cols[1]:
        all_formats = ["All"] + registry.get_all_output_formats()
        selected_format = st.selectbox("Format", all_formats, key="filter_format")

    with filter_cols[2]:
        all_tags = registry.get_all_tags()
        selected_tags = st.multiselect("Tags", all_tags, key="filter_tags")

    # Status checkboxes
    status_cols = st.columns(3)
    with status_cols[0]:
        show_active = st.checkbox("Active", value=True, key="filter_active")
    with status_cols[1]:
        show_draft = st.checkbox("Draft", value=True, key="filter_draft")
    with status_cols[2]:
        show_deprecated = st.checkbox("Deprecated", value=False, key="filter_deprecated")

    statuses = []
    if show_active:
        statuses.append("active")
    if show_draft:
        statuses.append("draft")
    if show_deprecated:
        statuses.append("deprecated")

    # Build filter kwargs
    domains = [selected_domain] if selected_domain != "All" else None
    output_formats = [selected_format] if selected_format != "All" else None
    tags_filter = selected_tags if selected_tags else None

    filtered = registry.filter(
        domains=domains,
        output_formats=output_formats,
        statuses=statuses if statuses else None,
        tags=tags_filter,
        search_query=search_query if search_query else None,
    )

    st.divider()

    # Sort controls
    sort_cols = st.columns([2, 1])
    with sort_cols[0]:
        sort_by = st.selectbox(
            "Sort by",
            ["name", "domain", "output_format", "word_count", "last_modified", "status"],
            key="sort_by",
        )
    with sort_cols[1]:
        sort_order = st.selectbox(
            "Order",
            ["Ascending", "Descending"],
            key="sort_order",
        )

    st.caption(f"Showing {len(filtered)} of {registry.total_count} skills")

    # Render table
    render_skill_table(
        filtered,
        sort_by=sort_by,
        sort_ascending=(sort_order == "Ascending"),
        show_tier=(registry.mode == "tiered"),
    )


# ---------------------------------------------------------------------------
# Page: Coverage Map
# ---------------------------------------------------------------------------

def page_coverage(registry: SkillRegistry, config: SkillKitConfig) -> None:
    st.title("Coverage Map")

    # Load coverage config (auto-generates if missing)
    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )

    # Build matrix
    matrix = build_coverage_matrix(registry, domain_areas, task_types)

    # Record snapshot and get delta
    delta = record_coverage_snapshot(matrix, registry, config.data_dir)
    history = load_coverage_history(config.data_dir)

    # Score display
    score = matrix.coverage_score
    # delta_since_last compares to *previous* entry (before the one we just wrote)
    display_delta = None
    if len(history.entries) >= 2:
        display_delta = history.entries[-1].score - history.entries[-2].score
    elif delta is not None and len(history.entries) == 1:
        display_delta = None  # First entry, no previous to compare

    score_col, unmapped_col = st.columns([2, 1])
    with score_col:
        render_coverage_score(score, display_delta, history)
    with unmapped_col:
        if matrix.unmapped_skills:
            st.warning(
                f"**{len(matrix.unmapped_skills)}** skills not mapped to the "
                "coverage grid. Add `domain_areas` and `task_types` to their "
                "frontmatter to place them."
            )
            with st.expander("Unmapped skills"):
                for s in matrix.unmapped_skills:
                    st.markdown(f"- {s.name}")

    st.divider()

    # Grid
    render_coverage_grid(matrix)

    # Stub creation from empty cell
    selected = st.session_state.get("selected_cell")
    if selected:
        da, tt = selected
        cell = matrix.get_cell(da, tt)
        if cell and not cell.skills:
            suggested_name = generate_name_from_coverage(tt, da)
            st.divider()
            st.subheader(f"Create stub for {da} \u00d7 {tt}")
            with st.form("coverage_stub_form"):
                stub_name = st.text_input("Skill name", value=suggested_name)
                stub_desc = st.text_area("Description", value="")
                stub_domain = st.text_input("Domain", value="general")
                if st.form_submit_button("Create Stub"):
                    if not stub_name:
                        st.error("Name is required.")
                    else:
                        content = generate_stub(
                            name=stub_name,
                            description=stub_desc,
                            domain=stub_domain,
                            domain_areas=[da],
                            task_types=[tt],
                        )
                        try:
                            path = write_stub(content, stub_name, config.skills_dir, registry.mode)
                            st.success(f"Created {path.name}")
                            st.session_state.pop("selected_cell", None)
                            st.rerun()
                        except FileExistsError as exc:
                            st.error(str(exc))


# ---------------------------------------------------------------------------
# Page: Overlap Detection (placeholder)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Computing overlap...")
def _cached_overlap_report(
    _registry_hash: str,
    config_data_dir: str,
    embedding_model: str,
    overlap_high: float,
    overlap_moderate: float,
):
    """Cached overlap report — recomputes only when skills or config change."""
    from skillkit.overlap import build_overlap_report

    config_path = _get_config_path()
    config = _load_config(str(config_path))
    registry = load_registry(config)
    return build_overlap_report(registry, config)


def page_overlap(registry: SkillRegistry, config: SkillKitConfig) -> None:
    st.title("Overlap Detection")

    from skillkit.overlap import check_analysis_available

    if not check_analysis_available():
        render_analysis_unavailable_message()
        return

    # Query simulator at the top (primary tool)
    render_query_simulator(config, registry)

    st.divider()

    # Overlap report below (cached)
    st.subheader("Overlap Report")
    dir_hash = _skills_dir_hash(config.skills_dir)
    report = _cached_overlap_report(
        dir_hash,
        str(config.data_dir),
        config.embedding_model,
        config.overlap_high,
        config.overlap_moderate,
    )
    render_overlap_table(report)


# ---------------------------------------------------------------------------
# Page: Gap Analysis (placeholder)
# ---------------------------------------------------------------------------

def page_gap_analysis(registry: SkillRegistry, config: SkillKitConfig) -> None:
    """Feature 4: Coverage gaps (always), query clusters + dead skills
    (if analysis deps + query log available), manual query entry."""
    st.title("Gap Analysis")

    # Load coverage config and build matrix for gaps
    domain_areas, task_types = load_coverage_config(
        config.coverage_config_path, registry
    )
    matrix = build_coverage_matrix(registry, domain_areas, task_types)

    # Build full gap report
    report = build_gap_report(registry, matrix, config)

    # Summary stats
    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.metric("Coverage Gaps", len(report.coverage_gaps))
    with stat_cols[1]:
        st.metric("Unmatched Queries", report.unmatched_query_count)
    with stat_cols[2]:
        st.metric("Query Clusters", len(report.clusters))
    with stat_cols[3]:
        st.metric("Dead Skills", len(report.dead_skills))

    st.divider()

    # --- Manual query entry ---
    st.subheader("Manual Query Entry")
    st.caption(
        "Paste queries your agent couldn't handle. These are merged with "
        "the query log (if configured) for analysis."
    )
    existing_manual = load_manual_queries(config.data_dir)
    manual_text = st.text_area(
        "Queries (one per line)",
        value="\n".join(existing_manual),
        height=120,
        key="manual_queries_input",
    )
    if st.button("Save Queries", key="save_manual_queries"):
        queries = [q.strip() for q in manual_text.split("\n") if q.strip()]
        save_manual_queries(queries, config.data_dir)
        st.success(f"Saved {len(queries)} manual query(ies).")
        st.rerun()

    st.divider()

    # --- Coverage gaps (always visible) ---
    st.subheader("Coverage Gaps")
    if report.coverage_gaps:
        st.caption(
            f"{len(report.coverage_gaps)} empty cell(s) in coverage map, "
            "prioritized by surrounding coverage."
        )
        for gap in report.coverage_gaps:
            with st.expander(f"{gap.domain_area} × {gap.task_type}"):
                suggested_name = generate_name_from_coverage(
                    gap.task_type, gap.domain_area
                )
                st.markdown(f"**Suggested skill:** `{suggested_name}`")
                if st.button(
                    "Create Stub",
                    key=f"gap_stub_{gap.domain_area}_{gap.task_type}",
                ):
                    content = generate_stub(
                        name=suggested_name,
                        description=f"Skill for {gap.task_type} in {gap.domain_area}",
                        domain="general",
                        domain_areas=[gap.domain_area],
                        task_types=[gap.task_type],
                    )
                    try:
                        path = write_stub(
                            content, suggested_name,
                            config.skills_dir, registry.mode,
                        )
                        st.success(f"Created {path.name}")
                        st.rerun()
                    except FileExistsError as exc:
                        st.error(str(exc))
    else:
        st.info("No coverage gaps — all cells in the coverage map are filled.")

    st.divider()

    # --- Query clusters (if available) ---
    st.subheader("Query Clusters")
    if not report.has_query_log and not report.has_manual_queries:
        _render_query_log_setup_guide()
    elif not report.clusters:
        if report.unmatched_query_count == 0:
            st.info("No unmatched queries to cluster.")
        else:
            from skillkit.overlap import check_analysis_available
            if not check_analysis_available():
                render_analysis_unavailable_message()
            else:
                st.info("No query clusters formed from the unmatched queries.")
    else:
        st.caption(f"{len(report.clusters)} cluster(s) from {report.unmatched_query_count} unmatched query(ies)")
        for cluster in report.clusters:
            with st.expander(
                f"{cluster.suggested_skill_name} ({cluster.count} queries)"
            ):
                st.markdown(f"**Representative:** {cluster.representative_query}")
                st.markdown(f"**Suggested description:** {cluster.suggested_description}")
                if len(cluster.queries) > 1:
                    with st.container():
                        st.caption("All queries in this cluster:")
                        for q in cluster.queries:
                            st.markdown(f"- {q}")
                if st.button(
                    "Create Stub",
                    key=f"cluster_stub_{cluster.suggested_skill_name}",
                ):
                    content = generate_stub(
                        name=cluster.suggested_skill_name,
                        description=cluster.suggested_description,
                        domain="general",
                        domain_areas=cluster.suggested_domain_areas,
                        task_types=cluster.suggested_task_types,
                    )
                    try:
                        path = write_stub(
                            content, cluster.suggested_skill_name,
                            config.skills_dir, registry.mode,
                        )
                        st.success(f"Created {path.name}")
                        st.rerun()
                    except FileExistsError as exc:
                        st.error(str(exc))

    st.divider()

    # --- Dead skills ---
    st.subheader("Dead Skills")
    if not report.has_query_log:
        st.caption("Query log required for dead skill detection.")
    elif not report.dead_skills:
        st.info("No dead skills detected — all active skills are being used.")
    else:
        st.warning(f"{len(report.dead_skills)} active skill(s) never loaded in the query log.")
        for ds in report.dead_skills:
            with st.expander(f"{ds.skill.name} — {ds.suggestion}"):
                st.markdown(f"**Description:** {ds.skill.description}")
                st.markdown(f"**Domain:** {ds.skill.domain}")
                st.markdown(f"**Suggestion:** {ds.suggestion}")


def _render_query_log_setup_guide() -> None:
    """Show helpful instructions when no query log exists."""
    st.info(
        "**No query log configured.**\n\n"
        "To enable query clustering and dead skill detection, "
        "configure a query log in `skillkit.yaml`:\n\n"
        "```yaml\nquery_log: ./data/query_log.json\n```\n\n"
        "The query log should be a JSON array of objects:\n\n"
        "```json\n"
        '[\n'
        '  {\n'
        '    "timestamp": "2026-03-01T10:00:00",\n'
        '    "query": "How do I get a refund?",\n'
        '    "skill_loaded": "handle_refund",\n'
        '    "skill_candidates": ["handle_refund"]\n'
        '  },\n'
        '  {\n'
        '    "timestamp": "2026-03-01T10:05:00",\n'
        '    "query": "What is the weather?",\n'
        '    "skill_loaded": null,\n'
        '    "skill_candidates": []\n'
        '  }\n'
        ']\n'
        "```\n\n"
        "You can also add manual queries above to get started without "
        "agent instrumentation."
    )


# ---------------------------------------------------------------------------
# Page: Draft Queue (placeholder)
# ---------------------------------------------------------------------------

def page_draft_queue(registry: SkillRegistry, config: SkillKitConfig) -> None:
    st.title("Draft Queue")
    render_draft_queue(registry)


# ---------------------------------------------------------------------------
# Page: Settings
# ---------------------------------------------------------------------------

def page_settings(config: SkillKitConfig) -> None:
    st.title("Settings")

    st.subheader("Paths")
    path_data = {
        "Setting": ["Skills directory", "Coverage config", "Data directory", "Query log"],
        "Path": [
            str(config.skills_dir),
            str(config.coverage_config_path),
            str(config.data_dir),
            str(config.query_log_path) if config.query_log_path else "Not configured",
        ],
        "Exists": [
            config.skills_dir.exists(),
            config.coverage_config_path.exists(),
            config.data_dir.exists(),
            config.query_log_path.exists() if config.query_log_path else False,
        ],
    }
    st.table(path_data)

    st.subheader("Analysis Configuration")
    cfg_data = {
        "Setting": [
            "Embedding model",
            "Overlap high threshold",
            "Overlap moderate threshold",
            "Cluster threshold",
        ],
        "Value": [
            config.embedding_model,
            str(config.overlap_high),
            str(config.overlap_moderate),
            str(config.cluster_threshold),
        ],
    }
    st.table(cfg_data)


# ---------------------------------------------------------------------------
# Stub creation form (modal-like)
# ---------------------------------------------------------------------------

def _render_stub_form(registry: SkillRegistry, config: SkillKitConfig) -> None:
    """Render the new skill stub creation form."""
    st.subheader("Create New Skill")

    with st.form("stub_form"):
        name = st.text_input("Skill name (snake_case)")
        description = st.text_area("Description")
        domain = st.text_input("Domain", value="general")

        if st.form_submit_button("Create Stub"):
            if not name:
                st.error("Skill name is required.")
            else:
                content = generate_stub(
                    name=name,
                    description=description,
                    domain=domain,
                )
                try:
                    path = write_stub(content, name, config.skills_dir, registry.mode)
                    st.success(f"Created {path.name}")
                    st.session_state["show_stub_form"] = False
                    st.rerun()
                except FileExistsError as exc:
                    st.error(str(exc))

    if st.button("Cancel", key="cancel_stub"):
        st.session_state["show_stub_form"] = False
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for both `streamlit run` and the `skillkit` CLI command."""
    st.set_page_config(
        page_title="SkillKit",
        page_icon="\U0001f527",
        layout="wide",
    )

    # Load config and registry
    config_path = _get_config_path()
    config = _load_config(str(config_path))
    dir_hash = _skills_dir_hash(config.skills_dir)
    registry = _load_registry_cached(config, dir_hash)

    # Sidebar
    selected_page = _render_sidebar(registry, config)

    # Stub form overlay
    if st.session_state.get("show_stub_form"):
        _render_stub_form(registry, config)
        return

    # Welcome page if no skills
    if registry.total_count == 0:
        render_welcome_page()
        return

    # Route to page
    page_map = {
        "catalog": page_catalog,
        "coverage": page_coverage,
        "overlap": page_overlap,
        "gap_analysis": page_gap_analysis,
        "draft_queue": page_draft_queue,
    }

    if selected_page == "settings":
        page_settings(config)
    elif selected_page in page_map:
        page_map[selected_page](registry, config)


def _cli() -> None:
    """CLI entry point: launches Streamlit with this file."""
    import subprocess
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", __file__],
            check=True,
        )
    except FileNotFoundError:
        print("Error: Streamlit not found. Install with: pip install skillkit")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
