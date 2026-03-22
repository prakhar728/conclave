from __future__ import annotations
import hashlib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
from scipy.stats import rankdata
from skills.hackathon_novelty.models import HackathonSubmission

# Singleton — loads model once, reuses across calls
_model: SentenceTransformer | None = None
_model_load_failed = False
_FALLBACK_DIM = 256


def _get_model() -> SentenceTransformer | None:
    global _model, _model_load_failed
    if _model_load_failed:
        return None
    if _model is None:
        try:
            # Keep the deterministic pipeline runnable in offline CI/local environments.
            _model = SentenceTransformer("all-mpnet-base-v2", local_files_only=True)
        except Exception:
            _model_load_failed = True
            return None
    return _model


def _fallback_embeddings(texts: list[str]) -> np.ndarray:
    """Deterministic offline embedding fallback based on token hashing."""
    embeddings = np.zeros((len(texts), _FALLBACK_DIM), dtype=np.float32)
    for row, text in enumerate(texts):
        tokens = text.lower().split()
        if not tokens:
            tokens = [""]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % _FALLBACK_DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            embeddings[row, index] += sign * weight

        norm = np.linalg.norm(embeddings[row])
        if norm > 0:
            embeddings[row] /= norm

    return embeddings


def fuse_text(submission: HackathonSubmission) -> str:
    """Idea text only — similarity/novelty based on core idea, not supporting materials."""
    return submission.idea_text


def compute_embeddings(texts: list[str]) -> np.ndarray:
    """Embed texts using sentence-transformers. Returns (N, D) array."""
    model = _get_model()
    if model is None:
        return _fallback_embeddings(texts)
    return model.encode(texts, show_progress_bar=False)


def pairwise_similarity(embeddings: np.ndarray) -> np.ndarray:
    """Compute (N, N) cosine similarity matrix."""
    return cosine_similarity(embeddings)


def compute_novelty_scores(sim_matrix: np.ndarray) -> np.ndarray:
    """Novelty = 1 - max(similarity to any OTHER submission). Diagonal masked."""
    masked = sim_matrix.copy()
    np.fill_diagonal(masked, -1.0)
    max_sim = masked.max(axis=1)
    novelty = 1.0 - max_sim
    return np.clip(novelty, 0.0, 1.0)


def compute_percentiles(novelty_scores: np.ndarray) -> np.ndarray:
    """Rank-based percentile. Higher novelty -> higher percentile."""
    ranks = rankdata(novelty_scores, method="average")
    n = len(novelty_scores)
    percentiles = (ranks / n) * 100.0
    return percentiles


def cluster_submissions(embeddings: np.ndarray) -> list[str]:
    """KMeans clustering. Auto-select k. Return generic labels."""
    n = embeddings.shape[0]
    k = min(n, max(2, n // 3))
    if n < 2:
        return ["Uncategorized"] * n
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    label_names = [f"Cluster_{i}" for i in range(k)]
    return [label_names[l] for l in labels]


def run_deterministic(
    submissions: list[HackathonSubmission],
    guidelines: str = "",
    criteria: dict[str, float] | None = None,
) -> dict:
    """
    Full deterministic pipeline. Returns dict with:
    - embeddings: np.ndarray (N, D)
    - sim_matrix: np.ndarray (N, N)
    - novelty_scores: np.ndarray (N,)
    - percentiles: np.ndarray (N,)       — internal, used by triage_context
    - clusters: list[str] (N,)           — internal, used by triage_context
    - submission_ids: list[str] (N,)
    """
    texts = [fuse_text(s) for s in submissions]
    embeddings = compute_embeddings(texts)
    sim_matrix = pairwise_similarity(embeddings)
    novelty_scores = compute_novelty_scores(sim_matrix)
    percentiles = compute_percentiles(novelty_scores)
    clusters = cluster_submissions(embeddings)

    return {
        "embeddings": embeddings,
        "sim_matrix": sim_matrix,
        "novelty_scores": novelty_scores,
        "percentiles": percentiles,
        "clusters": clusters,
        "submission_ids": [s.submission_id for s in submissions],
    }
