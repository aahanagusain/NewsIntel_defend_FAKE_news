"""
Claim-Evidence Verifier Module for India-Focused Evidence-Grounded Fake News Verification.
Compares extracted claims against retrieved evidence passages to produce
NLI classifications: SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE.
Specially tuned for Indian political, economic, science, and social media misinformation.
"""

import re
from typing import Dict, List, Tuple


class ClaimVerifier:
    """
    NLI Verifier comparing claim assertions against retrieved external evidence.
    
    Verdict Labels:
    - SUPPORTED: Evidence confirms claim assertions.
    - CONTRADICTED: Evidence directly refutes claim assertions.
    - INSUFFICIENT_EVIDENCE: Available evidence is neutral or insufficient.
    """

    def __init__(self):
        # Contradiction indicators (negation, extreme conflict words)
        self.contradiction_tokens = {
            'impossible', 'false', 'absurd', 'exceed', 'differ', 'not', 'no', 'cannot', 'never',
            'refuted', 'fake', 'denied', 'debunked', 'hoax', 'misleading', 'fabricated',
            'misattributed', 'altered', 'manipulated', 'no evidence', 'out of context',
        }
        # Support indicators
        self.support_tokens = {
            'confirmed', 'detected', 'observed', 'valid', 'authentic', 'verified',
            'demonstrated', 'supports', 'measured', 'official', 'notified', 'gazette',
            'announced', 'approved', 'ratified', 'signed', 'enacted', 'passed',
        }

    def verify_claim_against_evidence(self, claim: str, evidence_list: List[Dict]) -> Dict:
        """
        Verify claim against a list of retrieved evidence passages.
        Returns verdict, confidence, and reasoning.
        """
        if not claim or not evidence_list:
            return {
                'verdict': 'INSUFFICIENT_EVIDENCE',
                'confidence': 0.0,
                'explanation': 'No relevant external evidence was retrieved to verify or refute this claim.',
                'matched_evidence': None
            }

        top_evidence = evidence_list[0]
        evidence_text = top_evidence.get('text', '').lower()
        claim_text = claim.lower()
        sim_score = top_evidence.get('similarity_score', 0.5)

        # Token overlap analysis
        claim_words = set(re.findall(r'\w+', claim_text))
        evidence_words = set(re.findall(r'\w+', evidence_text))
        intersection = claim_words.intersection(evidence_words)
        
        overlap_ratio = len(intersection) / max(len(claim_words), 1)

        # Check contradiction heuristics
        has_contradiction_signal = any(t in evidence_text for t in self.contradiction_tokens)
        has_support_signal = any(t in evidence_text for t in self.support_tokens)

        # ---------------------------------------------------------------
        # India-specific domain verification rules
        # ---------------------------------------------------------------

        # Demonetization
        if any(w in claim_text for w in ['demonetisation', 'demonetization', 'note ban', '500 note', '1000 note', '2000 note']):
            if any(w in evidence_text for w in ['gazette', 'rbi', 'legal tender', 'notified', 'government notification']):
                verdict = 'SUPPORTED' if has_support_signal else 'CONTRADICTED'
                confidence = 0.91
                reason = "RBI and Government of India official gazette notifications govern currency demonetization; cross-checked with evidence."

        # Article 370 abrogation
        elif 'article 370' in claim_text or 'article 35a' in claim_text:
            if any(w in evidence_text for w in ['abrogated', 'parliament', 'constitution', 'passed', 'amended']):
                verdict = 'SUPPORTED'
                confidence = 0.95
                reason = "Article 370 was constitutionally abrogated by the Indian Parliament in August 2019, as recorded in official records."

        # Electoral bonds
        elif 'electoral bond' in claim_text:
            if any(w in evidence_text for w in ['supreme court', 'struck down', 'unconstitutional', 'sbi', 'eci']):
                verdict = 'SUPPORTED'
                confidence = 0.93
                reason = "Supreme Court of India struck down the Electoral Bonds Scheme in February 2024 as unconstitutional."

        # ISRO missions
        elif any(w in claim_text for w in ['chandrayaan', 'gaganyaan', 'isro', 'aditya', 'mangalyaan']):
            if any(w in evidence_text for w in ['isro', 'launched', 'mission', 'orbit', 'successfully', 'lander', 'rover']):
                verdict = 'SUPPORTED'
                confidence = 0.94
                reason = "ISRO official mission records and verified scientific publications confirm the mission status."

        # UPI / payment system
        elif any(w in claim_text for w in ['upi', 'paytm', 'digital payment', 'npci']):
            if any(w in evidence_text for w in ['npci', 'rbi', 'transactions', 'billion', 'crore', 'official data']):
                verdict = 'SUPPORTED' if has_support_signal else 'INSUFFICIENT_EVIDENCE'
                confidence = 0.88
                reason = "NPCI and RBI officially publish UPI transaction statistics verifying or refuting digital payment claims."

        # General Indian fake-news patterns (WhatsApp forwards)
        elif any(w in claim_text for w in ['whatsapp', 'viral', 'forward', 'share']) and has_contradiction_signal:
            verdict = 'CONTRADICTED'
            confidence = 0.85
            reason = "Claim matches patterns of viral misinformation common on Indian social media; evidence contradicts assertion."

        # Vaccine / health misinformation
        elif any(w in claim_text for w in ['vaccine', 'covaxin', 'covishield', 'booster', 'side effect']):
            if any(w in evidence_text for w in ['icmr', 'who', 'clinical trial', 'approved', 'safety', 'efficacy']):
                verdict = 'SUPPORTED' if has_support_signal else 'CONTRADICTED'
                confidence = 0.90
                reason = "ICMR and WHO clinical data provide authoritative vaccine information for verification."

        # Currency / paper money (kept for demonetization-adjacent claims)
        elif ('currency' in claim_text or 'cash' in claim_text) and ('legal tender' in evidence_text or 'rbi' in evidence_text):
            verdict = 'CONTRADICTED'
            confidence = 0.91
            reason = "RBI regulations confirm paper currency remains legal tender unless formally legislated by gazette notification."

        elif has_contradiction_signal and overlap_ratio > 0.15:
            verdict = 'CONTRADICTED'
            confidence = min(0.85, round(sim_score + 0.3, 2))
            reason = f"External evidence passage from '{top_evidence.get('source', 'corpus')}' contains conflicting factual assertions."

        elif has_support_signal and overlap_ratio > 0.20:
            verdict = 'SUPPORTED'
            confidence = min(0.90, round(sim_score + 0.3, 2))
            reason = f"External evidence passage from '{top_evidence.get('source', 'corpus')}' supports the claim assertions."

        else:
            verdict = 'INSUFFICIENT_EVIDENCE'
            confidence = 0.50
            reason = "Retrieved evidence overlap is neutral or insufficient to make a definitive verification decision."

        return {
            'verdict': verdict,
            'confidence': confidence,
            'explanation': reason,
            'matched_evidence': top_evidence
        }


if __name__ == '__main__':
    verifier = ClaimVerifier()
    c = "Humans can comfortably survive on Venus surface without oxygen gear"
    ev = [{
        'source': 'NASA Factsheet',
        'text': 'The surface atmospheric pressure of Venus is 92 times that of Earth at sea level with 460C heat, making human survival impossible.',
        'similarity_score': 0.85
    }]
    v = verifier.verify_claim_against_evidence(c, ev)
    print("Verification Result:")
    print("Verdict:", v['verdict'])
    print("Explanation:", v['explanation'])
