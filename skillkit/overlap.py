"""Embedding computation, caching, similarity calculations, and query simulation."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import SkillKitConfig
from .skill_parser import Skill, SkillRegistry

logger = logging.getLogger("skillkit")


# ---------------------------------------------------------------------------
# Optional dependency check
# ---------------------------------------------------------------------------

def _check_analysis_deps() -> bool:
    """Returns True if analysis dependencies are available."""
    try:
        import sentence_transformers  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


ANALYSIS_AVAILABLE = _check_analysis_deps()


def check_analysis_available() -> bool:
    """Public API: returns True if sentence-transformers and numpy are importable."""
    return ANALYSIS_AVAILABLE


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingCacheEntry:
    content_hash: str
    embedding: list[float]
    skill_name: str


@dataclass
class EmbeddingCache:
    entries: dict[str, EmbeddingCacheEntry] = field(default_factory=dict)
    model_name: str = ""

    def get(self, content_hash: str) -> Optional[list[float]]:
        entry = self.entries.get(content_hash)
        return entry.embedding if entry else None

    def put(self, content_hash: str, embedding: list[float], skill_name: str) -> None:
        self.entries[content_hash] = EmbeddingCacheEntry(
            content_hash=content_hash,
            embedding=embedding,
            skill_name=skill_name,
        )

    def needs_recompute(self, content_hash: str) -> bool:
        return content_hash not in self.entries


@dataclass
class OverlapPair:
    """A pair of skills with measured similarity."""
    skill_a: Skill
    skill_b: Skill
    similarity: float
    risk_level: str
    text_a: str
    text_b: str


@dataclass
class OverlapReport:
    """All pairwise overlaps above the moderate threshold."""
    pairs: list[OverlapPair] = field(default_factory=list)
    high_threshold: float = 0.85
    moderate_threshold: float = 0.70

    @property
    def high_risk_pairs(self) -> list[OverlapPair]:
        return [p for p in self.pairs if p.risk_level == "high"]

    @property
    def moderate_risk_pairs(self) -> list[OverlapPair]:
        return [p for p in self.pairs if p.risk_level == "moderate"]


@dataclass
class ScoredSkill:
    """A skill with a similarity score to a query."""
    skill: Skill
    score: float


@dataclass
class QuerySimulationResult:
    """Result of simulating a query against all skills."""
    query: str
    ranked_skills: list[ScoredSkill] = field(default_factory=list)
    is_ambiguous: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_text(skill: Skill) -> str:
    """The text used for embedding: description + ' ' + when_to_use."""
    return skill.description + " " + skill.when_to_use


def _content_hash(text: str) -> str:
    """SHA-256 hash of the embedding source text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _classify_risk(similarity: float, high: float, moderate: float) -> str:
    if similarity >= high:
        return "high"
    if similarity >= moderate:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Cache persistence
# ---------------------------------------------------------------------------

def load_embedding_cache(data_dir: Path, model_name: str) -> EmbeddingCache:
    """Load cache from data/embedding_cache.json. Returns empty cache if
    file missing or model_name doesn't match stored model."""
    path = data_dir / "embedding_cache.json"
    if not path.exists():
        return EmbeddingCache(model_name=model_name)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load embedding cache from %s: %s", path, exc)
        return EmbeddingCache(model_name=model_name)

    if not isinstance(raw, dict):
        logger.warning("Embedding cache at %s is not a dict, starting fresh", path)
        return EmbeddingCache(model_name=model_name)

    stored_model = raw.get("model", "")
    if stored_model != model_name:
        logger.info(
            "Embedding model changed (%s → %s), invalidating cache",
            stored_model, model_name,
        )
        return EmbeddingCache(model_name=model_name)

    entries: dict[str, EmbeddingCacheEntry] = {}
    for key, val in raw.get("entries", {}).items():
        try:
            entries[key] = EmbeddingCacheEntry(
                content_hash=val["content_hash"],
                embedding=val["embedding"],
                skill_name=val.get("skill_name", ""),
            )
        except (KeyError, TypeError):
            continue

    return EmbeddingCache(entries=entries, model_name=model_name)


def save_embedding_cache(cache: EmbeddingCache, data_dir: Path) -> None:
    """Write cache to data/embedding_cache.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "embedding_cache.json"
    data = {
        "model": cache.model_name,
        "entries": {
            key: {
                "content_hash": entry.content_hash,
                "embedding": entry.embedding,
                "skill_name": entry.skill_name,
            }
            for key, entry in cache.entries.items()
        },
    }
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Model cache
# ---------------------------------------------------------------------------

_model_cache: dict[str, object] = {}


def _get_model(model_name: str):
    """Return a cached SentenceTransformer instance."""
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


# ---------------------------------------------------------------------------
# Embedding computation
# ---------------------------------------------------------------------------

def compute_embeddings(
    skills: list[Skill],
    model_name: str,
    cache: EmbeddingCache,
) -> dict[str, list[float]]:
    """Compute or retrieve cached embeddings for each skill.

    Text per skill = description + " " + when_to_use
    Key = SHA-256 of that text.

    Returns dict mapping skill.name -> embedding vector.
    Raises ImportError if analysis deps not available.
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError(
            "Analysis dependencies (sentence-transformers, numpy) are required. "
            "Install with: pip install skillkit[analysis]"
        )

    result: dict[str, list[float]] = {}
    texts_to_encode: list[str] = []
    names_to_encode: list[str] = []
    hashes_to_encode: list[str] = []

    for skill in skills:
        text = _skill_text(skill)
        h = _content_hash(text)
        cached = cache.get(h)
        if cached is not None:
            result[skill.name] = cached
        else:
            texts_to_encode.append(text)
            names_to_encode.append(skill.name)
            hashes_to_encode.append(h)

    if texts_to_encode:
        model = _get_model(model_name)
        new_embeddings = model.encode(texts_to_encode, convert_to_numpy=True)
        for i, emb in enumerate(new_embeddings):
            emb_list = emb.tolist()
            result[names_to_encode[i]] = emb_list
            cache.put(hashes_to_encode[i], emb_list, names_to_encode[i])

    return result


# ---------------------------------------------------------------------------
# Pairwise similarity
# ---------------------------------------------------------------------------

def compute_pairwise_similarity(
    embeddings: dict[str, list[float]],
) -> list[tuple[str, str, float]]:
    """Cosine similarity for all skill pairs.
    Returns list of (name_a, name_b, similarity) sorted by similarity desc.
    """
    if not ANALYSIS_AVAILABLE:
        raise ImportError("Analysis dependencies required.")

    import numpy as np

    names = sorted(embeddings.keys())
    if len(names) < 2:
        return []

    vectors = np.array([embeddings[n] for n in names])
    # Normalize
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normalized = vectors / norms

    # Cosine similarity matrix
    sim_matrix = normalized @ normalized.T

    pairs: list[tuple[str, str, float]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pairs.append((names[i], names[j], float(sim_matrix[i, j])))

    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


# ---------------------------------------------------------------------------
# Overlap report
# ---------------------------------------------------------------------------

def build_overlap_report(
    registry: SkillRegistry,
    config: SkillKitConfig,
) -> OverlapReport:
    """Full overlap analysis pipeline."""
    cache = load_embedding_cache(config.data_dir, config.embedding_model)
    active = registry.get_active_skills()
    embeddings = compute_embeddings(active, config.embedding_model, cache)
    save_embedding_cache(cache, config.data_dir)

    all_pairs = compute_pairwise_similarity(embeddings)

    # Build a name -> skill lookup
    skill_map = {s.name: s for s in active}
    text_map = {s.name: _skill_text(s) for s in active}

    overlap_pairs: list[OverlapPair] = []
    for name_a, name_b, sim in all_pairs:
        risk = _classify_risk(sim, config.overlap_high, config.overlap_moderate)
        if risk == "low":
            continue
        overlap_pairs.append(OverlapPair(
            skill_a=skill_map[name_a],
            skill_b=skill_map[name_b],
            similarity=sim,
            risk_level=risk,
            text_a=text_map[name_a],
            text_b=text_map[name_b],
        ))

    return OverlapReport(
        pairs=overlap_pairs,
        high_threshold=config.overlap_high,
        moderate_threshold=config.overlap_moderate,
    )


# ---------------------------------------------------------------------------
# Query simulation
# ---------------------------------------------------------------------------

def simulate_query(
    query: str,
    registry: SkillRegistry,
    config: SkillKitConfig,
) -> QuerySimulationResult:
    """Embed the query, rank all active skills by similarity."""
    active = registry.get_active_skills()
    if not active or not query.strip():
        return QuerySimulationResult(query=query, ranked_skills=[], is_ambiguous=False)

    if not ANALYSIS_AVAILABLE:
        raise ImportError("Analysis dependencies required.")

    import numpy as np

    cache = load_embedding_cache(config.data_dir, config.embedding_model)
    skill_embeddings = compute_embeddings(active, config.embedding_model, cache)
    save_embedding_cache(cache, config.data_dir)

    model = _get_model(config.embedding_model)
    query_embedding = model.encode([query], convert_to_numpy=True)[0]

    q_vec = np.array(query_embedding)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return QuerySimulationResult(query=query, ranked_skills=[], is_ambiguous=False)
    q_vec = q_vec / q_norm

    scored: list[ScoredSkill] = []
    for skill in active:
        s_vec = np.array(skill_embeddings[skill.name])
        s_norm = np.linalg.norm(s_vec)
        if s_norm == 0:
            sim = 0.0
        else:
            sim = float(np.dot(q_vec, s_vec / s_norm))
        scored.append(ScoredSkill(skill=skill, score=sim))

    scored.sort(key=lambda x: x.score, reverse=True)

    is_ambiguous = False
    if len(scored) >= 2:
        is_ambiguous = (scored[0].score - scored[1].score) <= 0.05

    return QuerySimulationResult(
        query=query,
        ranked_skills=scored,
        is_ambiguous=is_ambiguous,
    )
