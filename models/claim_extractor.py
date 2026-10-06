"""
Claim Extractor Module for Evidence-Grounded Fake News Verification.
Extracts check-worthy factual, numerical, and entity claims from high-attention dEFEND sentences.
"""

import re
from typing import Dict, List, Tuple


class ClaimExtractor:
    """
    Identifies and structures check-worthy claims from top dEFEND attention sentences.
    Filters out generic commentary, prioritizing verifiable assertions (numbers, named entities, dates, events).
    """

    def __init__(self, top_k: int = 3):
        self.top_k = top_k
        self.numeric_pattern = re.compile(r'\b\d+(?:\.\d+)?%?|\b(?:millions|billions|thousands|hundreds)\b', re.IGNORECASE)
        self.entity_pattern = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b')
        self.check_words = {'announced', 'discovered', 'claims', 'leaked', 'reported', 'stated', 'confirmed', 'found', 'asserts'}

    def extract_claims(self, sentences: List[str], attention_weights: List[float]) -> List[Dict]:
        """
        Extract check-worthy claims from sentences ranked by dEFEND co-attention weights.
        """
        if not sentences or not attention_weights:
            return []

        paired = []
        for i, (sent, weight) in enumerate(zip(sentences, attention_weights)):
            sent_clean = sent.strip()
            if len(sent_clean) < 15:
                continue
            
            score_boost = 0.0
            reasons = []

            if self.numeric_pattern.search(sent_clean):
                score_boost += 0.2
                reasons.append("Numerical data")

            named_entities = self.entity_pattern.findall(sent_clean)
            if named_entities and len(named_entities) >= 1:
                score_boost += 0.2
                reasons.append(f"Named entities ({', '.join(named_entities[:2])})")

            if any(cw in sent_clean.lower() for cw in self.check_words):
                score_boost += 0.15
                reasons.append("Factual assertion verb")

            combined_score = round(float(weight) + score_boost, 4)
            reason_str = ", ".join(reasons) if reasons else "High attention sentence"

            paired.append({
                'claim': sent_clean,
                'source_sentence': sent_clean,
                'sentence_index': i,
                'importance_score': round(float(weight), 4),
                'check_worthiness_score': combined_score,
                'check_worthy_reason': reason_str
            })

        paired.sort(key=lambda x: x['check_worthiness_score'], reverse=True)
        return paired[:self.top_k]


if __name__ == '__main__':
    extractor = ClaimExtractor(top_k=2)
    sents = [
        "Astronomers using NASA's James Webb Space Telescope detected signatures of water vapor.",
        "The report asserts that atmospheric pressure at Venus surface is identical to sea level on Earth.",
        "This is just a general statement with no particular claims."
    ]
    weights = [0.45, 0.40, 0.15]
    claims = extractor.extract_claims(sents, weights)
    print("Extracted Claims:")
    for c in claims:
        print(c)
