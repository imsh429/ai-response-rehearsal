import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .config import ROOT
from . import db
from langsmith import traceable

class BusinessTools:
    def __init__(self, session):
        self.session = session
        self.lock = asyncio.Lock()

    @traceable(name='mcp_business_tool', run_type='tool')
    async def call(self, name, sid, actor='trainee', **arguments):
        if name not in ('get_order','get_history','get_policy','search_policy'):
            raise ValueError('허용되지 않은 도구입니다.')
        async with self.lock:
            try:
                result = await asyncio.wait_for(self.session.call_tool(name, {'session_id':sid, **arguments}), timeout=55 if name == 'search_policy' else 15)
            except TimeoutError:
                if name == 'search_policy':
                    raise ValueError('정책 검색 시간이 초과됐습니다. MCP 연결을 확인하고 서버를 재시작하세요. 대화는 저장되어 있습니다.') from None
                raise
        if result.isError:
            if name == 'search_policy':
                # Only forward our own fixed, stage-specific error messages.
                from .rag_worker import STAGES
                raw = ' '.join(c.text for c in result.content if c.type == 'text')
                for stage in STAGES.values():
                    if stage+'.' in raw:
                        raise ValueError(f'정책 검색 실패: {stage}. 대화는 저장되어 있습니다. 서버 터미널의 [RAG] 단계 기록을 확인하세요.')
                raise ValueError('정책 검색에 실패했습니다. 서버 터미널의 [RAG] 단계 기록을 확인하세요. 대화는 저장되어 있습니다.')
            raise RuntimeError('업무 데이터 조회에 실패했습니다.')
        structured = result.structuredContent
        if structured is not None:
            data = structured if name in ('get_order', 'search_policy') else structured.get('result')
        else:
            parts = [json.loads(c.text) for c in result.content if c.type == 'text']
            data = parts[0] if name in ('get_order', 'search_policy') or (len(parts) == 1 and isinstance(parts[0], list)) else parts
        expected = dict if name in ('get_order', 'search_policy') else list
        if not isinstance(data, expected):
            raise RuntimeError('MCP 도구가 잘못된 데이터 형식을 반환했습니다.')
        db.record_lookup(sid, name, actor, data)
        return data

@asynccontextmanager
async def connect_business_tools():
    # Keep process/session lifetime inside the FastAPI lifespan task.
    env = dict(os.environ)
    # Embeddings run in the MCP subprocess; pass only needed provider credentials.
    for key in ('LANGSMITH_API_KEY','ADMIN_TOKEN'):
        env.pop(key, None)
    env['LANGSMITH_TRACING'] = 'false'
    env['DB_PATH'] = str(db.DB_PATH)
    params = StdioServerParameters(command=sys.executable, args=['-m','app.mcp_server'], cwd=str(ROOT), env=env)
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            available = await session.list_tools()
            if {t.name for t in available.tools} != {'get_order','get_history','get_policy','search_policy'}:
                raise RuntimeError('MCP 업무 도구 초기화 실패')
            yield BusinessTools(session)
