"""
News Cleaner & Normalization & Deduplication Service.
Handles HTML stripping, entity decoding, whitespace normalization,
and exact + near-duplicate content deduplication.
"""

import re
import html
import hashlib
from typing import Dict, List, Optional, Set, Tuple


class NewsCleaner:
    def __init__(self, jaccard_threshold: float = 0.72):
        self.jaccard_threshold = jaccard_threshold
        self._seen_exact_hashes: Set[str] = set()
        self._seen_articles: List[Dict[str, any]] = []  # Stores recent signatures for fuzzy matching

        # Boilerplate phrases common in scraped/RSS news
        self.boilerplate_patterns = [
            re.compile(r'subscribe\s+to\s+our\s+newsletter.*', re.IGNORECASE),
            re.compile(r'follow\s+us\s+on\s+(twitter|x|facebook|instagram).*', re.IGNORECASE),
            re.compile(r'all\s+rights\s+reserved.*', re.IGNORECASE),
            re.compile(r'click\s+here\s+to\s+read\s+more.*', re.IGNORECASE),
            re.compile(r'copyright\s+©?\s*\d{4}.*', re.IGNORECASE),
            re.compile(r'advertisement\s*', re.IGNORECASE),
            re.compile(r'share\s+this\s+article.*', re.IGNORECASE)
        ]

    def clean_text(self, raw_html_or_text: str) -> str:
        """Strip HTML tags, decode entities, remove ads boilerplate, normalize whitespace."""
        if not raw_html_or_text:
            return ""

        # Step 1: Decode HTML entities (&amp;, &nbsp;, etc.)
        text = html.unescape(raw_html_or_text)

        # Step 2: Remove script, style, and svg blocks
        text = re.sub(r'<(script|style|svg)[^>]*>[\s\S]*?</\1>', ' ', text, flags=re.IGNORECASE)

        # Step 3: Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Step 4: Normalize quotes, dashes, and unicode special chars
        text = text.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")
        text = text.replace('—', ' - ').replace('–', ' - ').replace('…', '...')

        # Step 5: Remove boilerplate
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            is_bp = any(bp.search(line_str) for bp in self.boilerplate_patterns)
            if not is_bp:
                clean_lines.append(line_str)
        text = " ".join(clean_lines)

        # Step 6: Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def compute_hash(self, text: str) -> str:
        """Compute SHA-256 fingerprint of normalized text."""
        normalized = re.sub(r'\W+', '', text.lower())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def tokenize_for_similarity(self, text: str) -> Set[str]:
        """Extract alphanumeric word tokens of length >= 3 for similarity testing."""
        words = re.findall(r'\b[a-z0-9]{3,}\b', text.lower())
        return set(words)

    def is_duplicate(self, title: str, content: str, url: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if an incoming news item is an exact duplicate or a syndicated near-duplicate.
        Returns: (is_dup, reason)
        """
        combined = f"{title} {content}"
        content_hash = self.compute_hash(combined)

        # 1. Exact hash check
        if content_hash in self._seen_exact_hashes:
            return True, "Exact content hash duplicate detected"

        # 2. Fuzzy title and content token overlap check
        title_tokens = self.tokenize_for_similarity(title)
        content_tokens = self.tokenize_for_similarity(content[:400])

        for prev in self._seen_articles[-200:]:  # Check against recent window
            # Title exact or high overlap
            prev_title_tokens = prev['title_tokens']
            if title_tokens and prev_title_tokens:
                intersection = len(title_tokens.intersection(prev_title_tokens))
                union = len(title_tokens.union(prev_title_tokens))
                if union > 0 and (intersection / union) >= self.jaccard_threshold:
                    return True, f"Syndicated title duplicate of: '{prev['title'][:50]}...'"

            # Content lead overlap
            prev_content_tokens = prev['content_tokens']
            if content_tokens and prev_content_tokens:
                c_inter = len(content_tokens.intersection(prev_content_tokens))
                c_union = len(content_tokens.union(prev_content_tokens))
                if c_union > 0 and (c_inter / c_union) >= 0.85:
                    return True, f"High body content overlap with existing article ID {prev['id']}"

        return False, "Unique"

    def register_article(self, article_id: str, title: str, content: str, url: Optional[str] = None) -> str:
        """Register article into seen cache for subsequent deduplication."""
        combined = f"{title} {content}"
        content_hash = self.compute_hash(combined)
        self._seen_exact_hashes.add(content_hash)

        self._seen_articles.append({
            'id': article_id,
            'title': title,
            'title_tokens': self.tokenize_for_similarity(title),
            'content_tokens': self.tokenize_for_similarity(content[:400]),
            'hash': content_hash,
            'url': url
        })
        # Keep window bounded
        if len(self._seen_articles) > 500:
            self._seen_articles = self._seen_articles[-500:]

        return content_hash
