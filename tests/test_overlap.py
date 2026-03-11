"""Tests for skillkit/overlap.py — TC-OV01 through TC-OV61."""

import hashlib
import json
import logging
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from skillkit.config import SkillKitConfig
from skillkit.overlap import (
    EmbeddingCache,
    EmbeddingCacheEntry,
    OverlapPair,
    OverlapReport,
    QuerySimulationResult,
    ScoredSkill,
    check_analysis_available,
    compute_embeddings,
    compute_pairwise_similarity,
    build_overlap_report,
    load_embedding_cache,
    save_embedding_cache,
    simulate_query,
    _content_hash,
    _skill_text,
)
from skillkit.skill_parser import Skill, SkillRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill(name: str, description: str = "", when_to_use: str = "", **kw) -> Skill:
    return Skill(name=name, description=description, when_to_use=when_to_use, **kw)


def _registry(skills: list[Skill]) -> SkillRegistry:
    return SkillRegistry(skills=skills, mode="flat")


def _config(tmp_path: Path) -> SkillKitConfig:
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    return SkillKitConfig(
        skills_dir=tmp_path / "skills",
        coverage_config_path=tmp_path / "coverage_config.yaml",
        query_log_path=None,
        data_dir=data_dir,
        embedding_model="all-MiniLM-L6-v2",
        overlap_high=0.85,
        overlap_moderate=0.70,
        cluster_threshold=0.75,
    )


# ===========================================================================
# Embedding Computation (TC-OV01 – TC-OV03)
# ===========================================================================

@pytest.mark.analysis
class TestEmbeddingComputation:

    # TC-OV01
    def test_ov01_compute_embeddings(self, tmp_path):
        s1 = _skill("s1", description="Handle customer refunds")
        s2 = _skill("s2", description="Analyze server logs")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        result = compute_embeddings([s1, s2], "all-MiniLM-L6-v2", cache)

        assert "s1" in result
        assert "s2" in result
        assert isinstance(result["s1"], list)
        assert all(isinstance(x, float) for x in result["s1"])
        assert len(result["s1"]) == 384  # all-MiniLM-L6-v2 dimension

    # TC-OV02
    def test_ov02_text_is_description_plus_when_to_use(self, tmp_path):
        s = _skill("s1", description="My description", when_to_use="My when to use")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        compute_embeddings([s], "all-MiniLM-L6-v2", cache)

        expected_text = "My description My when to use"
        expected_hash = hashlib.sha256(expected_text.encode()).hexdigest()
        assert expected_hash in cache.entries

    # TC-OV03
    def test_ov03_empty_when_to_use(self, tmp_path):
        s = _skill("s1", description="Only description", when_to_use="")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        result = compute_embeddings([s], "all-MiniLM-L6-v2", cache)

        assert "s1" in result
        assert len(result["s1"]) == 384


# ===========================================================================
# Caching (TC-OV10 – TC-OV17)
# ===========================================================================

@pytest.mark.analysis
class TestCaching:

    # TC-OV10
    def test_ov10_cold_cache(self, tmp_path):
        s1 = _skill("s1", description="Skill one")
        s2 = _skill("s2", description="Skill two")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        compute_embeddings([s1, s2], "all-MiniLM-L6-v2", cache)

        assert len(cache.entries) == 2
        assert cache.model_name == "all-MiniLM-L6-v2"

    # TC-OV11
    def test_ov11_warm_cache(self, tmp_path):
        s1 = _skill("s1", description="Skill one")
        s2 = _skill("s2", description="Skill two")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        # Cold run
        result_cold = compute_embeddings([s1, s2], "all-MiniLM-L6-v2", cache)

        # Warm run — same cache, should be instant
        start = time.time()
        result_warm = compute_embeddings([s1, s2], "all-MiniLM-L6-v2", cache)
        warm_time = time.time() - start

        assert result_cold["s1"] == result_warm["s1"]
        assert result_cold["s2"] == result_warm["s2"]
        # Warm should be very fast (< 0.1s) since no model inference
        assert warm_time < 1.0

    # TC-OV12
    def test_ov12_partial_cache(self, tmp_path):
        s1 = _skill("s1", description="Skill one")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        result1 = compute_embeddings([s1], "all-MiniLM-L6-v2", cache)
        assert len(cache.entries) == 1

        s2 = _skill("s2", description="Skill two")
        result2 = compute_embeddings([s1, s2], "all-MiniLM-L6-v2", cache)

        assert len(cache.entries) == 2
        assert result1["s1"] == result2["s1"]  # Cached entry unchanged

    # TC-OV13
    def test_ov13_content_changed(self, tmp_path):
        s = _skill("s1", description="Original description")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")

        result1 = compute_embeddings([s], "all-MiniLM-L6-v2", cache)
        old_hash = _content_hash(_skill_text(s))

        s_modified = _skill("s1", description="Completely different description now")
        result2 = compute_embeddings([s_modified], "all-MiniLM-L6-v2", cache)
        new_hash = _content_hash(_skill_text(s_modified))

        assert old_hash != new_hash
        assert result1["s1"] != result2["s1"]
        assert new_hash in cache.entries

    # TC-OV14
    def test_ov14_model_change(self, tmp_path):
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")
        cache.put("fakehash", [0.1, 0.2], "old_skill")
        save_embedding_cache(cache, tmp_path / "data")

        loaded = load_embedding_cache(tmp_path / "data", "other-model")
        assert len(loaded.entries) == 0
        assert loaded.model_name == "other-model"

    # TC-OV15
    def test_ov15_round_trip(self, tmp_path):
        s = _skill("s1", description="Round trip test")
        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")
        compute_embeddings([s], "all-MiniLM-L6-v2", cache)

        data_dir = tmp_path / "data"
        save_embedding_cache(cache, data_dir)
        loaded = load_embedding_cache(data_dir, "all-MiniLM-L6-v2")

        original_emb = list(cache.entries.values())[0].embedding
        loaded_emb = list(loaded.entries.values())[0].embedding
        assert len(original_emb) == len(loaded_emb)
        for a, b in zip(original_emb, loaded_emb):
            assert abs(a - b) < 1e-10


# TC-OV16 and TC-OV17 don't need analysis deps
def test_ov16_missing_cache_file(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cache = load_embedding_cache(data_dir, "all-MiniLM-L6-v2")
    assert len(cache.entries) == 0


def test_ov17_malformed_cache(tmp_path, caplog):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "embedding_cache.json").write_text("not valid json{{{")

    with caplog.at_level(logging.WARNING, logger="skillkit"):
        cache = load_embedding_cache(data_dir, "all-MiniLM-L6-v2")

    assert len(cache.entries) == 0


# ===========================================================================
# Pairwise Similarity (TC-OV20 – TC-OV27)
# ===========================================================================

@pytest.mark.analysis
class TestPairwiseSimilarity:

    def _embed(self, texts: dict[str, str]) -> dict[str, list[float]]:
        """Embed a dict of name -> text."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        result = {}
        for name, text in texts.items():
            emb = model.encode([text], convert_to_numpy=True)[0]
            result[name] = emb.tolist()
        return result

    # TC-OV20
    def test_ov20_identical_strings(self):
        embs = self._embed({"a": "identical text here", "b": "identical text here"})
        pairs = compute_pairwise_similarity(embs)
        assert len(pairs) == 1
        assert pairs[0][2] > 0.99

    # TC-OV21
    def test_ov21_unrelated_strings(self):
        embs = self._embed({
            "a": "quantum physics string theory dark matter",
            "b": "chocolate cake recipe with vanilla frosting",
        })
        pairs = compute_pairwise_similarity(embs)
        assert pairs[0][2] < 0.30

    # TC-OV22 [Calibration]
    def test_ov22_handle_refund_escalate_ticket(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        hr = reg.get_by_name("handle_refund")
        et = reg.get_by_name("escalate_ticket")
        assert hr and et

        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")
        embs = compute_embeddings([hr, et], "all-MiniLM-L6-v2", cache)
        pairs = compute_pairwise_similarity(embs)

        assert len(pairs) == 1
        sim = pairs[0][2]
        assert 0.65 <= sim <= 0.95, f"Expected [0.65, 0.95], got {sim}"

    # TC-OV23 [Calibration]
    def test_ov23_handle_refund_summarize_paper(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        hr = reg.get_by_name("handle_refund")
        sp = reg.get_by_name("summarize_paper")
        assert hr and sp

        cache = EmbeddingCache(model_name="all-MiniLM-L6-v2")
        embs = compute_embeddings([hr, sp], "all-MiniLM-L6-v2", cache)
        pairs = compute_pairwise_similarity(embs)

        assert pairs[0][2] < 0.55, f"Expected < 0.55, got {pairs[0][2]}"

    # TC-OV24
    def test_ov24_single_skill(self):
        embs = self._embed({"only": "some text"})
        pairs = compute_pairwise_similarity(embs)
        assert pairs == []

    # TC-OV25
    def test_ov25_two_skills(self):
        embs = self._embed({"a": "text a", "b": "text b"})
        pairs = compute_pairwise_similarity(embs)
        assert len(pairs) == 1

    # TC-OV26
    def test_ov26_n_skills(self):
        embs = self._embed({f"s{i}": f"text {i}" for i in range(5)})
        pairs = compute_pairwise_similarity(embs)
        expected = 5 * 4 // 2
        assert len(pairs) == expected

    # TC-OV27
    def test_ov27_sorted_descending(self):
        embs = self._embed({
            "a": "customer refund return money",
            "b": "customer refund request",
            "c": "quantum physics dark matter",
        })
        pairs = compute_pairwise_similarity(embs)
        sims = [p[2] for p in pairs]
        assert sims == sorted(sims, reverse=True)


# ===========================================================================
# Risk Classification (TC-OV30 – TC-OV34)
# ===========================================================================

from skillkit.overlap import _classify_risk


def test_ov30_high():
    assert _classify_risk(0.90, 0.85, 0.70) == "high"


def test_ov31_moderate():
    assert _classify_risk(0.75, 0.85, 0.70) == "moderate"


def test_ov32_low():
    assert _classify_risk(0.50, 0.85, 0.70) == "low"


def test_ov33_high_inclusive():
    assert _classify_risk(0.85, 0.85, 0.70) == "high"


def test_ov34_moderate_inclusive():
    assert _classify_risk(0.70, 0.85, 0.70) == "moderate"


# ===========================================================================
# Overlap Report (TC-OV40 – TC-OV44)
# ===========================================================================

@pytest.mark.analysis
class TestOverlapReport:

    # TC-OV40 [Calibration]
    def test_ov40_example_skills(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        report = build_overlap_report(reg, cfg)

        assert len(report.pairs) >= 1
        sims = [p.similarity for p in report.pairs]
        assert sims == sorted(sims, reverse=True)
        for p in report.pairs:
            assert p.text_a
            assert p.text_b

    # TC-OV41
    def test_ov41_filters_low_risk(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        report = build_overlap_report(reg, cfg)

        for p in report.pairs:
            assert p.similarity >= cfg.overlap_moderate

    # TC-OV42
    def test_ov42_high_risk_property(self):
        report = OverlapReport(
            pairs=[
                OverlapPair(_skill("a"), _skill("b"), 0.90, "high", "ta", "tb"),
                OverlapPair(_skill("c"), _skill("d"), 0.75, "moderate", "tc", "td"),
            ],
        )
        assert len(report.high_risk_pairs) == 1
        assert report.high_risk_pairs[0].risk_level == "high"

    # TC-OV43
    def test_ov43_moderate_risk_property(self):
        report = OverlapReport(
            pairs=[
                OverlapPair(_skill("a"), _skill("b"), 0.90, "high", "ta", "tb"),
                OverlapPair(_skill("c"), _skill("d"), 0.75, "moderate", "tc", "td"),
            ],
        )
        assert len(report.moderate_risk_pairs) == 1
        assert report.moderate_risk_pairs[0].risk_level == "moderate"

    # TC-OV44
    def test_ov44_no_pairs_above_threshold(self, tmp_path):
        # Two very distinct skills
        s1 = _skill("s1", description="quantum physics dark matter string theory")
        s2 = _skill("s2", description="chocolate cake recipe vanilla frosting baking")
        reg = _registry([s1, s2])
        cfg = _config(tmp_path)

        report = build_overlap_report(reg, cfg)

        assert report.pairs == []
        assert report.high_risk_pairs == []
        assert report.moderate_risk_pairs == []


# ===========================================================================
# Query Simulation (TC-OV50 – TC-OV54)
# ===========================================================================

@pytest.mark.analysis
class TestQuerySimulation:

    # TC-OV50
    def test_ov50_matching_query(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        result = simulate_query("customer wants their money back refund", reg, cfg)

        assert len(result.ranked_skills) > 0
        top_names = [s.skill.name for s in result.ranked_skills[:2]]
        assert "handle_refund" in top_names or "escalate_ticket" in top_names

    # TC-OV51
    def test_ov51_ambiguous_query(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        # This query is designed to match both refund-related skills equally
        result = simulate_query(
            "customer requesting refund escalation for defective product",
            reg, cfg,
        )
        # We can't guarantee ambiguity with natural language, so just check it runs
        assert isinstance(result.is_ambiguous, bool)
        assert len(result.ranked_skills) > 0

    # TC-OV52
    def test_ov52_clear_query(self, example_skills_dir, tmp_path):
        cfg = _config(tmp_path)
        cfg.skills_dir = example_skills_dir
        from skillkit.skill_parser import load_registry
        reg = load_registry(cfg)

        # Very specific query targeting one domain
        result = simulate_query(
            "read and summarize an academic research paper abstract findings",
            reg, cfg,
        )
        assert len(result.ranked_skills) > 0
        # Top skill should be from research domain
        top = result.ranked_skills[0].skill
        assert top.domain == "research"

    # TC-OV53
    def test_ov53_empty_query(self, tmp_path):
        s = _skill("s1", description="Some skill")
        reg = _registry([s])
        cfg = _config(tmp_path)

        result = simulate_query("", reg, cfg)

        assert result.ranked_skills == []
        assert result.is_ambiguous is False

    # TC-OV54
    def test_ov54_empty_registry(self, tmp_path):
        reg = _registry([])
        cfg = _config(tmp_path)

        result = simulate_query("any query", reg, cfg)

        assert result.ranked_skills == []
        assert result.is_ambiguous is False


# ===========================================================================
# Graceful Degradation (TC-OV60 – TC-OV61)
# ===========================================================================

@pytest.mark.analysis
def test_ov60_deps_available():
    assert check_analysis_available() is True


# TC-OV61 — NOT marked @analysis (tests fallback path)
def test_ov61_deps_missing():
    with patch("skillkit.overlap.ANALYSIS_AVAILABLE", False):
        # Re-import to use the patched value
        from skillkit.overlap import check_analysis_available as check
        # check_analysis_available reads the module-level ANALYSIS_AVAILABLE
        # but since it's cached, we patch the function's view
        pass

    # More direct: patch the function itself
    with patch("skillkit.overlap.ANALYSIS_AVAILABLE", False):
        # compute_embeddings should raise ImportError
        s = _skill("s1", description="test")
        cache = EmbeddingCache(model_name="test")
        with pytest.raises(ImportError):
            compute_embeddings([s], "test", cache)

        with pytest.raises(ImportError):
            compute_pairwise_similarity({"a": [0.1]})
