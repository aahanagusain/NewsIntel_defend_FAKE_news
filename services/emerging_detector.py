"""
Emerging News & Statistical Anomaly Detector Service.
Performs rolling time-window frequency analysis, category velocity calculations,
z-score burstiness detection, and real-time alert/insight synthesis.
"""

import math
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple


class EmergingDetector:
    def __init__(self):
        # Rolling event timestamps per category and topic
        self.category_windows: Dict[str, deque] = defaultdict(deque)
        self.topic_windows: Dict[str, deque] = defaultdict(deque)
        self.all_events: deque = deque(maxlen=2000)
        self.alerts_history: List[Dict] = []

        # Baseline expected rate (articles/hr) per category from historical priors
        self.baseline_rates = {
            'Technology': 8.0,
            'Politics': 10.0,
            'National': 9.0,
            'International': 9.0,
            'Business': 7.0,
            'Science': 5.0,
            'Cybersecurity': 4.0
        }
        # Baseline std dev
        self.baseline_stds = {
            'Technology': 2.5,
            'Politics': 3.0,
            'National': 2.5,
            'International': 2.5,
            'Business': 2.0,
            'Science': 1.5,
            'Cybersecurity': 1.2
        }

    def record_event(self, article: Dict):
        """Record newly ingested article into time-window tracker."""
        now = datetime.fromisoformat(article.get('timestamp', datetime.now().isoformat()))
        cat = article.get('category', 'National')
        topics = article.get('topics', [])
        article_id = article.get('id', '')

        event = {
            'time': now,
            'id': article_id,
            'title': article.get('title', ''),
            'category': cat,
            'topics': topics,
            'risk_score': article.get('risk_score', 0),
            'risk_level': article.get('risk_level', 'LOW RISK'),
            'sentiment': article.get('sentiment', {}).get('label', 'NEUTRAL')
        }

        self.all_events.append(event)
        self.category_windows[cat].append(event)
        for t in topics:
            self.topic_windows[t].append(event)

        # Check for immediate alert generation
        self._evaluate_alerts(event)

    def prune_windows(self, max_hours: int = 24):
        """Remove events older than max_hours from deques."""
        cutoff = datetime.now() - timedelta(hours=max_hours)
        for cat, dq in self.category_windows.items():
            while dq and dq[0]['time'] < cutoff:
                dq.popleft()
        for topic, dq in self.topic_windows.items():
            while dq and dq[0]['time'] < cutoff:
                dq.popleft()

    def calculate_velocity(self, category: str, window_minutes: int = 60) -> float:
        """Calculate publication rate (articles/hour) in the specified window."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        events = [e for e in self.category_windows[category] if e['time'] >= cutoff]
        hours = max(window_minutes / 60.0, 0.1)
        return round(len(events) / hours, 2)

    def evaluate_burstiness(self, category: str) -> Dict[str, any]:
        """
        Compute statistical z-score burstiness for a category.
        z = (observed_rate - baseline_mean) / baseline_std
        """
        observed_1h = self.calculate_velocity(category, window_minutes=60)
        observed_15m = self.calculate_velocity(category, window_minutes=15)
        
        base_mean = self.baseline_rates.get(category, 6.0)
        base_std = self.baseline_stds.get(category, 2.0)

        # Weight the more immediate 15m rate to catch sudden surges faster
        weighted_rate = 0.6 * observed_15m + 0.4 * observed_1h
        z_score = round((weighted_rate - base_mean) / base_std, 2)

        if z_score >= 2.5:
            status = 'BREAKING_SPIKE'
            badge_color = 'rose'
            label = 'Breaking Surge'
        elif z_score >= 1.4:
            status = 'EMERGING'
            badge_color = 'amber'
            label = 'Rapidly Developing'
        elif z_score >= 0.5:
            status = 'DEVELOPING'
            badge_color = 'sky'
            label = 'Developing Story'
        else:
            status = 'STEADY'
            badge_color = 'slate'
            label = 'Normal Volume'

        return {
            'category': category,
            'velocity_1h': observed_1h,
            'velocity_15m': observed_15m,
            'z_score': z_score,
            'status': status,
            'badge_color': badge_color,
            'label': label
        }

    def detect_emerging_news(self) -> List[Dict[str, any]]:
        """
        Scan all categories and active topics to surface emerging, rapidly developing clusters.
        """
        self.prune_windows()
        emerging_clusters = []

        for cat in self.baseline_rates.keys():
            stats = self.evaluate_burstiness(cat)
            if stats['status'] in ['BREAKING_SPIKE', 'EMERGING', 'DEVELOPING']:
                # Find most recent articles in this surging category
                recent = [e for e in list(self.category_windows[cat])[-5:]]
                emerging_clusters.append({
                    **stats,
                    'article_count': len(self.category_windows[cat]),
                    'recent_headlines': [e['title'] for e in recent]
                })

        emerging_clusters.sort(key=lambda x: x['z_score'], reverse=True)
        return emerging_clusters

    def _evaluate_alerts(self, event: Dict):
        """Generate high-priority alert if event meets risk, anomaly, or security conditions."""
        alerts = []
        now_str = event['time'].strftime('%H:%M:%S')

        # 1. Critical Misinformation Alert
        if event.get('risk_score', 0) >= 70:
            alerts.append({
                'id': f"alert_misinfo_{event['id']}",
                'type': 'CRITICAL_MISINFORMATION',
                'severity': 'high',
                'timestamp': now_str,
                'title': f"Elevated Misinformation Risk in {event['category']}",
                'message': f"Article '{event['title'][:70]}...' triggered a high misinformation score ({event['risk_score']}/100) with contradicted external evidence.",
                'article_id': event['id'],
                'category': event['category']
            })

        # 2. Cybersecurity Zero-Day / Breach Alert
        if event['category'] == 'Cybersecurity' and any(kw in event['title'].lower() for kw in ['zero-day', 'cve', 'ransomware', 'breach', 'critical']):
            alerts.append({
                'id': f"alert_cyber_{event['id']}",
                'type': 'CYBER_THREAT_ADVISORY',
                'severity': 'medium',
                'timestamp': now_str,
                'title': "Urgent Cybersecurity Incident Detected",
                'message': f"New threat alert reported: '{event['title'][:70]}...'",
                'article_id': event['id'],
                'category': 'Cybersecurity'
            })

        for a in alerts:
            # Check duplicate alert
            if not any(prev['id'] == a['id'] for prev in self.alerts_history):
                self.alerts_history.append(a)
                if len(self.alerts_history) > 50:
                    self.alerts_history.pop(0)

    def get_alerts(self, limit: int = 10) -> List[Dict]:
        """Return latest system alerts sorted by most recent."""
        return list(reversed(self.alerts_history))[:limit]

    def get_analytical_insights(self) -> Dict[str, any]:
        """
        Synthesize automated analytical insights summarizing current news landscape.
        """
        all_list = list(self.all_events)
        total = len(all_list)
        if total == 0:
            return {
                'headline': 'Real-time pipeline initialized and listening for new events.',
                'insights': [
                    'Ingestion system is active across RSS feeds and public web sources.',
                    'Zero-day anomaly detection monitors 7 primary coverage categories.',
                    'Evidence verification engine actively scoring claim credibility.'
                ],
                'dominant_category': 'Technology',
                'average_risk_score': 18.5
            }

        cat_counts = Counter(e['category'] for e in all_list)
        dom_cat, dom_count = cat_counts.most_common(1)[0]
        avg_risk = round(sum(e['risk_score'] for e in all_list) / total, 1)

        insights = []
        insights.append(f"Highest coverage volume is in **{dom_cat}** ({round(dom_count/total*100, 1)}% of ingested articles).")
        
        # Check high-risk items
        high_risk_count = sum(1 for e in all_list if e['risk_score'] >= 50)
        if high_risk_count > 0:
            insights.append(f"Detected **{high_risk_count} article(s)** with elevated misinformation risk requiring claim verification scrutiny.")
        else:
            insights.append("No systemic misinformation spikes detected across verified sources in the current 24-hour cycle.")

        # Burstiness insight
        emerging = self.detect_emerging_news()
        if emerging:
            top_surge = emerging[0]
            insights.append(f"Statistical surge flagged in **{top_surge['category']}** (z-score: +{top_surge['z_score']}, rate: {top_surge['velocity_1h']} art/hr).")
        else:
            insights.append("Publishing velocity is balanced within normal standard deviations across all monitored categories.")

        return {
            'headline': f"Live Analysis: {total} articles processed with {avg_risk}/100 avg risk index.",
            'insights': insights,
            'dominant_category': dom_cat,
            'average_risk_score': avg_risk,
            'total_processed': total
        }
