"""python scripts/check_setup.py : local configuration check, no paid call."""
import importlib.metadata
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import validate_settings, MODE, MODEL
try:
    validate_settings()
    print('설정 확인: OK')
    print('모드:',MODE,'/ 모델:',MODEL)
    print('OpenAI 키:', '입력됨 (유효성은 실제 호출 시 확인)' if os.getenv('OPENAI_API_KEY') else '없음')
    print('LangSmith:', '활성' if os.getenv('LANGSMITH_TRACING','false').lower()=='true' else '비활성')
    print('포함된 화면:', '있음' if (ROOT/'frontend/dist/index.html').is_file() else '없음 — frontend에서 npm ci 및 npm run build 필요')
    for name in ('fastapi','langchain','langgraph','mcp','langchain-openai','chromadb'):
        print(name,importlib.metadata.version(name))
    print('다음 명령: python run.py → http://127.0.0.1:8000')
except Exception as e:
    print('설정 확인 실패:',e)
    raise SystemExit(1)
