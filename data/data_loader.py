"""
Data loader module for dEFEND Explainable Fake News Detection project.
Supports loading FakeNewsNet datasets (gossipcop, politifact) and sample datasets.
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))
import config

logger = logging.getLogger(__name__)


class DatasetLoader:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or config.DATA_DIR
        self.samples_dir = config.SAMPLES_DATA_DIR

    def load_samples(self) -> List[Dict]:
        """Load local sample articles with user comments for demo and testing."""
        sample_path = self.samples_dir / 'sample_articles.json'
        if not sample_path.exists():
            logger.warning("Sample articles file not found at %s", sample_path)
            return []
        
        with open(sample_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_fakenewsnet(self) -> pd.DataFrame:
        """
        Load FakeNewsNet dataset files if present locally in raw data dir.
        Falls back to generating sample dataset if raw files are missing.
        """
        raw_dir = config.RAW_DATA_DIR
        files_and_labels = [
            ("gossipcop_fake.csv", 1, "fakenewsnet_gossipcop_fake"),
            ("gossipcop_real.csv", 0, "fakenewsnet_gossipcop_real"),
            ("politifact_fake.csv", 1, "fakenewsnet_politifact_fake"),
            ("politifact_real.csv", 0, "fakenewsnet_politifact_real"),
        ]

        frames = []
        found_any = False
        for filename, label, source in files_and_labels:
            file_path = raw_dir / filename
            if file_path.exists():
                found_any = True
                df = pd.read_csv(file_path)
                title_col = df.get('title', pd.Series([''] * len(df))).fillna('')
                text_col = df.get('text', pd.Series([''] * len(df))).fillna('')
                full_text = title_col + " " + text_col
                
                frames.append(pd.DataFrame({
                    'id': df.get('id', pd.Series(range(len(df)))),
                    'content': full_text.str.strip(),
                    'label': label,
                    'source': source,
                    'comments': df.get('comments', pd.Series([[]] * len(df)))
                }))

        if found_any and frames:
            return pd.concat(frames, ignore_index=True)

        logger.info("FakeNewsNet raw files not found. Using sample articles pipeline.")
        samples = self.load_samples()
        return pd.DataFrame(samples)


if __name__ == '__main__':
    loader = DatasetLoader()
    df = loader.load_fakenewsnet()
    print(f"Loaded dataset rows: {len(df)}")
