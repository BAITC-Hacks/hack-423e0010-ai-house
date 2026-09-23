import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{(DATA_DIR / "platform.db").as_posix()}')
DATASET_PATH = Path(os.getenv('DATASET_PATH', str(ROOT / 'project-df' / 'hackathon dataset anonymized .csv')))
API_KEY = os.getenv('OPENAI_API_KEY', '')
API_BASE = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
CHAT_MODEL = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4.1-mini')
EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'local')
EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
SENTENCE_MODEL = os.getenv('SENTENCE_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
CALENDAR_START = '2026-09-23'
CALENDAR_END = '2026-12-31'

