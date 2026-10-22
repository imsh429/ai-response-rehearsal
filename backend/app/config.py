import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)
DB_PATH = Path(os.getenv('DB_PATH', str(ROOT / 'data' / 'rehearsal.db'))).resolve()
MODE = os.getenv('APP_MODE', 'openai').lower()
MODEL = os.getenv('OPENAI_MODEL', 'gpt-5-mini')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'local-admin-2026')
MAX_TURNS = 20
RUBRIC_VERSION = 'rubric-1.0'
PROMPT_VERSION = 'prompts-1.2-fast-rag'

def validate_settings():
    if MODE not in ('openai', 'demo'):
        raise RuntimeError('APP_MODE는 openai 또는 demo여야 합니다.')
    if MODE == 'openai' and not os.getenv('OPENAI_API_KEY', '').strip():
        raise RuntimeError('backend/.env에 OPENAI_API_KEY를 입력하세요. 화면 점검만 하려면 APP_MODE=demo로 설정하세요.')
    if os.getenv('LANGSMITH_TRACING', 'false').lower() == 'true' and not os.getenv('LANGSMITH_API_KEY'):
        raise RuntimeError('LANGSMITH_TRACING=true이면 LANGSMITH_API_KEY가 필요합니다.')
