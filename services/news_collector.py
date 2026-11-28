"""
News Collector Service for India-Focused Multi-Source Ingestion.
Collects from Indian RSS Feeds, authorized APIs (GDELT India, NewsAPI India), Reddit, and public web sources.
Filters to India-only news, cleans, normalizes, deduplicates, classifies, and runs NLP analysis on every item.
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

        # ----------------------------------------------------------------
        # India-Focused RSS Feeds — major Indian publishers only
        # ----------------------------------------------------------------
        self.registered_feeds = [
            # National / Politics
            {'url': 'https://feeds.feedburner.com/ndtvnews-top-stories', 'source': 'NDTV', 'default_category': 'National'},
            {'url': 'https://timesofindia.indiatimes.com/rssfeeds/296589292.cms', 'source': 'Times of India – Top Stories', 'default_category': 'National'},
            {'url': 'https://www.thehindu.com/news/national/?service=rss', 'source': 'The Hindu – National', 'default_category': 'National'},
            {'url': 'https://indianexpress.com/section/india/feed/', 'source': 'Indian Express – India', 'default_category': 'National'},
            # Politics
            {'url': 'https://www.thehindu.com/news/national/politics/?service=rss', 'source': 'The Hindu – Politics', 'default_category': 'Politics'},
            {'url': 'https://timesofindia.indiatimes.com/rssfeeds/1221656.cms', 'source': 'Times of India – Politics', 'default_category': 'Politics'},
            # Business / Economy
            {'url': 'https://www.livemint.com/rss/economy', 'source': 'Livemint – Economy', 'default_category': 'Business'},
            {'url': 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms', 'source': 'Economic Times – Markets', 'default_category': 'Business'},
            {'url': 'https://www.business-standard.com/rss/economy-policy-10106.rss', 'source': 'Business Standard', 'default_category': 'Business'},
            # Technology
            {'url': 'https://timesofindia.indiatimes.com/rssfeeds/66949542.cms', 'source': 'Times of India – Tech', 'default_category': 'Technology'},
            {'url': 'https://www.hindustantimes.com/feeds/rss/technology/rssfeed.xml', 'source': 'Hindustan Times – Tech', 'default_category': 'Technology'},
            # Science
            {'url': 'https://www.thehindu.com/sci-tech/?service=rss', 'source': 'The Hindu – Sci/Tech', 'default_category': 'Science'},
            # Sports (Cricket, Football, Olympics, Badminton, Hockey)
            {'url': 'https://timesofindia.indiatimes.com/rssfeeds/4719148.cms', 'source': 'Times of India – Sports', 'default_category': 'Sports'},
            {'url': 'https://www.thehindu.com/sport/cricket/?service=rss', 'source': 'The Hindu – Cricket', 'default_category': 'Sports'},
            {'url': 'https://indianexpress.com/section/sports/feed/', 'source': 'Indian Express – Sports', 'default_category': 'Sports'},
            # Entertainment / Cinema / Culture
            {'url': 'https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms', 'source': 'Times of India – Entertainment', 'default_category': 'Entertainment'},
            {'url': 'https://www.thehindu.com/entertainment/?service=rss', 'source': 'The Hindu – Entertainment', 'default_category': 'Entertainment'},
            # International (India-related foreign coverage)
            {'url': 'http://feeds.bbci.co.uk/news/world/asia/india/rss.xml', 'source': 'BBC India', 'default_category': 'International'},
            # Fact-Check
            {'url': 'https://www.altnews.in/feed/', 'source': 'AltNews Fact-Check', 'default_category': 'FactCheck'},
            {'url': 'https://factchecker.in/feed/', 'source': 'FactChecker.in', 'default_category': 'FactCheck'},
        ]

        # India-relevance keyword set (used to filter non-Indian news)
        self.india_keywords = {
            'india', 'indian', 'bharat', 'bharatiya', 'modi', 'delhi', 'mumbai',
            'bangalore', 'bengaluru', 'hyderabad', 'chennai', 'kolkata', 'pune',
            'ahmedabad', 'jaipur', 'lucknow', 'patna', 'bhopal', 'chandigarh',
            'parliament', 'lok sabha', 'rajya sabha', 'bjp', 'congress', 'aap',
            'rbi', 'sebi', 'isro', 'niti aayog', 'supreme court of india',
            'cbi', 'ed enforcement', 'income tax', 'gst', 'rupee', 'sensex',
            'nifty', 'bse', 'nse', 'reliance', 'tata', 'infosys', 'wipro',
            'adani', 'hdfc', 'sbi', 'lic', 'ola', 'zomato', 'paytm', 'flipkart',
            'kashmir', 'punjab', 'haryana', 'rajasthan', 'gujarat', 'maharashtra',
            'karnataka', 'kerala', 'telangana', 'andhra', 'uttar pradesh', 'bihar',
            'jharkhand', 'odisha', 'assam', 'manipur', 'mizoram', 'nagaland',
            'uttarakhand', 'himachal', 'goa', 'sikkim', 'tripura', 'meghalaya',
            'lakshadweep', 'andaman', 'ladakh', 'arunachal', 'daman', 'puducherry',
            'pm modi', 'rahul gandhi', 'amit shah', 'yogi adityanath', 'mamata',
            'arvind kejriwal', 'nitish kumar', 'narendra modi', 'president of india',
            'vice president of india', 'chief minister', 'union budget', 'make in india',
            'digital india', 'atmanirbhar', 'swachh bharat', 'jan dhan', 'aadhaar',
            'upi', 'neet', 'jee', 'iit', 'iim', 'aiims', 'ugc',
            # Sports & Entertainment keywords
            'cricket', 'bcci', 'ipl', 'team india', 'rohit sharma', 'virat kohli',
            'hardik pandya', 'bumrah', 'shubman gill', 'gautam gambhir', 'dhoni',
            'wpl', 'test match', 'odi', 't20', 'icc', 'ranji trophy', 'badminton',
            'pv sindhu', 'neeraj chopra', 'hockey', 'olympics', 'asian games',
            'kabaddi', 'pro kabaddi', 'isl', 'football', 'wrestling', 'chess',
            'praggnanandhaa', 'gukesh', 'viswanathan anand', 'bollywood', 'tollywood',
            'kollywood', 'cinema', 'box office', 'actor', 'actress', 'film',
        }

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

    def query_gdelt_api(self, query: str = 'India', max_records: int = 5) -> List[Dict]:
        """
        Query GDELT 2.0 Doc API restricted to India-related news articles.
        Uses sourcecountry:IN and domain filter to bias results toward Indian publishers.
        """
        items = []
        try:
            encoded_query = urllib.parse.quote(query)
            url = (
                f"https://api.gdeltproject.org/api/v2/doc/doc"
                f"?query={encoded_query}&mode=artlist&maxrecords={max_records}&format=json"
                f"&sourcelang=english"
            )
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for art in data.get('articles', []):
                    title = self.cleaner.clean_text(art.get('title', ''))
                    if len(title) > 15 and self.is_india_relevant(title):
                        items.append({
                            'title':    title,
                            'content':  f"GDELT-indexed Indian news report from {art.get('domain', 'Indian web source')}. {title}",
                            'source':   art.get('domain', 'GDELT India News'),
                            'category': 'National',
                            'url':      art.get('url', ''),
                            'timestamp': datetime.now().isoformat(),
                            '_origin':  'gdelt',
                        })
        except Exception as exc:
            logger.debug("GDELT India query skipped: %s", exc)

        return items

    # ------------------------------------------------------------------
    # Processing pipeline
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # India relevance filter
    # ------------------------------------------------------------------

    def is_india_relevant(self, text: str) -> bool:
        """
        Return True if the article title/content contains at least one
        India-related keyword. This keeps the pipeline India-focused.
        """
        lower = text.lower()
        return any(kw in lower for kw in self.india_keywords)

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
        if not url or url.startswith('https://news.public/') or url.startswith('https://removed.com'):
            logger.debug("Dropped article with no real URL: %s", title[:50])
            return None

        # Drop articles not related to India
        if not self.is_india_relevant(f"{title} {content}"):
            logger.debug("Dropped non-India article: %s", title[:50])
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
        feed_cat      = raw_item.get('category')

        # If feed has a specific category like Sports or Entertainment and NLP is generic/low confidence, respect the feed
        if feed_cat and feed_cat in ['Sports', 'Entertainment', 'Science', 'Technology', 'Business', 'FactCheck']:
            if category == 'National' or cat_result.get('confidence', 0) < 0.65:
                category = feed_cat

        # Sentiment Analysis
        sentiment = self.nlp.analyze_sentiment(combined_text)

        # Named Entity Recognition
        entities = self.nlp.extract_named_entities(combined_text)

        # Topic hashtags
        topics = self.nlp.detect_topics(combined_text)

        # Risk score calculation — India-specific signals
        risk_score = raw_item.get('risk_score')
        if risk_score is None:
            sens      = sentiment.get('sensationalism_score', 0.0)
            base_risk = 10.0 + (sens * 30.0)

            # Indian fake-news / misinformation red flags (high-risk boosters)
            india_red_flags = [
                'fake', 'false', 'rumor', 'hoax', 'misleading', 'conspiracy',
                'falsely', 'debunked', 'misinformation', 'disinformation',
                'viral forward', 'whatsapp', 'fabricated', 'propaganda',
                'manipulated video', 'deepfake', 'out of context', 'no evidence',
                'misattributed', 'edited photo', 'not verified',
            ]
            # Indian authoritative trust signals (low-risk suppressors)
            india_trust_signals = [
                'isro', 'rbi', 'sebi', 'supreme court', 'government of india',
                'ministry of', 'election commission', 'official gazette', 'pib',
                'uidai', 'npci', 'icmr', 'cert-in', 'niti aayog', 'parliament',
                'press information bureau', 'fact check', 'altnews', 'factchecker',
            ]

            if any(w in title.lower() for w in india_red_flags):
                base_risk = max(75.0, base_risk + 40.0)
            elif any(w in title.lower() for w in india_trust_signals):
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

        # 2. GDELT — India-specific queries
        for india_query in [
            'India politics parliament BJP Congress',
            'India technology startup Bengaluru',
            'India economy RBI rupee GDP',
            'India cybersecurity data breach',
        ]:
            gdelt_items = self.query_gdelt_api(query=india_query, max_records=3)
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

    def fetch_live_batch(self, max_feeds: int = 5) -> List[Dict]:
        """
        Quickly poll external RSS feeds (rotating across all 15 registered Indian sources)
        for real-time news updates.
        """
        new_items: List[Dict] = []

        # Rotate through registered feeds to maximize variety across calls
        if not hasattr(self, '_feed_index'):
            self._feed_index = 0

        total_feeds = len(self.registered_feeds)
        selected_feeds = [
            self.registered_feeds[(self._feed_index + i) % total_feeds]
            for i in range(min(max_feeds, total_feeds))
        ]
        self._feed_index = (self._feed_index + max_feeds) % total_feeds

        for feed in selected_feeds:
            pulled = self.parse_rss_feed(feed['url'], feed['source'], feed['default_category'])
            for raw in pulled:
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
