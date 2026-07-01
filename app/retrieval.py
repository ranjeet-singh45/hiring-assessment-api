"""Lightweight TF-IDF retrieval over the normalized catalog. Avoids any
external vector DB dependency so the service has no extra infra to manage."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .catalog import catalog


class Retriever:
    def __init__(self):
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.docs: list[dict] = []

    def build(self):
        self.docs = catalog.items
        corpus = [
            f"{d['name']} {d['description']} {' '.join(d.get('test_type', []))} "
            f"{' '.join(d.get('job_levels', []))}"
            for d in self.docs
        ]
        if not corpus:
            self.vectorizer = None
            self.matrix = None
            return
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, k: int = 10, test_types: list[str] | None = None) -> list[dict]:
        if not query or self.vectorizer is None or not self.docs:
            return []
        qvec = self.vectorizer.transform([query])
        sims = cosine_similarity(qvec, self.matrix)[0]
        ranked_idx = sims.argsort()[::-1]

        results = []
        for idx in ranked_idx:
            if sims[idx] <= 0:
                break
            item = self.docs[idx]
            if test_types:
                item_types = set(t.upper() for t in item.get("test_type", []))
                if not item_types.intersection(set(t.upper() for t in test_types)):
                    continue
            results.append({**item, "score": float(sims[idx])})
            if len(results) >= k:
                break
        return results


retriever = Retriever()
