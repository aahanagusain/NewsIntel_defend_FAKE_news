"""
NLP Processor Service for News Analysis.
Implements:
1. Category Classification (Technology, Politics, National, International, Business, Science, Cybersecurity)
2. Sentiment Analysis (Polarity, Subjectivity/Sensationalism, Classification)
3. Named-Entity Recognition (PERSON, ORGANIZATION, LOCATION, DATE, EVENT)
4. Topic & Keyphrase Detection (TF-IDF inspired term-frequency ranking and thematic tags)
"""

import re
import math
from collections import Counter
from typing import Dict, List, Set, Tuple


class NLPProcessor:
    def __init__(self):
        # Category lexicon dictionaries with weighted terms
        self.category_lexicons: Dict[str, Dict[str, float]] = {
            'Cybersecurity': {
                'ransomware': 3.5, 'malware': 3.0, 'vulnerability': 2.8, 'cve': 3.5,
                'zero-day': 3.5, 'hack': 2.5, 'hacker': 2.8, 'breach': 2.8,
                'phishing': 3.0, 'cisa': 3.2, 'cyberattack': 3.5, 'ddos': 3.0,
                'trojan': 3.0, 'exploit': 2.8, 'cyber': 2.5, 'firewall': 2.2,
                'encryption': 2.2, 'infosec': 3.0, 'threat actor': 3.5, 'apt': 3.0,
                'patch': 2.0, 'backdoor': 3.2, 'spyware': 3.0, 'data leak': 2.8
            },
            'Technology': {
                'ai': 2.5, 'artificial intelligence': 3.5, 'algorithm': 2.2, 'software': 2.0,
                'hardware': 2.0, 'semiconductor': 3.0, 'chip': 2.0, 'gpu': 2.5,
                'apple': 2.0, 'microsoft': 2.0, 'google': 2.0, 'nvidia': 2.8,
                'meta': 1.8, 'smartphone': 2.2, 'cloud': 1.8, 'robotics': 2.8,
                'llm': 3.2, 'neural network': 3.0, 'startup': 1.8, 'computing': 2.0,
                'quantum': 2.2, 'open-source': 2.2, 'virtual reality': 2.5, 'autonomous': 2.2
            },
            'Science': {
                'nasa': 3.0, 'space': 2.2, 'telescope': 2.8, 'astronomy': 3.0,
                'planet': 2.2, 'galaxy': 2.8, 'exoplanet': 3.5, 'physics': 2.8,
                'biology': 2.5, 'climate': 2.2, 'gene': 2.8, 'crispr': 3.5,
                'fossil': 2.8, 'laboratory': 2.0, 'study': 1.5, 'researchers': 1.8,
                'scientists': 2.0, 'experiment': 2.0, 'james webb': 3.5, 'ocean': 1.8,
                'ecosystem': 2.2, 'species': 2.2, 'dna': 2.8, 'quantum physics': 3.2
            },
            'Politics': {
                'senate': 2.8, 'congress': 2.8, 'election': 3.0, 'democrat': 2.8,
                'republican': 2.8, 'president': 2.2, 'bill': 2.0, 'lawmaker': 2.5,
                'legislation': 2.8, 'governor': 2.2, 'campaign': 2.5, 'voter': 2.5,
                'ballot': 2.8, 'court': 2.0, 'supreme court': 3.2, 'politician': 2.8,
                'policy': 1.8, 'diplomat': 2.2, 'parliament': 2.8, 'minister': 2.2,
                'prime minister': 2.8, 'veto': 2.8, 'caucus': 3.0, 'impeachment': 3.2
            },
            'Business': {
                'stock': 2.8, 'shares': 2.5, 'revenue': 2.8, 'profit': 2.5,
                'quarter': 1.8, 'earnings': 2.8, 'wall street': 3.2, 'market': 2.0,
                'investor': 2.5, 'nasdaq': 3.2, 's&p': 3.0, 'dow jones': 3.2,
                'inflation': 2.5, 'interest rate': 2.8, 'central bank': 2.8, 'fed': 2.2,
                'ceo': 2.2, 'acquisition': 2.8, 'merger': 2.8, 'ipo': 3.2,
                'recession': 2.8, 'valuation': 2.5, 'fintech': 2.8, 'dividend': 2.8
            },
            'International': {
                'united nations': 3.2, 'treaty': 2.8, 'global': 1.8, 'foreign minister': 2.8,
                'nato': 3.2, 'eu': 2.2, 'european union': 3.0, 'summit': 2.2,
                'sanctions': 3.0, 'diplomacy': 2.8, 'ukraine': 2.5, 'middle east': 2.8,
                'asia-pacific': 2.8, 'bilateral': 2.8, 'geopolitics': 3.2, 'embassy': 2.8,
                'international': 2.2, 'humanitarian': 2.5, 'refugee': 2.8, 'cross-border': 2.5
            },
            'National': {
                'federal': 2.0, 'state': 1.5, 'homeland': 2.5, 'nationwide': 2.2,
                'domestic': 2.2, 'infrastructure': 2.0, 'public safety': 2.5, 'census': 2.8,
                'highway': 2.0, 'agency': 1.5, 'national park': 2.8, 'interstate': 2.2,
                'county': 1.8, 'coast guard': 2.8, 'department of': 2.0, 'fbi': 2.8,
                'postal service': 2.8, 'treasury': 2.2, 'governance': 2.0
            }
        }

        # Sentiment lexicon
        self.positive_words = {
            'breakthrough', 'success', 'triumph', 'progress', 'recovery', 'growth',
            'innovative', 'soars', 'gains', 'peace', 'cure', 'verified', 'approved',
            'historic', 'boost', 'promising', 'record-high', 'effective', 'excellence'
        }
        self.negative_words = {
            'crisis', 'threat', 'collapse', 'fraud', 'scandal', 'crash', 'fatal',
            'catastrophe', 'exploit', 'breach', 'warning', 'danger', 'deadly', 'halt',
            'panic', 'plunge', 'arrested', 'severe', 'investigation', 'decline', 'turmoil'
        }
        self.sensational_words = {
            'shocking', 'unbelievable', 'bombshell', 'secret', 'leaked', 'conspiracy',
            'cover-up', 'they don\'t want you to know', 'mind-blowing', 'unprecedented',
            'destroy', 'annihilate', 'miracle', 'terrifying', 'exposed', 'urgent alert'
        }

        # Common stop words for topic extraction
        self.stop_words = {
            'the', 'and', 'for', 'that', 'this', 'with', 'from', 'have', 'were', 'been',
            'they', 'their', 'which', 'about', 'after', 'will', 'more', 'also', 'said',
            'reported', 'into', 'over', 'than', 'them', 'these', 'would', 'could', 'some'
        }

        # Known entity lists for fast high-accuracy NER
        self.known_orgs = {
            'NASA', 'Google', 'Microsoft', 'Apple', 'Meta', 'NVIDIA', 'OpenAI', 'Amazon',
            'Tesla', 'CISA', 'FBI', 'CIA', 'NATO', 'WHO', 'UN', 'SEC', 'NIST', 'CDC',
            'Federal Reserve', 'White House', 'European Commission', 'Reuters', 'BBC',
            'PolitiFact', 'CrowdStrike', 'Lockheed', 'SpaceX', 'DeepMind', 'Anthropic'
        }
        self.known_locations = {
            'Washington', 'London', 'Beijing', 'Moscow', 'Kyiv', 'Brussels', 'Tokyo',
            'Paris', 'Berlin', 'New York', 'California', 'Texas', 'Florida', 'Geneva',
            'United States', 'China', 'Russia', 'Ukraine', 'India', 'Europe', 'Taiwan',
            'Middle East', 'San Francisco', 'Silicon Valley', 'Venus', 'Mars', 'Moon'
        }

    def classify_category(self, text: str) -> Dict[str, any]:
        """
        Classify text into: Technology, Politics, National, International, Business, Science, Cybersecurity.
        Returns primary category, confidence, and score distributions.
        """
        lower_text = text.lower()
        scores = {}

        for category, lexicon in self.category_lexicons.items():
            cat_score = 0.0
            for term, weight in lexicon.items():
                # Count occurrences of term (word boundaries)
                pattern = r'\b' + re.escape(term) + r'\b'
                matches = len(re.findall(pattern, lower_text))
                if matches > 0:
                    cat_score += weight * (1 + math.log(matches))
            scores[category] = cat_score

        # Default fallback if no keywords matched
        total_score = sum(scores.values())
        if total_score == 0:
            return {
                'primary_category': 'National',
                'secondary_category': 'Technology',
                'confidence': 0.50,
                'distribution': {k: 0.14 for k in self.category_lexicons}
            }

        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_cats[0][0]
        secondary = sorted_cats[1][0] if len(sorted_cats) > 1 else 'National'
        
        confidence = min(0.96, round(sorted_cats[0][1] / (total_score + 1e-5), 2))
        confidence = max(0.45, confidence)

        # Normalize distributions to percentage
        distribution = {k: round((v / total_score) * 100, 1) for k, v in scores.items()}

        return {
            'primary_category': primary,
            'secondary_category': secondary,
            'confidence': confidence,
            'distribution': distribution
        }

    def analyze_sentiment(self, text: str) -> Dict[str, any]:
        """
        Compute polarity score (-1.0 to 1.0), subjectivity / sensationalism (0.0 to 1.0),
        and label (POSITIVE, NEUTRAL, NEGATIVE).
        """
        lower_text = text.lower()
        tokens = set(re.findall(r'\b[a-z]{3,}\b', lower_text))

        pos_count = sum(1 for w in tokens if w in self.positive_words)
        neg_count = sum(1 for w in tokens if w in self.negative_words)
        sens_count = sum(1 for w in self.sensational_words if w in lower_text)

        total_emotional = pos_count + neg_count
        if total_emotional == 0:
            polarity = 0.0
        else:
            polarity = round((pos_count - neg_count) / total_emotional, 2)

        # Sensationalism / subjectivity
        subjectivity = min(1.0, round((sens_count * 0.25) + (total_emotional * 0.08), 2))

        if polarity > 0.15:
            label = 'POSITIVE'
        elif polarity < -0.15:
            label = 'NEGATIVE'
        else:
            label = 'NEUTRAL'

        return {
            'polarity': polarity,
            'subjectivity': subjectivity,
            'sensationalism_score': subjectivity,
            'label': label,
            'is_sensational': subjectivity >= 0.50
        }

    def extract_named_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract categorized Named Entities: PERSON, ORGANIZATION, LOCATION, DATE, EVENT.
        """
        entities: Dict[str, List[str]] = {
            'ORGANIZATION': [],
            'LOCATION': [],
            'PERSON': [],
            'DATE': [],
            'EVENT': []
        }

        # 1. Match known organizations
        for org in self.known_orgs:
            if re.search(r'\b' + re.escape(org) + r'\b', text, re.IGNORECASE):
                if org not in entities['ORGANIZATION']:
                    entities['ORGANIZATION'].append(org)

        # 2. Match known locations
        for loc in self.known_locations:
            if re.search(r'\b' + re.escape(loc) + r'\b', text, re.IGNORECASE):
                if loc not in entities['LOCATION']:
                    entities['LOCATION'].append(loc)

        # 3. Capitalized 2-word names heuristics (potential Persons)
        candidate_persons = re.findall(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b', text)
        for p in candidate_persons:
            # Skip if already identified in orgs/locs
            if p not in entities['ORGANIZATION'] and p not in entities['LOCATION']:
                if p not in entities['PERSON'] and len(entities['PERSON']) < 4:
                    entities['PERSON'].append(p)

        # 4. Dates
        dates = re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|\b\d{4}\b|\b(?:today|yesterday|tomorrow)\b', text, re.IGNORECASE)
        for d in dates[:3]:
            if d.strip() not in entities['DATE']:
                entities['DATE'].append(d.strip())

        # 5. Events
        event_patterns = [r'\b(?:Summit|Conference|Election|Forum|Crisis|Hearing|Launch|Mission|War|Ceasefire)\b']
        for pat in event_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                if m.capitalize() not in entities['EVENT'] and len(entities['EVENT']) < 3:
                    entities['EVENT'].append(m.capitalize())

        return entities

    def detect_topics(self, text: str, top_k: int = 5) -> List[str]:
        """
        Extract dominant topics and generate clean topic hashtags.
        """
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        filtered = [w for w in words if w not in self.stop_words]

        counts = Counter(filtered)
        common = counts.most_common(top_k)

        topics = []
        for word, _ in common:
            tag = f"#{word.capitalize()}"
            topics.append(tag)

        # Add domain hashtag if strong signal exists
        if any(w in text.lower() for w in ['ai', 'gpt', 'model', 'neural', 'intel']):
            topics.insert(0, '#AI_Innovation')
        elif any(w in text.lower() for w in ['ransomware', 'cyber', 'vulnerability', 'cve']):
            topics.insert(0, '#CyberSecurity')
        elif any(w in text.lower() for w in ['space', 'telescope', 'planet', 'nasa']):
            topics.insert(0, '#SpaceScience')

        # Deduplicate preserving order
        seen = set()
        unique_topics = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                unique_topics.append(t)

        return unique_topics[:top_k]
