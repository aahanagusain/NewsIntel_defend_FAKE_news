"""
Social Media Collector — India-Focused Real News Ingestion via Multiple APIs.

Sources:
  • Reddit OAuth2      — top posts from India-focused subreddits (free)
  • NewsAPI            — top Indian headlines (country=in, free 100 req/day)
  • NewsData.io        — India news search (free 200 req/day, NEWSDATA_KEY)
  • GNews API          — India top headlines (free 100 req/day, GNEWS_KEY)
  • Currents API       — India latest news (free 600 req/day, CURRENTS_KEY)

All sources fail-gracefully: if credentials are absent or the network is
unavailable the collector simply returns an empty list and logs a debug message.
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE  = "https://oauth.reddit.com"

# India-focused subreddits that surface real, sourced Indian news
REDDIT_NEWS_SUBREDDITS = [
    ("india",          "National"),
    ("IndiaSpeaks",    "Politics"),
    ("indianews",      "National"),
    ("IndiaInvestments", "Business"),
    ("developersIndia", "Technology"),
    ("IndianDefense",  "National"),
    ("worldnews",      "International"),   # kept for India-related global coverage
]

# NewsAPI category → our internal category mapping (country=in applied at fetch time)
NEWSAPI_CATEGORIES = {
    "technology":    "Technology",
    "science":       "Science",
    "business":      "Business",
    "health":        "National",
    "general":       "National",
    "entertainment": "National",
}

# Sources per-collector (used for the /api/news/sources status endpoint)
SOURCE_STATUS: Dict[str, Dict] = {
    "reddit":  {"active": False, "last_fetch": None, "articles_total": 0, "error": None},
    "newsapi": {"active": False, "last_fetch": None, "articles_total": 0, "error": None},
}


class RedditCollector:
    """
    Fetches top posts from news subreddits via the Reddit OAuth2 API.
    Posts must link to an external URL (not reddit.com) to qualify as news.
    """

    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.user_agent    = user_agent or "dEFEND-News-Collector/1.0"
        self._token: Optional[str] = None
        self._token_expiry: float  = 0.0

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _fetch_token(self) -> bool:
        """Obtain an OAuth2 app-only access token."""
        try:
            resp = requests.post(
                REDDIT_TOKEN_URL,
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": self.user_agent},
                timeout=8,
            )
            if resp.status_code == 200:
                payload = resp.json()
                self._token        = payload.get("access_token")
                expires_in         = payload.get("expires_in", 3600)
                self._token_expiry = time.time() + expires_in - 60  # 1-min safety margin
                return bool(self._token)
            logger.debug("Reddit token fetch failed: HTTP %s", resp.status_code)
            return False
        except Exception as exc:
            logger.debug("Reddit token fetch error: %s", exc)
            return False

    def _get_valid_token(self) -> Optional[str]:
        """Return a valid access token, refreshing if necessary."""
        if self._token and time.time() < self._token_expiry:
            return self._token
        if self._fetch_token():
            return self._token
        return None

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    def fetch_subreddit_top(
        self,
        subreddit: str,
        category: str,
        limit: int = 5,
        time_filter: str = "day",
    ) -> List[Dict]:
        """Pull top posts from a subreddit and convert them to raw news items."""
        token = self._get_valid_token()
        if not token:
            return []

        try:
            url  = f"{REDDIT_API_BASE}/r/{subreddit}/top"
            resp = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent":    self.user_agent,
                },
                params={"limit": limit, "t": time_filter},
                timeout=8,
            )
            if resp.status_code != 200:
                logger.debug("Reddit /r/%s failed: HTTP %s", subreddit, resp.status_code)
                return []

            posts     = resp.json().get("data", {}).get("children", [])
            articles  = []

            for post_wrapper in posts:
                post = post_wrapper.get("data", {})

                # Skip self-posts (no external URL) and NSFW/spoiler content
                if post.get("is_self") or post.get("over_18") or post.get("spoiler"):
                    continue

                url_field = post.get("url", "")
                # Skip links back to reddit itself
                if not url_field or "reddit.com" in url_field or "redd.it" in url_field:
                    continue

                title   = post.get("title", "").strip()
                score   = post.get("score", 0)
                domain  = post.get("domain", "")
                author  = post.get("author", "Unknown")
                created = post.get("created_utc", time.time())

                if len(title) < 10:
                    continue

                # Build a content summary from title + metadata
                content = (
                    f"{title}. "
                    f"Reported by {domain}. "
                    f"Posted on r/{subreddit} with {score} upvotes. "
                    f"Source: {url_field}"
                )

                articles.append({
                    "title":     title,
                    "content":   content,
                    "source":    f"Reddit r/{subreddit}",
                    "author":    f"u/{author}",
                    "category":  category,
                    "url":       url_field,
                    "timestamp": datetime.utcfromtimestamp(created).isoformat(),
                    "_origin":   "reddit",
                })

            return articles

        except Exception as exc:
            logger.debug("Reddit fetch error for r/%s: %s", subreddit, exc)
            return []

    def collect(self, posts_per_subreddit: int = 4) -> Tuple[List[Dict], str]:
        """
        Collect posts from all configured subreddits.
        Returns (articles, error_msg). error_msg is empty string on success.
        """
        if not self.client_id or not self.client_secret:
            return [], "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not configured"

        all_articles: List[Dict] = []
        for subreddit, category in REDDIT_NEWS_SUBREDDITS:
            items = self.fetch_subreddit_top(
                subreddit, category, limit=posts_per_subreddit
            )
            all_articles.extend(items)
            if items:
                time.sleep(0.3)  # polite rate limiting between subreddit calls

        return all_articles, ""


class NewsAPICollector:
    """
    Fetches top headlines from newsapi.org by category.
    Requires NEWSAPI_KEY environment variable (free developer plan: 100 req/day).
    """

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_category(self, category: str, internal_category: str, page_size: int = 5) -> List[Dict]:
        """Pull top Indian headlines for a given category."""
        if not self.api_key:
            return []

        try:
            resp = requests.get(
                self.BASE_URL,
                params={
                    "apiKey":   self.api_key,
                    "category": category,
                    "country":  "in",          # ← India-only headlines
                    "language": "en",
                    "pageSize": page_size,
                },
                timeout=8,
            )
            if resp.status_code != 200:
                logger.debug("NewsAPI /%s failed: HTTP %s — %s", category, resp.status_code, resp.text[:120])
                return []

            articles_raw = resp.json().get("articles", [])
            articles     = []

            for art in articles_raw:
                title   = (art.get("title")   or "").strip()
                content = (art.get("content") or art.get("description") or "").strip()
                url     = (art.get("url")     or "").strip()
                source  = art.get("source", {}).get("name", "NewsAPI")
                author  = art.get("author") or "Staff Reporter"
                pub_at  = art.get("publishedAt") or datetime.now().isoformat()

                # NewsAPI appends "[+N chars]" to truncated content — strip it
                if content.endswith("]"):
                    content = content.rsplit("[", 1)[0].strip()

                if len(title) < 10 or not url or url == "https://removed.com":
                    continue

                if not content:
                    content = title

                articles.append({
                    "title":     title,
                    "content":   content,
                    "source":    source,
                    "author":    author,
                    "category":  internal_category,
                    "url":       url,
                    "timestamp": pub_at,
                    "_origin":   "newsapi",
                })

            return articles

        except Exception as exc:
            logger.debug("NewsAPI category %s error: %s", category, exc)
            return []

    def collect(self, articles_per_category: int = 4) -> Tuple[List[Dict], str]:
        """
        Collect top headlines across all configured categories.
        Returns (articles, error_msg).
        """
        if not self.api_key:
            return [], "NEWSAPI_KEY not configured"

        all_articles: List[Dict] = []
        for newsapi_cat, internal_cat in NEWSAPI_CATEGORIES.items():
            items = self.fetch_category(newsapi_cat, internal_cat, page_size=articles_per_category)
            all_articles.extend(items)
            if items:
                time.sleep(0.2)  # polite rate limiting

        return all_articles, ""




class IndianNewsAPICollector:
    """
    Collector for three additional free Indian news APIs:

    1. NewsData.io  — https://newsdata.io/  (free: 200 req/day, country=in)
       Register at: https://newsdata.io/register
       Env var: NEWSDATA_KEY

    2. GNews API    — https://gnews.io/     (free: 100 req/day, country=in)
       Register at: https://gnews.io/register
       Env var: GNEWS_KEY

    3. Currents API — https://currentsapi.services/ (free: 600 req/day, country=IN)
       Register at: https://currentsapi.services/en/register
       Env var: CURRENTS_KEY

    All three degrade gracefully — absent key → empty result, no crash.
    """

    NEWSDATA_URL  = "https://newsdata.io/api/1/latest"
    GNEWS_URL     = "https://gnews.io/api/v4/top-headlines"
    CURRENTS_URL  = "https://api.currentsapi.services/v1/latest-news"

    # NewsData.io categories supported (maps to our internal cats)
    NEWSDATA_CATEGORIES = {
        "top":           "National",
        "politics":      "Politics",
        "business":      "Business",
        "technology":    "Technology",
        "science":       "Science",
        "health":        "National",
        "entertainment": "National",
        "sports":        "National",
        "world":         "International",
        "crime":         "National",
    }

    # GNews topics (maps to internal cats)
    GNEWS_TOPICS = {
        "general":       "National",
        "world":         "International",
        "nation":        "National",
        "business":      "Business",
        "technology":    "Technology",
        "entertainment": "National",
        "sports":        "National",
        "science":       "Science",
        "health":        "National",
    }

    def __init__(self, newsdata_key: str, gnews_key: str, currents_key: str):
        self.newsdata_key  = newsdata_key
        self.gnews_key     = gnews_key
        self.currents_key  = currents_key

    # ------------------------------------------------------------------
    # NewsData.io
    # ------------------------------------------------------------------

    def fetch_newsdata(self, articles_per_cat: int = 4) -> Tuple[List[Dict], str]:
        """Fetch from NewsData.io — India news, English, multiple categories."""
        if not self.newsdata_key:
            return [], "NEWSDATA_KEY not configured"

        all_articles: List[Dict] = []
        for newsdata_cat, internal_cat in self.NEWSDATA_CATEGORIES.items():
            try:
                resp = requests.get(
                    self.NEWSDATA_URL,
                    params={
                        "apikey":   self.newsdata_key,
                        "country":  "in",
                        "language": "en",
                        "category": newsdata_cat,
                    },
                    timeout=8,
                )
                if resp.status_code != 200:
                    logger.debug("NewsData.io [%s] HTTP %s", newsdata_cat, resp.status_code)
                    continue

                for art in resp.json().get("results", [])[:articles_per_cat]:
                    title   = (art.get("title")       or "").strip()
                    content = (art.get("description") or art.get("content") or "").strip()
                    url     = (art.get("link")         or "").strip()
                    source  = (art.get("source_id")    or "NewsData India").strip()
                    author  = (art.get("creator")      or ["Staff Reporter"])[0] if art.get("creator") else "Staff Reporter"
                    pub_at  = art.get("pubDate") or datetime.now().isoformat()

                    if len(title) < 10 or not url:
                        continue

                    all_articles.append({
                        "title":     title,
                        "content":   content or title,
                        "source":    source,
                        "author":    author,
                        "category":  internal_cat,
                        "url":       url,
                        "timestamp": pub_at,
                        "_origin":   "newsdata",
                    })

                time.sleep(0.15)

            except Exception as exc:
                logger.debug("NewsData.io category %s error: %s", newsdata_cat, exc)

        return all_articles, ""

    # ------------------------------------------------------------------
    # GNews API
    # ------------------------------------------------------------------

    def fetch_gnews(self, articles_per_topic: int = 4) -> Tuple[List[Dict], str]:
        """Fetch from GNews API — India top headlines, English."""
        if not self.gnews_key:
            return [], "GNEWS_KEY not configured"

        all_articles: List[Dict] = []
        for gnews_topic, internal_cat in self.GNEWS_TOPICS.items():
            try:
                resp = requests.get(
                    self.GNEWS_URL,
                    params={
                        "token":    self.gnews_key,
                        "topic":    gnews_topic,
                        "country":  "in",
                        "lang":     "en",
                        "max":      articles_per_topic,
                    },
                    timeout=8,
                )
                if resp.status_code != 200:
                    logger.debug("GNews [%s] HTTP %s", gnews_topic, resp.status_code)
                    continue

                for art in resp.json().get("articles", []):
                    title   = (art.get("title")       or "").strip()
                    content = (art.get("description") or art.get("content") or "").strip()
                    url     = (art.get("url")          or "").strip()
                    source  = art.get("source", {}).get("name", "GNews India")
                    pub_at  = art.get("publishedAt") or datetime.now().isoformat()

                    if len(title) < 10 or not url:
                        continue

                    all_articles.append({
                        "title":     title,
                        "content":   content or title,
                        "source":    source,
                        "author":    "Staff Reporter",
                        "category":  internal_cat,
                        "url":       url,
                        "timestamp": pub_at,
                        "_origin":   "gnews",
                    })

                time.sleep(0.15)

            except Exception as exc:
                logger.debug("GNews topic %s error: %s", gnews_topic, exc)

        return all_articles, ""

    # ------------------------------------------------------------------
    # Currents API
    # ------------------------------------------------------------------

    def fetch_currents(self, max_articles: int = 20) -> Tuple[List[Dict], str]:
        """Fetch from Currents API — India latest news, English."""
        if not self.currents_key:
            return [], "CURRENTS_KEY not configured"

        try:
            resp = requests.get(
                self.CURRENTS_URL,
                params={
                    "apiKey":   self.currents_key,
                    "country":  "IN",
                    "language": "en",
                },
                timeout=8,
            )
            if resp.status_code != 200:
                logger.debug("Currents API HTTP %s: %s", resp.status_code, resp.text[:100])
                return [], f"Currents API HTTP {resp.status_code}"

            articles_raw = resp.json().get("news", [])[:max_articles]
            articles: List[Dict] = []
            for art in articles_raw:
                title    = (art.get("title")       or "").strip()
                content  = (art.get("description") or "").strip()
                url      = (art.get("url")          or "").strip()
                author   = (art.get("author")       or "Staff Reporter").strip()
                pub_at   = art.get("published") or datetime.now().isoformat()
                # Map Currents category list to our internal categories
                cats     = art.get("category", [])
                internal_cat = "National"
                if cats:
                    cat_map = {
                        "politics": "Politics", "business": "Business",
                        "technology": "Technology", "science": "Science",
                        "world": "International", "national": "National",
                        "entertainment": "National", "health": "National",
                        "sports": "National",
                    }
                    for c in cats:
                        if c.lower() in cat_map:
                            internal_cat = cat_map[c.lower()]
                            break

                if len(title) < 10 or not url or url == "N/A":
                    continue

                articles.append({
                    "title":     title,
                    "content":   content or title,
                    "source":    "Currents India",
                    "author":    author,
                    "category":  internal_cat,
                    "url":       url,
                    "timestamp": pub_at,
                    "_origin":   "currents",
                })

            return articles, ""

        except Exception as exc:
            logger.debug("Currents API error: %s", exc)
            return [], str(exc)

    def collect(self, articles_per_source: int = 5) -> Tuple[List[Dict], Dict[str, str]]:
        """
        Collect from all three Indian news APIs.
        Returns (combined_articles, {source: error_msg}).
        """
        combined: List[Dict] = []
        errors: Dict[str, str] = {}

        nd_arts, nd_err = self.fetch_newsdata(articles_per_cat=articles_per_source)
        if nd_err:
            errors["newsdata"] = nd_err
        else:
            combined.extend(nd_arts)

        gn_arts, gn_err = self.fetch_gnews(articles_per_topic=articles_per_source)
        if gn_err:
            errors["gnews"] = gn_err
        else:
            combined.extend(gn_arts)

        cu_arts, cu_err = self.fetch_currents(max_articles=articles_per_source * 4)
        if cu_err:
            errors["currents"] = cu_err
        else:
            combined.extend(cu_arts)

        return combined, errors


class SocialMediaCollector:
    """
    Unified façade that orchestrates all five Indian news sources:
    Reddit, NewsAPI, NewsData.io, GNews, and Currents API.
    Exposes collect() and source_status().
    """

    def __init__(self):
        # --- Reddit ---
        reddit_id     = os.getenv("REDDIT_CLIENT_ID", "")
        reddit_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        reddit_agent  = os.getenv("REDDIT_USER_AGENT", "dEFEND-News-Collector/1.0")
        # --- NewsAPI ---
        newsapi_key   = os.getenv("NEWSAPI_KEY", "")
        # --- Three new Indian news APIs ---
        newsdata_key  = os.getenv("NEWSDATA_KEY", "")
        gnews_key     = os.getenv("GNEWS_KEY", "")
        currents_key  = os.getenv("CURRENTS_KEY", "")

        self._reddit      = RedditCollector(reddit_id, reddit_secret, reddit_agent)
        self._newsapi     = NewsAPICollector(newsapi_key)
        self._india_apis  = IndianNewsAPICollector(newsdata_key, gnews_key, currents_key)

        self._source_status: Dict[str, Dict] = {
            "reddit": {
                "active":         bool(reddit_id and reddit_secret),
                "configured":     bool(reddit_id and reddit_secret),
                "last_fetch":     None,
                "articles_total": 0,
                "error":          None if (reddit_id and reddit_secret) else "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set",
            },
            "newsapi": {
                "active":         bool(newsapi_key),
                "configured":     bool(newsapi_key),
                "last_fetch":     None,
                "articles_total": 0,
                "error":          None if newsapi_key else "NEWSAPI_KEY not set",
            },
            "newsdata": {
                "active":         bool(newsdata_key),
                "configured":     bool(newsdata_key),
                "last_fetch":     None,
                "articles_total": 0,
                "error":          None if newsdata_key else "NEWSDATA_KEY not set",
            },
            "gnews": {
                "active":         bool(gnews_key),
                "configured":     bool(gnews_key),
                "last_fetch":     None,
                "articles_total": 0,
                "error":          None if gnews_key else "GNEWS_KEY not set",
            },
            "currents": {
                "active":         bool(currents_key),
                "configured":     bool(currents_key),
                "last_fetch":     None,
                "articles_total": 0,
                "error":          None if currents_key else "CURRENTS_KEY not set",
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self, posts_per_source: int = 5) -> List[Dict]:
        """
        Pull real Indian news articles from all configured sources.
        Returns a combined list of raw article dicts.
        """
        combined: List[Dict] = []
        now = datetime.now().isoformat()

        # --- Reddit ---
        reddit_articles, reddit_err = self._reddit.collect(posts_per_subreddit=posts_per_source)
        self._source_status["reddit"]["last_fetch"] = now
        if reddit_err:
            self._source_status["reddit"]["error"]  = reddit_err
            self._source_status["reddit"]["active"] = False
        else:
            self._source_status["reddit"]["error"]          = None
            self._source_status["reddit"]["active"]         = True
            self._source_status["reddit"]["articles_total"] += len(reddit_articles)
            combined.extend(reddit_articles)
            logger.info("Reddit: fetched %d articles", len(reddit_articles))

        # --- NewsAPI ---
        newsapi_articles, newsapi_err = self._newsapi.collect(articles_per_category=posts_per_source)
        self._source_status["newsapi"]["last_fetch"] = now
        if newsapi_err:
            self._source_status["newsapi"]["error"]  = newsapi_err
            self._source_status["newsapi"]["active"] = False
        else:
            self._source_status["newsapi"]["error"]          = None
            self._source_status["newsapi"]["active"]         = True
            self._source_status["newsapi"]["articles_total"] += len(newsapi_articles)
            combined.extend(newsapi_articles)
            logger.info("NewsAPI: fetched %d articles", len(newsapi_articles))

        # --- NewsData.io + GNews + Currents ---
        india_articles, india_errors = self._india_apis.collect(articles_per_source=posts_per_source)
        for source_key in ("newsdata", "gnews", "currents"):
            self._source_status[source_key]["last_fetch"] = now
            if source_key in india_errors:
                self._source_status[source_key]["error"]  = india_errors[source_key]
                self._source_status[source_key]["active"] = False
            else:
                self._source_status[source_key]["error"]  = None
                self._source_status[source_key]["active"] = self._source_status[source_key]["configured"]

        # Count per-source article additions
        for art in india_articles:
            origin = art.get("_origin", "")
            if origin in self._source_status:
                self._source_status[origin]["articles_total"] += 1

        combined.extend(india_articles)
        if india_articles:
            logger.info("Indian APIs (NewsData/GNews/Currents): fetched %d articles", len(india_articles))

        return combined

    def source_status(self) -> Dict[str, Dict]:
        """Return per-source status information for the /api/news/sources endpoint."""
        return dict(self._source_status)

