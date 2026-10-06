"""
Ingestion Service & Central Pipeline Coordinator.
Manages article repository, user preferences, background ingestion thread,
and analytical metrics.
"""

import time
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime

from services.news_cleaner import NewsCleaner
from services.nlp_processor import NLPProcessor
from services.emerging_detector import EmergingDetector
from services.news_collector import NewsCollector
from services.url_analyzer import URLAnalyzerService

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self):
        self._lock = threading.Lock()
        self.cleaner = NewsCleaner()
        self.nlp = NLPProcessor()
        self.emerging = EmergingDetector()
        self.collector = NewsCollector(self.cleaner, self.nlp, self.emerging)
        self.url_analyzer = URLAnalyzerService()

        # In-memory article registry
        self.articles: List[Dict] = []
        self._stats = {
            'total_ingested': 0,
            'total_duplicates_filtered': 0,
            'last_ingest_time': None,
            'pipeline_status': 'ACTIVE'
        }

        # User Dashboard Preferences (default configuration)
        self.user_preferences = {
            'active_categories': [
                'Technology', 'Politics', 'National', 'International',
                'Business', 'Science', 'Cybersecurity'
            ],
            'alert_sensitivity': 'Medium',  # Low, Medium, High
            'min_risk_alert': 65,
            'theme': 'dark',
            'refresh_interval_seconds': 30,
            'enable_breaking_alerts': True
        }

        # Initialize with seed articles
        self._initialize_corpus()

    def _initialize_corpus(self):
        """Bootstrap initial corpus from live RSS, GDELT, Reddit, and NewsAPI feeds."""
        logger.info("Bootstrapping live news corpus — this may take a few seconds…")
        initial = self.collector.collect_bootstrap_corpus()
        with self._lock:
            self.articles.extend(initial)
            self._stats['total_ingested'] = len(self.articles)
            self._stats['last_ingest_time'] = datetime.now().isoformat()
        logger.info("Ingestion Service ready with %d live articles", len(self.articles))

    def ingest_new_batch(self) -> int:
        """Trigger ingestion pull from registered feeds and public APIs."""
        try:
            new_items = self.collector.fetch_live_batch()
            if new_items:
                with self._lock:
                    for item in new_items:
                        # Insert at the beginning (most recent first)
                        self.articles.insert(0, item)
                    self._stats['total_ingested'] += len(new_items)
                    self._stats['last_ingest_time'] = datetime.now().isoformat()
            return len(new_items)
        except Exception as exc:
            logger.error("Ingestion batch failed: %s", exc)
            return 0

    def get_articles(
        self,
        category: Optional[str] = None,
        risk_level: Optional[str] = None,
        sentiment: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Query articles with multi-dimensional filtering for customizable dashboard.
        """
        with self._lock:
            results = list(self.articles)

        # 1. Filter by category
        if category and category.lower() != 'all':
            results = [a for a in results if a.get('category', '').lower() == category.lower()]

        # 2. Filter by risk level
        if risk_level and risk_level.lower() != 'all':
            results = [a for a in results if a.get('risk_level', '').lower() == risk_level.lower()]

        # 3. Filter by sentiment
        if sentiment and sentiment.lower() != 'all':
            results = [a for a in results if a.get('sentiment', {}).get('label', '').lower() == sentiment.lower()]

        # 4. Search query
        if search and search.strip():
            query = search.strip().lower()
            results = [
                a for a in results
                if query in a.get('title', '').lower()
                or query in a.get('content', '').lower()
                or any(query in t.lower() for t in a.get('topics', []))
            ]

        return results[:limit]

    def get_emerging_news(self) -> List[Dict]:
        """Get emerging and rapidly developing news spikes."""
        return self.emerging.detect_emerging_news()

    def get_alerts(self) -> List[Dict]:
        """Get live analytical alerts."""
        return self.emerging.get_alerts(limit=15)

    def get_analytical_insights(self) -> Dict:
        """Get synthesized analytical insights."""
        return self.emerging.get_analytical_insights()

    def get_pipeline_stats(self) -> Dict:
        """Compute real-time statistics for dashboard overview."""
        with self._lock:
            total = len(self.articles)
            cat_counts = {}
            for c in ['Technology', 'Politics', 'National', 'International', 'Business', 'Science', 'Cybersecurity']:
                cat_counts[c] = sum(1 for a in self.articles if a.get('category') == c)

            risk_distribution = {
                'low': sum(1 for a in self.articles if a.get('risk_level') == 'LOW RISK'),
                'moderate': sum(1 for a in self.articles if a.get('risk_level') == 'MODERATE RISK'),
                'elevated': sum(1 for a in self.articles if a.get('risk_level') == 'ELEVATED RISK'),
                'critical': sum(1 for a in self.articles if a.get('risk_level') == 'CRITICAL RISK')
            }

            avg_risk = round(sum(a.get('risk_score', 0) for a in self.articles) / max(total, 1), 1)

        return {
            'total_articles': total,
            'last_ingest_time': self._stats['last_ingest_time'],
            'pipeline_status': self._stats['pipeline_status'],
            'category_counts': cat_counts,
            'risk_distribution': risk_distribution,
            'average_risk_score': avg_risk,
            'active_sources': len(self.collector.registered_feeds) + 2
        }

    def get_user_preferences(self) -> Dict:
        """Retrieve user dashboard preferences."""
        return self.user_preferences

    def update_user_preferences(self, new_prefs: Dict) -> Dict:
        """Update and persist user dashboard customization."""
        self.user_preferences.update(new_prefs)
        return self.user_preferences

    def analyze_submitted_url(self, url: str) -> Dict:
        """Run full automated URL content scraping, summarization, and claim verification."""
        return self.url_analyzer.analyze_url(url)

    def get_source_status(self) -> Dict:
        """Return per-source live status (active, last_fetch, articles_total, error)."""
        return self.collector.get_source_status()
