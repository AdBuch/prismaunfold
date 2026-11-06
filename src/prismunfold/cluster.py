"""Group articles that report on the same event.

MVP approach: title-token Jaccard similarity within a time window, same language only.
Union-find over all pairs, O(n^2), which is fine for a daily pool of a few hundred articles.
Embeddings and cross-language linking come later behind the same function boundary.
"""

from __future__ import annotations

from datetime import timedelta

from .models import Article
from .normalize import tokens


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_articles(
    articles: list[Article], threshold: float, window: timedelta
) -> list[list[Article]]:
    """Return groups of articles, each group sorted oldest first."""
    n = len(articles)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    toks = [tokens(a.title) for a in articles]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = articles[i], articles[j]
            if a.language != b.language:
                continue
            if abs(a.published_at - b.published_at) > window:
                continue
            if jaccard(toks[i], toks[j]) >= threshold:
                parent[find(i)] = find(j)

    groups: dict[int, list[Article]] = {}
    for i, article in enumerate(articles):
        groups.setdefault(find(i), []).append(article)
    return [sorted(g, key=lambda x: x.published_at) for g in groups.values()]
