from __future__ import annotations
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
from scipy.stats import rankdata
from skills.hackathon_novelty.models import HackathonSubmission

# Singleton — loads model once, reuses across calls
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-mpnet-base-v2")
    return _model


def fuse_text(submission: HackathonSubmission) -> str:
    """Idea text only — similarity/novelty based on core idea, not supporting materials."""
    return submission.idea_text


def compute_embeddings(texts: list[str]) -> np.ndarray:
    """Embed texts using sentence-transformers. Returns (N, D) array."""
    model = _get_model()
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
