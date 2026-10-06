"""
Social Media Collector — Real News Ingestion via Reddit & NewsAPI.

Sources:
  • Reddit OAuth2 — top posts from news subreddits (no paid plan required)
  • NewsAPI       — top headlines by category  (requires NEWSAPI_KEY, free 100 req/day)

Both sources fail-gracefully: if credentials are absent or the network is
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

# Subreddits that surface real, sourced news with external URLs
REDDIT_NEWS_SUBREDDITS = [
    ("worldnews",      "International"),
    ("technology",     "Technology"),
    ("science",        "Science"),
    ("politics",       "Politics"),
    ("netsec",         "Cybersecurity"),
    ("business",       "Business"),
    ("unitedstates",   "National"),
]

# NewsAPI category → our internal category mapping
NEWSAPI_CATEGORIES = {
    "technology":  "Technology",
    "science":     "Science",
    "business":    "Business",
    "health":      "National",
    "general":     "International",
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
        """Pull top headlines for a given category."""
        if not self.api_key:
            return []

        try:
            resp = requests.get(
                self.BASE_URL,
                params={
                    "apiKey":   self.api_key,
                    "category": category,
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


class SocialMediaCollector:
    """
    Unified façade that orchestrates Reddit and NewsAPI collectors.
    Exposes collect() and source_status().
    """

    def __init__(self):
        reddit_id     = os.getenv("REDDIT_CLIENT_ID", "")
        reddit_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        reddit_agent  = os.getenv("REDDIT_USER_AGENT", "dEFEND-News-Collector/1.0")
        newsapi_key   = os.getenv("NEWSAPI_KEY", "")

        self._reddit  = RedditCollector(reddit_id, reddit_secret, reddit_agent)
        self._newsapi = NewsAPICollector(newsapi_key)

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
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self, posts_per_source: int = 5) -> List[Dict]:
        """
        Pull real news articles from all configured social media sources.
        Returns a combined, deduplicated list of raw article dicts.
        """
        combined: List[Dict] = []

        # --- Reddit ---
        reddit_articles, reddit_err = self._reddit.collect(posts_per_subreddit=posts_per_source)
        self._source_status["reddit"]["last_fetch"] = datetime.now().isoformat()
        if reddit_err:
            self._source_status["reddit"]["error"]  = reddit_err
            self._source_status["reddit"]["active"] = False
        else:
            self._source_status["reddit"]["error"]         = None
            self._source_status["reddit"]["active"]        = True
            self._source_status["reddit"]["articles_total"] += len(reddit_articles)
            combined.extend(reddit_articles)
            logger.info("Reddit: fetched %d articles", len(reddit_articles))

        # --- NewsAPI ---
        newsapi_articles, newsapi_err = self._newsapi.collect(articles_per_category=posts_per_source)
        self._source_status["newsapi"]["last_fetch"] = datetime.now().isoformat()
        if newsapi_err:
            self._source_status["newsapi"]["error"]  = newsapi_err
            self._source_status["newsapi"]["active"] = False
        else:
            self._source_status["newsapi"]["error"]         = None
            self._source_status["newsapi"]["active"]        = True
            self._source_status["newsapi"]["articles_total"] += len(newsapi_articles)
            combined.extend(newsapi_articles)
            logger.info("NewsAPI: fetched %d articles", len(newsapi_articles))

        return combined

    def source_status(self) -> Dict[str, Dict]:
        """Return per-source status information for the /api/news/sources endpoint."""
        return dict(self._source_status)
