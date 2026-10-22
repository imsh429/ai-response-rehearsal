import json
import pytest
from app import db
from app.main import busy
from app.agents import validate_report


def new(client,scenario='delivery'):
    r=client.post('/api/sessions',json={'scenario_id':scenario})
    assert r.status_code==201,r.text
    return r.json()

def send(client,sid,text='불편을 드려 죄송합니다. 사실을 확인하고 가능한 접수 절차를 안내하겠습니다.'):
    r=client.post(f'/api/sessions/{sid}/messages',json={'content':text})
    assert r.status_code==200,r.text
    events=[]
    for frame in r.text.split('\n\n'):
        if not frame.startswith('event:'):continue
        lines=frame.splitlines()
        events.append((lines[0][7:],json.loads(lines[1][6:])))
    assert any(e[0]=='token' for e in events)
    assert events[-1][0]=='done',r.text
    tokens=''.join(e[1] for e in events if e[0]=='token')
    assert tokens==events[-1][1]['message']['content']
    return events

@pytest.mark.parametrize('scenario',['delivery','return','promise'])
def test_complete_workflow_with_real_mcp(client,scenario):
    s=new(client,scenario);sid=s['id']
    assert 'snapshot' not in s
    for kind,expected in [('order',dict),('history',list),('policy',list)]:
        r=client.post(f'/api/sessions/{sid}/lookup/{kind}')
        assert r.status_code==200,r.text
        assert isinstance(r.json()['data'],expected)
    send(client,sid)
    r=client.post(f'/api/sessions/{sid}/finish')
    assert r.status_code==200,r.text
    finished=r.json();report=finished['report']
    assert finished['status']=='completed'
    assert report['is_demo'] is True
    assert report['total']==sum(x['score'] for x in report['criteria'])
    assert next(x['score'] for x in report['criteria'] if x['key']=='facts')==25
    assert len(finished['messages'])==3
    assert len([x for x in finished['lookups'] if x['actor']=='trainee'])==3
    assert len([x for x in finished['lookups'] if x['actor']=='evaluator'])==3
    # Finishing twice is idempotent, not a second charged evaluation.
    assert client.post(f'/api/sessions/{sid}/finish').json()['report']==report
    assert client.post(f'/api/sessions/{sid}/messages',json={'content':'추가 답변'}).status_code==409
    child=client.post(f'/api/sessions/{sid}/retry').json()
    assert child['retry_of']==sid
    assert len(child['messages'])==1 and child['lookups']==[]
    assert db.session(child['id'])['snapshot']==db.session(sid)['snapshot']
    send(client,child['id'],'죄송합니다. 확인 후 접수 절차를 안내하겠습니다.')
    assert client.post(f"/api/sessions/{child['id']}/finish").status_code==200
    compare=client.get(f"/api/sessions/{child['id']}/comparison").json()
    assert compare['previous_id']==sid
    assert next(c['after'] for c in compare['criteria'] if c['key']=='facts')==0


def test_evaluator_lookups_do_not_count_as_trainee(client):
    sid=new(client)['id'];send(client,sid)
    r=client.post(f'/api/sessions/{sid}/finish').json()
    assert next(c['score'] for c in r['report']['criteria'] if c['key']=='facts')==0
    assert r['report']['sources']['LOOKUPS']=='상담사가 조회한 도구: 없음'


def test_input_validation_and_state_guards(client):
    sid=new(client)['id']
    assert client.post('/api/sessions',json={'scenario_id':'unknown'}).status_code==422
    assert client.post(f'/api/sessions/{sid}/finish').status_code==400
    assert client.post(f'/api/sessions/{sid}/retry').status_code==409
    for text in ['', '  ', 'x'*2001]:
        assert client.post(f'/api/sessions/{sid}/messages',json={'content':text}).status_code==422
    assert client.get('/api/sessions/no-such-id').status_code==404
    assert client.post(f'/api/sessions/{sid}/lookup/execute_refund').status_code==404
    busy.add(sid)
    try:
        assert client.post(f'/api/sessions/{sid}/messages',json={'content':'안녕하세요'}).status_code==409
        assert client.post(f'/api/sessions/{sid}/lookup/order').status_code==409
        assert client.post(f'/api/sessions/{sid}/finish').status_code==409
    finally:busy.discard(sid)


def test_turn_limit(client):
    from uuid import uuid4
    sid=new(client)['id']
    with db.connection() as c:
        for i in range(20):
            c.execute('INSERT INTO messages VALUES (?,?,?,?,?)',(str(uuid4()),sid,'user',str(i),db.now()))
    assert client.post(f'/api/sessions/{sid}/messages',json={'content':'21번째 메시지'}).status_code==409


def test_admin_and_usage_records(client):
    assert client.get('/api/admin/overview').status_code==401
    r=client.get('/api/admin/overview',headers={'X-Admin-Token':'test-admin'})
    assert r.status_code==200
    assert r.json()['stats']['completed']>=1
    assert r.json()['runs'][0]['status']=='success'
    assert 'usage' in r.json()['runs'][0]
    assert client.get('/api/no-such-api').status_code==404


def test_evidence_and_rewrite_validation_rejects_fabrications(client):
    sid=new(client)['id'];send(client,sid)
    s=client.post(f'/api/sessions/{sid}/finish').json();r=s['report']
    validate_report(r,r['coaching'],r['sources'],s['messages'])
    bad=json.loads(json.dumps(r))
    bad['criteria'][0]['evidence'][0]['source_id']='FAKE-POLICY'
    with pytest.raises(ValueError):validate_report(bad,r['coaching'],r['sources'],s['messages'])
    bad=json.loads(json.dumps(r));bad['criteria'][0]['evidence'][0]['quote']='실제로 하지 않은 발언'
    with pytest.raises(ValueError):validate_report(bad,r['coaching'],r['sources'],s['messages'])
    bad=json.loads(json.dumps(r['coaching']));bad['rewrites'][0]['original']='가짜 원문'
    with pytest.raises(ValueError):validate_report(r,bad,r['sources'],s['messages'])


def test_sse_failure_does_not_commit_partial_turn(client,monkeypatch):
    sid=new(client)['id'];graph=client.app.state.engine.graph
    async def broken(*args,**kwargs):
        yield {'event':'token','data':'일부 생성'}
        raise RuntimeError('secret-do-not-expose')
    with monkeypatch.context() as patch:
        patch.setattr(graph,'astream',broken)
        r=client.post(f'/api/sessions/{sid}/messages',json={'content':'안녕하세요'})
    assert 'event: error' in r.text
    assert 'secret-do-not-expose' not in r.text
    assert len(client.get(f'/api/sessions/{sid}').json()['messages'])==1
    assert sid not in busy
    send(client,sid)


def test_evaluation_failure_is_retryable(client,monkeypatch):
    sid=new(client)['id'];send(client,sid);graph=client.app.state.engine.graph
    async def broken(*args,**kwargs):raise RuntimeError('secret-do-not-expose')
    with monkeypatch.context() as patch:
        patch.setattr(graph,'ainvoke',broken)
        r=client.post(f'/api/sessions/{sid}/finish')
    assert r.status_code==502 and 'secret-do-not-expose' not in r.text
    assert client.get(f'/api/sessions/{sid}').json()['status']=='active'
    assert sid not in busy
    assert client.post(f'/api/sessions/{sid}/finish').status_code==200


def test_openai_sdk_streaming_and_structured_agents_with_mock_transport(client,monkeypatch):
    """Exercise real ChatOpenAI + create_agent protocols without a paid API key."""
    import httpx
    import app.agents as agents
    from langchain_openai import ChatOpenAI
    sid=new(client)['id']
    seen=[]
    text='말씀하신 절차는 알겠어요. 결과가 언제 나오는지도 설명해 주세요.'

    def handler(request):
        body=json.loads(request.content);seen.append(body)
        if body.get('stream'):
            chunks=[]
            for token in [text[:14],text[14:]]:
                chunks.append('data: '+json.dumps({'id':'chatcmpl-mock','object':'chat.completion.chunk','created':1,'model':'gpt-5-mini','choices':[{'index':0,'delta':{'role':'assistant','content':token},'finish_reason':None}]},ensure_ascii=False)+'\n\n')
            chunks.append('data: '+json.dumps({'id':'chatcmpl-mock','object':'chat.completion.chunk','created':1,'model':'gpt-5-mini','choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n')
            return httpx.Response(200,headers={'content-type':'text/event-stream'},content=''.join(chunks).encode())
        name=body['tools'][0]['function']['name']
        data=json.loads(body['messages'][-1]['content'])
        if name=='EvaluationSelection':
            catalog=data['evidence_catalog']
            trainee=next(x['id'] for x in catalog if x['kind']=='trainee')
            policy=next(x['id'] for x in catalog if x['kind']=='policy')
            lookup=next(x['id'] for x in catalog if x['kind']=='lookups')
            out={'summary':'실제 근거를 선택한 모의 평가입니다.','criteria':[
                {'key':key,'score':min(18,data['verified_fact_score']) if key=='facts' else 18,
                 'reason':'제공된 자료와 발언을 대조했습니다.',
                 'evidence_ids':[policy,trainee] if key=='policy' else [lookup] if key=='facts' else [trainee],
                 'action':'다음 절차를 구체적으로 안내하세요.'}
                for key in ('facts','policy','solution','communication')]}
        else:
            m=next(m for m in data['messages'] if m['role']=='user')
            out={'strengths':['먼저 상황을 확인하려 했습니다.'],'next_actions':['후속 절차를 구체적으로 안내하세요.'],'rewrites':[{'message_ref':m['message_ref'],'improved':'불편을 드려 죄송합니다. 주문과 이전 안내를 먼저 확인하겠습니다.','reason':'사실 확인을 먼저 안내합니다.'}]}
        return httpx.Response(200,json={'id':'chatcmpl-mock','object':'chat.completion','created':1,'model':'gpt-5-mini','choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[{'id':'call_mock','type':'function','function':{'name':name,'arguments':json.dumps(out,ensure_ascii=False)}}]},'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':20,'completion_tokens':30,'total_tokens':50}})

    def factory(**kwargs):
        return ChatOpenAI(**kwargs,api_key='test-key-not-real',http_client=httpx.Client(transport=httpx.MockTransport(handler)),http_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with monkeypatch.context() as patch:
        patch.setattr(agents,'MODE','openai')
        patch.setattr(agents,'ChatOpenAI',factory)
        engine=agents.TrainingEngine(client.app.state.tools)
        patch.setattr(client.app.state,'engine',engine)
        events=send(client,sid)
        assert events[-1][1]['message']['content']==text
        r=client.post(f'/api/sessions/{sid}/finish')
        assert r.status_code==200,r.text
        assert r.json()['report']['is_demo'] is False
    assert len(seen)==3
    assert seen[0]['model']=='gpt-5-mini'
    assert seen[1]['tools'][0]['function']['name']=='EvaluationSelection'
    assert seen[2]['tools'][0]['function']['name']=='CoachingSelection'
