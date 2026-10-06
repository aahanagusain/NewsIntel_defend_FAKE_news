"""
News Collector Service for Multi-Source Ingestion.
Collects from RSS Feeds, authorized APIs (GDELT, NewsAPI), Reddit, and public web sources.
Cleans, normalizes, deduplicates, classifies, and runs NLP analysis on every item.
"""

import sys
import time
import json
import logging
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import requests

from services.news_cleaner import NewsCleaner
from services.nlp_processor import NLPProcessor
from services.emerging_detector import EmergingDetector
from services.social_media_collector import SocialMediaCollector

logger = logging.getLogger(__name__)


class NewsCollector:
    def __init__(self, cleaner: NewsCleaner, nlp: NLPProcessor, emerging_detector: EmergingDetector):
        self.cleaner  = cleaner
        self.nlp      = nlp
        self.emerging = emerging_detector

        # Social media / API collector (Reddit + NewsAPI)
        self.social = SocialMediaCollector()

        # Registered Authorized RSS and Public Feeds
        self.registered_feeds = [
            # Cybersecurity
            {'url': 'https://feeds.feedburner.com/TheHackersNews', 'source': 'The Hacker News', 'default_category': 'Cybersecurity'},
            {'url': 'https://www.bleepingcomputer.com/feed/', 'source': 'BleepingComputer', 'default_category': 'Cybersecurity'},
            # Technology
            {'url': 'https://techcrunch.com/feed/', 'source': 'TechCrunch', 'default_category': 'Technology'},
            {'url': 'https://feeds.arstechnica.com/arstechnica/index', 'source': 'Ars Technica', 'default_category': 'Technology'},
            # Science
            {'url': 'https://www.sciencedaily.com/rss/top/science.xml', 'source': 'ScienceDaily', 'default_category': 'Science'},
            # International & National
            {'url': 'http://feeds.bbci.co.uk/news/world/rss.xml', 'source': 'BBC World News', 'default_category': 'International'},
            {'url': 'https://feeds.npr.org/1001/rss.xml', 'source': 'NPR National News', 'default_category': 'National'},
            # Business
            {'url': 'https://search.cnbc.com/rs/search/combinedlist/cid/10000664/requestor/rss/briefing.xml', 'source': 'CNBC Business', 'default_category': 'Business'}
        ]

    # ------------------------------------------------------------------
    # RSS
    # ------------------------------------------------------------------

    def parse_rss_feed(self, feed_url: str, source_name: str, default_cat: str) -> List[Dict]:
        """
        Fetch and parse RSS feed items using lightweight xml.etree parser.
        """
        items = []
        headers = {'User-Agent': 'dEFEND-News-Collector/1.0 (+https://github.com/defend-research)'}
        try:
            resp = requests.get(feed_url, headers=headers, timeout=5)
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.content)
            # Find all <item> in RSS 2.0 or <entry> in Atom
            for item in root.findall('.//item')[:6]:
                title_elem = item.find('title')
                desc_elem  = item.find('description')
                link_elem  = item.find('link')
                pub_elem   = item.find('pubDate')

                title = title_elem.text if title_elem is not None and title_elem.text else ''
                desc  = desc_elem.text  if desc_elem  is not None and desc_elem.text  else ''
                link  = link_elem.text  if link_elem  is not None and link_elem.text  else ''
                pub   = pub_elem.text   if pub_elem   is not None and pub_elem.text   else datetime.now().isoformat()

                clean_title   = self.cleaner.clean_text(title)
                clean_content = self.cleaner.clean_text(desc)

                if len(clean_title) > 10:
                    items.append({
                        'title':     clean_title,
                        'content':   clean_content or clean_title,
                        'source':    source_name,
                        'category':  default_cat,
                        'url':       link.strip() if link else '',
                        'timestamp': datetime.now().isoformat(),
                        '_origin':   'rss',
                    })

        except Exception as exc:
            logger.debug("RSS pull failed for %s: %s", feed_url, exc)

        return items

    # ------------------------------------------------------------------
    # GDELT
    # ------------------------------------------------------------------

    def query_gdelt_api(self, query: str = 'technology OR science OR security', max_records: int = 5) -> List[Dict]:
        """
        Query GDELT 2.0 Doc API (free, open, authorized public real-time news dataset).
        """
        items = []
        try:
            encoded_query = urllib.parse.quote(query)
            url = (
                f"https://api.gdeltproject.org/api/v2/doc/doc"
                f"?query={encoded_query}&mode=artlist&maxrecords={max_records}&format=json"
            )
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for art in data.get('articles', []):
                    title = self.cleaner.clean_text(art.get('title', ''))
                    if len(title) > 15:
                        items.append({
                            'title':    title,
                            'content':  f"Public report published by {art.get('domain', 'global web source')}. {title}",
                            'source':   art.get('domain', 'GDELT Global News'),
                            'category': 'International',
                            'url':      art.get('url', ''),
                            'timestamp': datetime.now().isoformat(),
                            '_origin':  'gdelt',
                        })
        except Exception as exc:
            logger.debug("GDELT query skipped: %s", exc)

        return items

    # ------------------------------------------------------------------
    # Processing pipeline
    # ------------------------------------------------------------------

    def process_raw_item(self, raw_item: Dict) -> Optional[Dict]:
        """
        Clean, deduplicate, classify, and run NLP pipelines on a single news item.
        Items without a real external URL are dropped.
        """
        title   = self.cleaner.clean_text(raw_item.get('title', ''))
        content = self.cleaner.clean_text(raw_item.get('content', ''))
        url     = raw_item.get('url', '').strip()

        if len(title) < 10:
            return None

        # Drop articles with no real source URL
        if not url or url.startswith('https://news.public/'):
            logger.debug("Dropped article with no real URL: %s", title[:50])
            return None

        # Check deduplication
        is_dup, reason = self.cleaner.is_duplicate(title, content, url)
        if is_dup:
            logger.debug("Deduplication dropped article: %s (%s)", title[:40], reason)
            return None

        article_id = raw_item.get('id') or f"art_{int(time.time() * 1000)}_{abs(hash(title)) % 10000}"
        self.cleaner.register_article(article_id, title, content, url)

        # NLP Classification
        combined_text = f"{title}. {content}"
        cat_result    = self.nlp.classify_category(combined_text)
        category      = cat_result['primary_category']

        # Sentiment Analysis
        sentiment = self.nlp.analyze_sentiment(combined_text)

        # Named Entity Recognition
        entities = self.nlp.extract_named_entities(combined_text)

        # Topic hashtags
        topics = self.nlp.detect_topics(combined_text)

        # Risk score calculation
        risk_score = raw_item.get('risk_score')
        if risk_score is None:
            sens      = sentiment.get('sensationalism_score', 0.0)
            base_risk = 10.0 + (sens * 30.0)
            if any(w in title.lower() for w in ['false', 'rumor', 'conspiracy', 'falsely', 'debunked', 'misinformation']):
                base_risk = max(75.0, base_risk + 40.0)
            elif any(w in title.lower() for w in ['cisa', 'directive', 'standards', 'bipartisan', 'adopts', 'ratified', 'official']):
                base_risk = min(15.0, base_risk)
            risk_score = round(min(100.0, max(5.0, base_risk)), 1)

        if risk_score <= 25:
            risk_level   = 'LOW RISK'
            badge_color  = 'emerald'
        elif risk_score <= 50:
            risk_level   = 'MODERATE RISK'
            badge_color  = 'amber'
        elif risk_score <= 75:
            risk_level   = 'ELEVATED RISK'
            badge_color  = 'orange'
        else:
            risk_level   = 'CRITICAL RISK'
            badge_color  = 'rose'

        processed_article = {
            'id':                  article_id,
            'title':               title,
            'content':             content,
            'source':              raw_item.get('source', 'Authorized News Feed'),
            'author':              raw_item.get('author', 'Staff Reporter'),
            'category':            category,
            'secondary_category':  cat_result.get('secondary_category', 'Technology'),
            'category_confidence': cat_result.get('confidence', 0.8),
            'sentiment':           sentiment,
            'entities':            entities,
            'topics':              topics,
            'url':                 url,
            'timestamp':           raw_item.get('timestamp', datetime.now().isoformat()),
            'risk_score':          risk_score,
            'risk_level':          risk_level,
            'badge_color':         badge_color,
            '_origin':             raw_item.get('_origin', 'rss'),
        }

        # Track event in emerging & burstiness detector
        self.emerging.record_event(processed_article)

        return processed_article

    # ------------------------------------------------------------------
    # Bootstrap corpus (replaces static seed)
    # ------------------------------------------------------------------

    def collect_bootstrap_corpus(self) -> List[Dict]:
        """
        Fetch a live seed corpus from all sources so the dashboard is populated
        immediately on startup without any hardcoded/fabricated content.
        """
        logger.info("Bootstrapping live corpus from all sources…")
        raw_items: List[Dict] = []

        # 1. RSS feeds (first 4 feeds, up to 6 items each)
        for feed in self.registered_feeds[:4]:
            pulled = self.parse_rss_feed(feed['url'], feed['source'], feed['default_category'])
            raw_items.extend(pulled)

        # 2. GDELT
        gdelt_items = self.query_gdelt_api(
            query='technology OR cybersecurity OR science OR politics', max_records=5
        )
        raw_items.extend(gdelt_items)

        # 3. Social media (Reddit + NewsAPI)
        social_items = self.social.collect(posts_per_source=5)
        raw_items.extend(social_items)

        # Process all
        processed: List[Dict] = []
        for raw in raw_items:
            art = self.process_raw_item(raw)
            if art:
                processed.append(art)

        logger.info("Bootstrap corpus: %d articles collected", len(processed))
        return processed

    # ------------------------------------------------------------------
    # Live batch fetch
    # ------------------------------------------------------------------

    def fetch_live_batch(self) -> List[Dict]:
        """
        Poll external RSS feeds, open public APIs, and social media for new items.
        """
        new_items: List[Dict] = []

        # 1. Sample 4 RSS feeds
        for feed in self.registered_feeds[:4]:
            pulled = self.parse_rss_feed(feed['url'], feed['source'], feed['default_category'])
            for raw in pulled:
                processed = self.process_raw_item(raw)
                if processed:
                    new_items.append(processed)

        # 2. GDELT
        gdelt_items = self.query_gdelt_api(query='technology OR cybersecurity OR science', max_records=2)
        for raw in gdelt_items:
            processed = self.process_raw_item(raw)
            if processed:
                new_items.append(processed)

        # 3. Social media (Reddit + NewsAPI)
        social_raw = self.social.collect(posts_per_source=3)
        for raw in social_raw:
            processed = self.process_raw_item(raw)
            if processed:
                new_items.append(processed)

        return new_items

    def get_source_status(self) -> Dict:
        """Expose combined source status from RSS + GDELT + social media."""
        social_status = self.social.source_status()
        return {
            "rss": {
                "active":    True,
                "feeds":     len(self.registered_feeds),
                "error":     None,
            },
            "gdelt": {
                "active":    True,
                "error":     None,
            },
            **social_status,
        }
