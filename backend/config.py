"""
Configuration file for dEFEND Explainable Fake News Detection Research Project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / '.env')

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5001))
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Directory Structure
DATA_DIR = PROJECT_ROOT / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'
SAMPLES_DATA_DIR = DATA_DIR / 'samples'
EVIDENCE_CORPUS_DIR = DATA_DIR / 'evidence_corpus'
MODELS_DIR = PROJECT_ROOT / 'models'
SERVICES_DIR = PROJECT_ROOT / 'services'
CHECKPOINTS_DIR = PROJECT_ROOT / 'checkpoints'
EXPERIMENTS_DIR = PROJECT_ROOT / 'experiments'

# System Operation Mode
DEMO_MODE = os.getenv('DEMO_MODE', 'True').lower() == 'true'
USE_ONLINE_SEARCH = os.getenv('USE_ONLINE_SEARCH', 'False').lower() == 'true'

# dEFEND Hyperparameters
MAX_SENTENCES_PER_DOC = 15
MAX_WORDS_PER_SENTENCE = 30
MAX_COMMENTS_PER_DOC = 10
MAX_WORDS_PER_COMMENT = 30
EMBEDDING_DIM = 100
HIDDEN_DIM = 64
ATTENTION_DIM = 64
BATCH_SIZE = 16
LEARNING_RATE = 0.001
EPOCHS = 10

# API Keys
NEWSAPI_KEY         = os.getenv('NEWSAPI_KEY', '')
SEARCH_API_KEY      = os.getenv('SEARCH_API_KEY', '')

# Reddit OAuth2 (free — create an app at https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID     = os.getenv('REDDIT_CLIENT_ID', '')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')
REDDIT_USER_AGENT    = os.getenv('REDDIT_USER_AGENT', 'dEFEND-News-Collector/1.0')

# Twitter/X Bearer Token (optional — requires paid plan)
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')
