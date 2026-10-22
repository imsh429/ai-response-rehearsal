"""One persistent Chroma owner, isolated from the MCP event loop.

The parent can terminate a stuck native DB operation; cancelling a thread
cannot do that. stdout is a private JSON-lines protocol, never MCP stdout.
"""
import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path
from .config import ROOT, DB_PATH

STAGES = {
    'worker_start': '검색 작업 시작',
    'chroma_import': 'Chroma 모듈 로딩',
    'chroma_init': 'Chroma 저장소 연결',
    'chroma_collection': '정책 인덱스 확인',
    'document_embeddings': '정책 문서 임베딩',
    'chroma_upsert': '정책 벡터 저장',
    'query_embeddings': '검색어 임베딩',
    'chroma_query': '정책 벡터 검색',
}


class PolicySearchWorker:
    def __init__(self, timeout=45):
        self.timeout = timeout
        self.process = None
        self.lock = asyncio.Lock()

    async def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), 3)

    async def search(self, documents, query, top_k):
        async with self.lock:
            stage = 'worker_start'
            try:
                async with asyncio.timeout(self.timeout):
                    if self.process is None or self.process.returncode is not None:
                        self.process = await asyncio.create_subprocess_exec(
                            sys.executable, '-u', '-m', 'app.rag_worker',
                            cwd=str(ROOT), stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE, limit=1024*1024,
                            # No stdout logging and no additional LangSmith roots.
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8',
                                 'LANGSMITH_TRACING': 'false'},
                        )
                    payload = {'documents': documents, 'query': query, 'top_k': top_k}
                    self.process.stdin.write((json.dumps(payload, ensure_ascii=False)+'\n').encode('utf-8'))
                    await self.process.stdin.drain()
                    while True:
                        line = await self.process.stdout.readline()
                        if not line:
                            raise RuntimeError('WORKER_EXITED')
                        frame = json.loads(line)
                        if frame.get('type') == 'stage':
                            stage = frame['stage'] if frame['stage'] in STAGES else stage
                        elif frame.get('type') == 'result':
                            return frame['data']
                        elif frame.get('type') == 'error':
                            raise RuntimeError(frame.get('error_type', 'WorkerError'))
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as exc:
                await self.close()
                # Type/stage only. Provider errors may contain sensitive data.
                label = '시간 초과' if isinstance(exc, TimeoutError) else '실패'
                raise ValueError(f'정책 검색 {label}: {STAGES[stage]}. '
                                 '대화는 저장되어 있습니다. 서버 터미널의 [RAG] 단계 기록을 확인하세요.') from None


def main():
    wire = sys.stdout.buffer

    def emit(frame):
        wire.write((json.dumps(frame, ensure_ascii=False)+'\n').encode('utf-8'))
        wire.flush()

    def progress(stage):
        emit({'type': 'stage', 'stage': stage})
        print('[RAG] '+stage, file=sys.stderr, flush=True)

    retriever = None
    for line in sys.stdin.buffer:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                if retriever is None:
                    progress('chroma_import')
                    from .rag import PolicyRetriever
                    # Keep an old, potentially interrupted local index intact.
                    # A single long-lived worker owns this new runtime cache.
                    path = Path(os.getenv('RAG_DB_PATH', str(DB_PATH.parent/'chroma-runtime-v2')))
                    retriever = PolicyRetriever(path=path, progress=progress)
                data = retriever.search(request['documents'], request['query'], request['top_k'])
            emit({'type': 'result', 'data': data})
        except Exception as exc:
            print('[RAG] failed '+type(exc).__name__, file=sys.stderr, flush=True)
            emit({'type': 'error', 'error_type': type(exc).__name__})


if __name__ == '__main__':
    main()
