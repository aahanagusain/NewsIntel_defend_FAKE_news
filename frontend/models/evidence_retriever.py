"""
Modular Evidence Retriever Engine for Evidence-Grounded Fake News Verification.
Provides abstraction supporting local corpus semantic retrieval and optional web search APIs.
"""

import sys
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))
import config

logger = logging.getLogger(__name__)


class AbstractEvidenceRetriever(ABC):
    """Abstract interface for evidence retrieval implementations."""

    @abstractmethod
    def retrieve_evidence(self, claim: str, top_k: int = 3) -> List[Dict]:
        pass


class LocalVectorRetriever(AbstractEvidenceRetriever):
    """
    Local TF-IDF / Vector Semantic Evidence Retriever.
    Indexes local verified facts from data/evidence_corpus and sample articles.
    Operates 100% offline without external API dependencies.
    """

    def __init__(self, corpus_path: Path = None):
        self.corpus_path = corpus_path or (config.EVIDENCE_CORPUS_DIR / 'evidence_passages.json')
        self.passages: List[Dict] = []
        self._load_corpus()

    def _load_corpus(self):
        """Load corpus JSON passages."""
        if self.corpus_path.exists():
            try:
                with open(self.corpus_path, 'r', encoding='utf-8') as f:
                    self.passages = json.load(f)
            except Exception as e:
                logger.error("Failed to load evidence corpus: %s", e)

        if not self.passages:
            self.passages = [
                {
                    "id": "default_01",
                    "topic": "Space Science",
                    "text": "NASA and international astronomical bodies publish peer-reviewed spectroscopic measurements of exoplanets and solar system atmospheric pressures.",
                    "source": "NASA Official Factsheet",
                    "credibility_score": 0.95
                },
                {
                    "id": "default_02",
                    "topic": "Finance & Currency",
                    "text": "Central bank legal tender currencies remain valid unless formally statutory acts specify legal demonetization with public bank exchange.",
                    "source": "Reserve Bank Financial Regulations",
                    "credibility_score": 0.95
                }
            ]
        logger.info("Loaded %d local evidence passages", len(self.passages))

    def _compute_jaccard_similarity(self, str1: str, str2: str) -> float:
        """Fallback lightweight word-overlap similarity when sklearn is not present."""
        w1 = set(str1.lower().split())
        w2 = set(str2.lower().split())
        if not w1 or not w2:
            return 0.0
        return len(w1.intersection(w2)) / float(len(w1.union(w2)))

    def retrieve_evidence(self, claim: str, top_k: int = 3) -> List[Dict]:
        """Retrieve top-K evidence passages matching claim via semantic similarity."""
        if not claim or not self.passages:
            return []

        try:
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                
                corpus_texts = [p['text'] for p in self.passages]
                vectorizer = TfidfVectorizer(stop_words='english')
                tfidf_matrix = vectorizer.fit_transform(corpus_texts)
                claim_vec = vectorizer.transform([claim])
                similarities = cosine_similarity(claim_vec, tfidf_matrix)[0]
                
                results = []
                for idx, score in enumerate(similarities):
                    if score > 0.02:
                        passage = self.passages[idx].copy()
                        passage['similarity_score'] = round(float(score), 4)
                        results.append(passage)
                results.sort(key=lambda x: x['similarity_score'], reverse=True)
                return results[:top_k]

            except ImportError:
                # Fallback to Jaccard similarity if sklearn is loading
                results = []
                for p in self.passages:
                    score = self._compute_jaccard_similarity(claim, p['text'])
                    if score > 0.01:
                        passage = p.copy()
                        passage['similarity_score'] = round(float(score), 4)
                        results.append(passage)
                results.sort(key=lambda x: x['similarity_score'], reverse=True)
                return results[:top_k]

        except Exception as exc:
            logger.error("Evidence retrieval failed for claim '%s': %s", claim, exc)
            return []


class ExternalSearchRetriever(AbstractEvidenceRetriever):
    """
    Optional External Web Search Evidence Retriever.
    Queries online news/fact-checking sources when enabled in .env.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.NEWSAPI_KEY
        self.local_fallback = LocalVectorRetriever()

    def retrieve_evidence(self, claim: str, top_k: int = 3) -> List[Dict]:
        """Query NewsAPI or fallback to local vector retriever."""
        if not config.USE_ONLINE_SEARCH or not self.api_key:
            logger.info("Online search disabled or API key missing; using local evidence retriever.")
            return self.local_fallback.retrieve_evidence(claim, top_k)

        try:
            import requests
            url = f"https://newsapi.org/v2/everything?q={requests.utils.quote(claim[:100])}&sortBy=relevance&pageSize={top_k}&apiKey={self.api_key}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                articles = resp.json().get('articles', [])
                results = []
                for a in articles:
                    results.append({
                        'id': a.get('url', ''),
                        'topic': 'News Article',
                        'text': (a.get('title', '') + '. ' + a.get('description', '')).strip(),
                        'source': a.get('source', {}).get('name', 'External Web Search'),
                        'credibility_score': 0.85,
                        'similarity_score': 0.80
                    })
                if results:
                    return results

        except Exception as exc:
            logger.warning("External web search failed: %s; falling back to local retriever", exc)

        return self.local_fallback.retrieve_evidence(claim, top_k)


class EvidenceRetriever:
    """Unified Evidence Retriever Factory."""

    def __init__(self):
        if config.USE_ONLINE_SEARCH:
            self.retriever = ExternalSearchRetriever()
        else:
            self.retriever = LocalVectorRetriever()

    def retrieve_evidence(self, claim: str, top_k: int = 3) -> List[Dict]:
        return self.retriever.retrieve_evidence(claim, top_k)


if __name__ == '__main__':
    retriever = EvidenceRetriever()
    claim = "Humans can comfortably survive on Venus surface without oxygen gear"
    evidence = retriever.retrieve_evidence(claim, top_k=2)
    print("Retrieved Evidence for Claim:")
    for e in evidence:
        print(f"- [{e['source']}] (Score: {e['similarity_score']}): {e['text']}")
