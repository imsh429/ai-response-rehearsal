"""Regression tests: generated text must never be required to duplicate an original."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app.agents import (
    TrainingEngine, evidence_catalog, resolve_evaluation, resolve_coaching,
    trainee_references, validate_report, EvidenceSelectionError,
)

MESSAGES = [
    {'id':'customer-uuid','role':'assistant','content':'어제는 “오늘 도착”이라고 했잖아요!'},
    {'id':'trainee-uuid','role':'user','content':'너나 잘해라\n  그렇게는 안 돼요. “정책”을 확인할게요…'},
]
SOURCES = {
    'customer-uuid':MESSAGES[0]['content'],
    'trainee-uuid':MESSAGES[1]['content'],
    'REFUND-02':'승인 후 3~5일이 소요됩니다.\n\n즉시 환불은 보장하지 않습니다.',
    'LOOKUPS':'상담사가 조회한 도구: get_order, get_history, get_policy',
}
CATALOG=evidence_catalog(SOURCES,MESSAGES)
IDS={item['kind']:item['id'] for item in CATALOG}
SELECTION={'summary':'원문 복사 없이 근거를 선택합니다.','criteria':[
    {'key':key,'score':12,'reason':'근거에 따라 판단했습니다.',
     'evidence_ids':[IDS['policy'],IDS['trainee']] if key=='policy' else [IDS['trainee']],
     'action':'정확한 절차를 안내하세요.'}
    for key in ('facts','policy','solution','communication')]}
COACHING={'strengths':['평가를 통해 개선할 부분을 확인할 수 있습니다.'],
          'next_actions':['불편을 인정하는 표현을 먼저 사용하세요.'],
          'rewrites':[{'message_ref':'M001','improved':'불편을 드려 죄송합니다. 먼저 정책을 확인하겠습니다.','reason':'공격적 표현을 줄입니다.'}]}


def test_exact_quotes_and_rewrite_original_are_attached_by_server():
    evaluation=resolve_evaluation(SELECTION,CATALOG)
    coaching=resolve_coaching(COACHING,trainee_references(MESSAGES))
    assert coaching['rewrites'][0]['original']==MESSAGES[1]['content']
    assert coaching['rewrites'][0]['message_id']=='trainee-uuid'
    assert next(c for c in evaluation['criteria'] if c['key']=='policy')['evidence'][1]['quote']==MESSAGES[1]['content']
    validate_report(evaluation,coaching,SOURCES,MESSAGES)


def test_long_unicode_sources_are_exact_slices():
    sources={'REFUND-02':('공백  두 개\n줄바꿈과 “따옴표”, …, 이모지🙂 ')*40}
    catalog=evidence_catalog(sources,[])
    assert len(catalog)>1
    assert ''.join(x['quote'] for x in catalog)==sources['REFUND-02']
    assert all(x['quote'] in sources[x['source_id']] for x in catalog)


@pytest.mark.parametrize('bad_id',['E999','REFUND-02','trainee-uuid',''])
def test_unknown_evidence_still_rejected(bad_id):
    data=deepcopy(SELECTION);data['criteria'][0]['evidence_ids']=[bad_id]
    with pytest.raises((ValueError,EvidenceSelectionError)):
        resolve_evaluation(data,CATALOG)


@pytest.mark.parametrize('kind',['trainee','policy','customer'])
def test_policy_requires_real_policy_and_trainee_evidence(kind):
    data=deepcopy(SELECTION);data['criteria'][1]['evidence_ids']=[IDS[kind]]
    with pytest.raises(EvidenceSelectionError,match='POLICY_REQUIRES_TWO_SOURCES'):
        resolve_evaluation(data,CATALOG)


def test_coaching_cannot_select_customer_or_invent_message():
    data=deepcopy(COACHING);data['rewrites'][0]['message_ref']='customer-uuid'
    with pytest.raises(EvidenceSelectionError,match='UNKNOWN_MESSAGE_REF'):
        resolve_coaching(data,trainee_references(MESSAGES))


class StubAgent:
    def __init__(self,outputs):self.outputs=iter(outputs);self.calls=[]
    async def ainvoke(self,payload,config=None):
        import json
        self.calls.append(json.loads(payload['messages'][0]['content']))
        return {'structured_response':next(self.outputs)}


@pytest.mark.asyncio
async def test_evaluation_repairs_invalid_selection_once(monkeypatch):
    import app.agents as agents
    monkeypatch.setattr(agents,'MODE','openai')
    engine=TrainingEngine.__new__(TrainingEngine)
    bad=deepcopy(SELECTION);bad['criteria'][0]['evidence_ids']=['E999']
    engine.evaluator=StubAgent([bad,SELECTION])
    state={'messages':MESSAGES,'sources':SOURCES,'verified_fact_score':10}
    result=await engine.evaluate_node(state)
    assert len(engine.evaluator.calls)==2
    assert 'UNKNOWN_EVIDENCE_ID' in engine.evaluator.calls[1]['validation_feedback']
    assert next(c for c in result['evaluation']['criteria'] if c['key']=='facts')['score']==10


@pytest.mark.asyncio
async def test_evaluation_never_swallows_persistent_fabrication(monkeypatch):
    import app.agents as agents
    monkeypatch.setattr(agents,'MODE','openai')
    engine=TrainingEngine.__new__(TrainingEngine)
    bad=deepcopy(SELECTION);bad['criteria'][0]['evidence_ids']=['E999']
    engine.evaluator=StubAgent([bad,bad,SELECTION])
    with pytest.raises(ValueError,match='대화는 저장되어'):
        await engine.evaluate_node({'messages':MESSAGES,'sources':SOURCES,'verified_fact_score':25})
    assert len(engine.evaluator.calls)==2


@pytest.mark.asyncio
async def test_coaching_repairs_reference_and_server_supplies_original(monkeypatch):
    import app.agents as agents
    monkeypatch.setattr(agents,'MODE','openai')
    engine=TrainingEngine.__new__(TrainingEngine)
    bad=deepcopy(COACHING);bad['rewrites'][0]['message_ref']='M999'
    engine.coach=StubAgent([bad,COACHING])
    result=await engine.coach_node({'messages':MESSAGES,'sources':SOURCES,'evaluation':resolve_evaluation(SELECTION,CATALOG)})
    assert len(engine.coach.calls)==2
    assert result['coaching']['rewrites'][0]['original']==MESSAGES[1]['content']
