"""
NLP Processor Service for India-Focused News Analysis.
Implements:
1. Category Classification (Technology, Politics, National, International, Business, Science, FactCheck, IndiaEconomy)
2. Sentiment Analysis (Polarity, Subjectivity/Sensationalism, Classification)
3. Named-Entity Recognition (PERSON, ORGANIZATION, LOCATION, DATE, EVENT) — India-aware
4. Topic & Keyphrase Detection — India-specific hashtags
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
                'phishing': 3.0, 'cert-in': 3.5, 'cyberattack': 3.5, 'ddos': 3.0,
                'trojan': 3.0, 'exploit': 2.8, 'cyber': 2.5, 'firewall': 2.2,
                'encryption': 2.2, 'infosec': 3.0, 'threat actor': 3.5, 'apt': 3.0,
                'patch': 2.0, 'backdoor': 3.2, 'spyware': 3.0, 'data leak': 2.8,
                'meity': 2.8, 'it act': 3.0, 'digital fraud': 2.8, 'sim swap': 2.5,
            },
            'Technology': {
                'ai': 2.5, 'artificial intelligence': 3.5, 'algorithm': 2.2, 'software': 2.0,
                'hardware': 2.0, 'semiconductor': 3.0, 'chip': 2.0, 'startup': 2.2,
                'isro': 3.0, 'chandrayaan': 3.5, 'gaganyaan': 3.5, 'drdo': 2.8,
                'infosys': 2.2, 'wipro': 2.2, 'tcs': 2.2, 'hcl': 2.0,
                'bengaluru': 2.0, 'tech park': 2.2, 'iit': 2.5, 'robotics': 2.8,
                'llm': 3.2, 'neural network': 3.0, 'deeptech': 2.8, 'computing': 2.0,
                'upi': 2.5, 'fintech': 2.8, 'digital india': 3.0, 'iot': 2.2,
                'open-source': 2.2, 'virtual reality': 2.5, 'autonomous': 2.2,
            },
            'Science': {
                'isro': 3.2, 'space': 2.2, 'telescope': 2.8, 'astronomy': 3.0,
                'chandrayaan': 3.5, 'gaganyaan': 3.5, 'aditya': 3.0, 'mars orbiter': 3.5,
                'iit': 2.5, 'iiser': 2.8, 'csir': 2.8, 'dbt': 2.2,
                'biology': 2.5, 'climate': 2.2, 'gene': 2.8, 'crispr': 3.5,
                'fossil': 2.8, 'laboratory': 2.0, 'researchers': 1.8,
                'scientists': 2.0, 'experiment': 2.0, 'ocean': 1.8,
                'ecosystem': 2.2, 'species': 2.2, 'dna': 2.8,
            },
            'Politics': {
                'parliament': 3.0, 'lok sabha': 3.5, 'rajya sabha': 3.5,
                'election': 3.0, 'bjp': 3.0, 'congress': 2.8, 'aap': 2.5,
                'modi': 2.8, 'rahul gandhi': 2.8, 'amit shah': 2.8,
                'chief minister': 2.5, 'governor': 2.2, 'mla': 2.8, 'mp': 2.2,
                'election commission': 3.2, 'evm': 3.0, 'bypolls': 2.8,
                'cabinet': 2.5, 'minister': 2.2, 'ruling party': 2.5,
                'opposition': 2.5, 'no-confidence': 3.2, 'budget session': 2.8,
                'supreme court': 2.8, 'high court': 2.5, 'verdict': 2.5,
                'constitution': 2.8, 'article 370': 3.5, 'referendum': 2.8,
            },
            'Business': {
                'sensex': 3.2, 'nifty': 3.2, 'bse': 2.8, 'nse': 2.8,
                'rupee': 2.5, 'rbi': 3.0, 'sebi': 3.0, 'repo rate': 3.0,
                'gdp': 2.8, 'inflation': 2.5, 'gst': 3.0, 'budget': 2.8,
                'ipo': 3.2, 'unicorn': 2.8, 'startup india': 3.0,
                'reliance': 2.5, 'tata': 2.2, 'adani': 2.5, 'hdfc': 2.5,
                'revenue': 2.8, 'profit': 2.5, 'quarter': 1.8, 'earnings': 2.8,
                'fdi': 3.0, 'export': 2.2, 'import': 2.2, 'trade deficit': 2.8,
                'mutual fund': 2.5, 'bond yield': 2.5, 'rupee depreciation': 2.8,
            },
            'International': {
                'united nations': 3.2, 'treaty': 2.8, 'global': 1.8,
                'nato': 3.2, 'eu': 2.2, 'asean': 3.0, 'saarc': 3.0,
                'pakistan': 2.8, 'china': 2.5, 'bangladesh': 2.5, 'nepal': 2.5,
                'sri lanka': 2.5, 'myanmar': 2.5, 'bhutan': 2.2,
                'sanctions': 3.0, 'diplomacy': 2.8, 'bilateral': 2.8,
                'geopolitics': 3.2, 'embassy': 2.8, 'consulate': 2.5,
                'g20': 3.0, 'g7': 2.8, 'quad': 3.0, 'brics': 3.0,
                'line of actual control': 3.5, 'lac': 3.0, 'border dispute': 2.8,
            },
            'National': {
                'india': 1.5, 'indian': 1.5, 'bharat': 2.0, 'central government': 2.5,
                'state government': 2.2, 'nationwide': 2.2, 'domestic': 2.0,
                'infrastructure': 2.0, 'public safety': 2.5, 'census': 2.8,
                'highway': 2.0, 'national highway': 2.5, 'metro': 2.0,
                'district': 1.8, 'cbi': 2.8, 'ed enforcement': 3.0,
                'income tax': 2.8, 'aadhaar': 2.8, 'jan dhan': 2.8,
                'swachh bharat': 2.8, 'make in india': 2.8, 'atmanirbhar': 2.8,
            },
            'Sports': {
                'cricket': 3.5, 'bcci': 3.5, 'ipl': 3.5, 'test match': 3.0,
                'wicket': 3.0, 'batting': 2.8, 'bowling': 2.8, 'century': 2.8,
                'odi': 3.0, 't20': 3.0, 'icc': 3.2, 'rohit sharma': 3.0,
                'virat kohli': 3.0, 'bumrah': 3.0, 'hardik pandya': 2.8,
                'football': 2.8, 'isl': 3.0, 'fifa': 3.0, 'olympics': 3.2,
                'badminton': 3.0, 'pv sindhu': 3.0, 'neeraj chopra': 3.5,
                'hockey': 3.0, 'asian games': 3.2, 'kabaddi': 3.0,
                'pro kabaddi': 3.0, 'chess': 3.0, 'grandmaster': 3.0,
                'praggnanandhaa': 3.2, 'gukesh': 3.2, 'tournament': 2.2,
                'champion': 2.5, 'medal': 2.8, 'athletics': 2.5,
            },
            'Entertainment': {
                'bollywood': 3.5, 'tollywood': 3.2, 'kollywood': 3.2,
                'box office': 3.2, 'cinema': 3.0, 'movie': 2.8, 'film': 2.5,
                'actor': 2.5, 'actress': 2.5, 'director': 2.2, 'trailer': 2.8,
                'ott': 3.0, 'netflix': 2.5, 'prime video': 2.5, 'teaser': 2.5,
                'celebrity': 2.5, 'album': 2.2, 'music': 2.2, 'singer': 2.2,
                'concert': 2.5, 'theatre': 2.2, 'blockbuster': 3.0,
            },
            'FactCheck': {
                'fake news': 4.0, 'fact check': 4.0, 'misinformation': 3.8,
                'disinformation': 3.8, 'debunked': 3.5, 'hoax': 3.5,
                'misleading': 3.2, 'rumor': 3.0, 'false claim': 3.5,
                'altnews': 3.5, 'factchecker': 3.5, 'boomlive': 3.5,
                'vishvasnews': 3.0, 'misattributed': 3.0, 'deepfake': 3.2,
                'edited video': 3.0, 'out of context': 3.0, 'no evidence': 3.0,
                'propaganda': 2.8, 'manipulated': 2.8, 'fabricated': 3.2,
            },
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

        # Known entity lists for fast high-accuracy NER — India-focused
        self.known_orgs = {
            # Indian government & agencies
            'ISRO', 'DRDO', 'RBI', 'SEBI', 'CBI', 'ED', 'NIA', 'NCB', 'RAW',
            'IB', 'NITI Aayog', 'Planning Commission', 'Election Commission',
            'Supreme Court', 'High Court', 'CAG', 'NHRC', 'UPSC', 'UIDAI',
            # Political parties
            'BJP', 'INC', 'Congress', 'AAP', 'TMC', 'SP', 'BSP', 'NCP',
            'JDU', 'RJD', 'DMK', 'AIADMK', 'TRS', 'YSR Congress', 'Shiv Sena',
            # Indian corporates
            'Reliance', 'Tata', 'Adani', 'Infosys', 'Wipro', 'TCS', 'HCL',
            'HDFC', 'ICICI', 'SBI', 'LIC', 'ONGC', 'BHEL', 'HAL',
            'Flipkart', 'Zomato', 'Paytm', 'Ola', 'Nykaa', 'Meesho',
            # Indian media / fact-check
            'NDTV', 'Times of India', 'The Hindu', 'Indian Express', 'Hindustan Times',
            'AltNews', 'FactChecker', 'Boom Live', 'Vishvas News',
            # International (relevant to India)
            'Google', 'Microsoft', 'Apple', 'Meta', 'Amazon', 'Samsung',
            'WHO', 'UN', 'IMF', 'World Bank', 'ADB', 'WTO',
        }
        self.known_locations = {
            # Indian cities
            'Delhi', 'New Delhi', 'Mumbai', 'Bengaluru', 'Bangalore', 'Hyderabad',
            'Chennai', 'Kolkata', 'Pune', 'Ahmedabad', 'Jaipur', 'Lucknow',
            'Surat', 'Kanpur', 'Nagpur', 'Indore', 'Bhopal', 'Patna',
            'Vadodara', 'Ghaziabad', 'Ludhiana', 'Coimbatore', 'Agra', 'Meerut',
            'Vishakhapatnam', 'Varanasi', 'Srinagar', 'Chandigarh', 'Amritsar',
            'Mysuru', 'Kochi', 'Thiruvananthapuram', 'Bhubaneswar', 'Guwahati',
            # Indian states / UTs
            'Uttar Pradesh', 'Maharashtra', 'Bihar', 'West Bengal', 'Madhya Pradesh',
            'Rajasthan', 'Gujarat', 'Karnataka', 'Odisha', 'Telangana',
            'Andhra Pradesh', 'Kerala', 'Jharkhand', 'Assam', 'Punjab',
            'Haryana', 'Chhattisgarh', 'Uttarakhand', 'Himachal Pradesh',
            'Tripura', 'Meghalaya', 'Manipur', 'Nagaland', 'Mizoram', 'Arunachal Pradesh',
            'Sikkim', 'Goa', 'Ladakh', 'Jammu', 'Kashmir',
            # Countries relevant to India
            'India', 'Pakistan', 'China', 'Bangladesh', 'Nepal', 'Sri Lanka',
            'Myanmar', 'Bhutan', 'United States', 'Russia', 'Israel',
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

        # Add India-specific domain hashtags
        if any(w in text.lower() for w in ['isro', 'chandrayaan', 'gaganyaan', 'aditya', 'mars orbiter']):
            topics.insert(0, '#IndiaSpace')
        elif any(w in text.lower() for w in ['bjp', 'congress', 'election', 'lok sabha', 'modi', 'parliament']):
            topics.insert(0, '#IndiaPolitics')
        elif any(w in text.lower() for w in ['sensex', 'nifty', 'rbi', 'rupee', 'gst', 'budget']):
            topics.insert(0, '#IndiaEconomy')
        elif any(w in text.lower() for w in ['startup', 'unicorn', 'fintech', 'upi', 'bengaluru', 'iit']):
            topics.insert(0, '#IndiaTech')
        elif any(w in text.lower() for w in ['fake news', 'fact check', 'debunked', 'hoax', 'misinformation']):
            topics.insert(0, '#FactCheck')
        elif any(w in text.lower() for w in ['ransomware', 'cyber', 'vulnerability', 'cve', 'cert-in']):
            topics.insert(0, '#CyberSecurity')
        elif any(w in text.lower() for w in ['ai', 'gpt', 'model', 'neural', 'intel']):
            topics.insert(0, '#AI_Innovation')

        # Deduplicate preserving order
        seen = set()
        unique_topics = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                unique_topics.append(t)

        return unique_topics[:top_k]
