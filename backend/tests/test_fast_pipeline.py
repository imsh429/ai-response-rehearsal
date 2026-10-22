"""Regression coverage for policy-search stalls and duplicate LLM context."""
import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app import db
from app.agents import (coaching_payload, evaluation_payload, evidence_catalog,
                        evidence_sources)
from app.mcp_client import connect_business_tools
from app.rag import PolicyRetriever
from app.rag_worker import PolicySearchWorker
from test_rag import ControlledEmbeddings


def test_repeated_query_avoids_embedding_call_and_invalidates_on_model_change(tmp_path):
    embedding = ControlledEmbeddings()
    retriever = PolicyRetriever(tmp_path, embedding)
    docs = [{'id':'REFUND', 'title':'환불', 'text':'승인 후 환불'}]
    first = retriever.search(docs, '환불 문의', 1)
    count = len(embedding.calls)
    cached = retriever.search(docs, '환불 문의', 1)
    assert len(embedding.calls) == count
    assert first['hits'] == cached['hits']
    assert cached['query_cache_hit'] and cached['index_cache_hit']
    assert cached['embedding_usage'] == {'index':None, 'query':None}
    embedding.model = 'different-model'
    assert not retriever.search(docs, '환불 문의', 1)['query_cache_hit']
    assert len(embedding.calls) == count + 2


def test_worker_kills_stuck_native_operation_and_can_restart(monkeypatch):
    real_spawn = asyncio.create_subprocess_exec
    children = []
    # A real OS child, simulating a native call which ignores cancellation.
    script = ("import json,time; print(json.dumps({'type':'stage',"
              "'stage':'chroma_query'}),flush=True); time.sleep(60)")

    async def stalled_spawn(*args, **kwargs):
        child = await real_spawn(sys.executable, '-u', '-c', script, **kwargs)
        children.append(child)
        return child

    async def exercise():
        worker = PolicySearchWorker(timeout=0.5)
        started = time.monotonic()
        with monkeypatch.context() as patch:
            patch.setattr(asyncio, 'create_subprocess_exec', stalled_spawn)
            with pytest.raises(ValueError, match='정책 벡터 검색'):
                await worker.search([], '환불', 1)
        assert time.monotonic()-started < 3
        assert children[0].returncode is not None and worker.process is None
        worker.timeout = 20
        try:
            result = await worker.search([{'id':'ONE','title':'환불','text':'환불 원문'}], '환불', 1)
            assert result['hits'][0]['text'] == '환불 원문'
            assert result['embedding_mode'] == 'demo-hash'
        finally:
            await worker.close()

    asyncio.run(exercise())


def test_actual_mcp_worker_openai_protocol_and_cache_without_paid_api(client, monkeypatch, tmp_path):
    """Real stdio MCP + real Chroma + real SDK against a local fake provider."""
    requests = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            vectors = [[1.,0.,0.] if '환불' in t else [0.,1.,0.] for t in body['input']]
            result = {'object':'list', 'model':body['model'],
                      'data':[{'object':'embedding','index':i,'embedding':v}
                              for i,v in enumerate(vectors)],
                      'usage':{'prompt_tokens':7, 'total_tokens':7}}
            output = json.dumps(result).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(output)))
            self.end_headers()
            self.wfile.write(output)

        def log_message(self, *args):
            pass

    sid = client.post('/api/sessions', json={'scenario_id':'delivery'}).json()['id']
    server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('APP_MODE','openai')
    monkeypatch.setenv('OPENAI_API_KEY','test-not-real')
    monkeypatch.setenv('OPENAI_BASE_URL',f'http://127.0.0.1:{server.server_port}/v1')
    monkeypatch.setenv('RAG_DB_PATH',str(tmp_path/'isolated-chroma'))
    # The isolated test provider is local; do not inherit the host SOCKS proxy.
    for key in ('ALL_PROXY', 'all_proxy'):
        monkeypatch.delenv(key, raising=False)

    async def exercise():
        async with connect_business_tools() as tools:
            first = await tools.call('search_policy',sid,query='출고 전 환불',top_k=4)
            second = await tools.call('search_policy',sid,query='출고 전 환불',top_k=4)
            assert first['embedding_mode'] == 'openai' and len(first['hits']) == 4
            assert first['embedding_usage']['query']['total_tokens'] == 7
            assert second['query_cache_hit'] and second['embedding_usage']['query'] is None
            assert first['hits'] == second['hits']
            assert (await tools.call('get_order',sid))['id'] == 'ORD-1001'

    try:
        asyncio.run(exercise())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert len(requests) == 2  # initial corpus + initial query; repeat has no paid call


def test_compact_payload_keeps_every_original_and_resolves_all_refs(client):
    sid = client.post('/api/sessions',json={'scenario_id':'delivery'}).json()['id']
    # Use the real finished demo report as the source of valid evidence.
    client.post(f'/api/sessions/{sid}/messages',json={'content':'확인 후 취소 절차를 안내하겠습니다.'})
    result = client.post(f'/api/sessions/{sid}/finish').json()
    session = db.session(sid)
    report = result['report']
    sources = report['sources']
    state = {'messages':session['messages'], 'sources':sources, 'evaluation':report}
    catalog = evidence_catalog(sources, session['messages'])
    reduced = evaluation_payload(catalog,0)
    assert [x['quote'] for x in reduced['evidence_catalog']] == [x['quote'] for x in catalog]
    assert all('source_id' not in x for x in reduced['evidence_catalog'])
    coach = coaching_payload(state)
    assert [x['content'] for x in coach['messages']] == [x['content'] for x in session['messages']]
    assert set(coach['context']) == set(sources)-{m['id'] for m in session['messages']}
    valid_refs = set(coach['context']) | {m['message_ref'] for m in coach['messages']}
    for criterion in coach['evaluation']['criteria']:
        assert set(criterion['evidence_refs']) <= valid_refs
    assert next(m for m in coach['messages'] if m['role']=='user')['message_ref'] == 'M001'


def test_search_error_is_specific_and_does_not_leak_provider_error(client, monkeypatch):
    sid = client.post('/api/sessions',json={'scenario_id':'delivery'}).json()['id']
    graph = client.app.state.engine.graph

    async def broken(*args, **kwargs):
        raise ValueError('정책 검색 실패: 검색어 임베딩. 대화는 저장되어 있습니다.')

    client.post(f'/api/sessions/{sid}/messages',json={'content':'확인하겠습니다.'})
    with monkeypatch.context() as patch:
        patch.setattr(graph, 'ainvoke', broken)
        result = client.post(f'/api/sessions/{sid}/finish')
    assert result.status_code == 502 and '검색어 임베딩' in result.json()['detail']
    assert client.get(f'/api/sessions/{sid}').json()['status'] == 'active'
