import json
from app.rag import PolicyRetriever, corpus_hash
from app.agents import fact_score


class ControlledEmbeddings:
    mode='test'
    model='controlled-v1'
    def __init__(self): self.calls=[]
    def embed(self,texts):
        self.calls.append(texts)
        return [[1.,0.,0.] if '환불' in t else [0.,1.,0.] for t in texts], {'total_tokens':len(texts)}


def test_real_vector_index_cache_and_snapshot_isolation(tmp_path):
    embedding=ControlledEmbeddings()
    retriever=PolicyRetriever(tmp_path,embedding)
    docs=[{'id':'ONE','title':'환불','text':'환불 원문'}, {'id':'TWO','title':'회원','text':'회원 원문'}]
    first=retriever.search(docs,'환불 문의',1)
    assert first['hits'][0]['id']=='ONE' and first['hits'][0]['text']=='환불 원문'
    assert not first['index_cache_hit'] and len(embedding.calls)==2
    assert retriever.search(docs,'환불',1)['index_cache_hit'] and len(embedding.calls)==3
    changed=[{**d,'text':d['text']+' 변경'} for d in docs]
    assert corpus_hash(changed)!=corpus_hash(docs)
    assert not retriever.search(changed,'환불',1)['index_cache_hit']
    assert retriever.search(docs,'환불',1)['hits'][0]['text']=='환불 원문'
    embedding.model='controlled-v2'
    assert not retriever.search(docs,'환불',1)['index_cache_hit']


def test_policy_search_api_logs_trainee_and_limits(client):
    sid=client.post('/api/sessions',json={'scenario_id':'delivery'}).json()['id']
    url=f'/api/sessions/{sid}/policy-search'
    for body in ({'query':' '},{'query':'x','top_k':9},{'query':'x'*4001}):
        assert client.post(url,json=body).status_code==422
    r=client.post(url,json={'query':'출고 전 취소와 카드 환불','top_k':4})
    assert r.status_code==200,r.text
    data=r.json()
    assert len(data['hits'])==4 and data['corpus_size']==20
    assert data['embedding_mode']=='demo-hash' and data['embedding_usage']['query'] is None
    s=client.get(f'/api/sessions/{sid}').json()
    assert s['lookups'][-1]['actor']=='trainee' and s['lookups'][-1]['tool']=='search_policy'
    assert fact_score(s['lookups'])==5
    assert fact_score([{'tool':'search_policy','actor':'evaluator'}])==0


def test_mcp_resource_prompt_and_snapshot_reference(client):
    # Execute via the real stdio client, in TestClient's event loop.
    from anyio.from_thread import start_blocking_portal
    from app.mcp_client import connect_business_tools
    sid=client.post('/api/sessions',json={'scenario_id':'delivery'}).json()['id']
    async def exercise():
        async with connect_business_tools() as tools:
            templates=await tools.session.list_resource_templates()
            assert any('policy://' in t.uriTemplate for t in templates.resourceTemplates)
            result=await tools.session.read_resource(f'policy://{sid}/REFUND-02')
            assert json.loads(result.contents[0].text)['id']=='REFUND-02'
            prompts=await tools.session.list_prompts()
            assert any(p.name=='policy_search_guide' for p in prompts.prompts)
            prompt=await tools.session.get_prompt('policy_search_guide',{'customer_question':'환불'})
            assert 'search_policy' in prompt.messages[0].content.text
    with start_blocking_portal() as portal:portal.call(exercise)


def test_openai_embedding_sdk_response_order_and_usage():
    import httpx
    from openai import OpenAI
    from app.rag import Embeddings
    requests=[]
    def respond(request):
        body=json.loads(request.content);requests.append(body)
        return httpx.Response(200,json={'object':'list','model':'text-embedding-3-small',
            'data':[{'object':'embedding','index':1,'embedding':[0.,1.]},
                    {'object':'embedding','index':0,'embedding':[1.,0.]}],
            'usage':{'prompt_tokens':7,'total_tokens':7}})
    provider=Embeddings();provider.mode='openai';provider.model='text-embedding-3-small'
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        provider.client=OpenAI(api_key='test-not-real',http_client=http)
        vectors,usage=provider.embed(['첫 문서','둘째 문서'])
    assert vectors==[[1.,0.],[0.,1.]] and usage['total_tokens']==7
    assert requests[0]['input']==['첫 문서','둘째 문서']
    assert requests[0]['model']=='text-embedding-3-small'
