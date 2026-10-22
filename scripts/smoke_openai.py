"""Opt-in paid smoke test against your running OpenAI-mode local server."""
import json
import httpx

base='http://127.0.0.1:8000'
with httpx.Client(base_url=base,timeout=300,trust_env=False) as c:
    health=c.get('/api/health');health.raise_for_status()
    if health.json()['mode']!='openai':
        raise SystemExit('먼저 APP_MODE=openai로 서버를 실행하세요. 이 스크립트는 실제 API를 호출하고 과금됩니다.')
    s=c.post('/api/sessions',json={'scenario_id':'delivery'});s.raise_for_status();sid=s.json()['id']
    print('상담 생성:',sid)
    for kind in ('order','history','policy'):
        r=c.post(f'/api/sessions/{sid}/lookup/{kind}');r.raise_for_status()
        print('MCP 조회:',kind,'OK')
    r=c.post(f'/api/sessions/{sid}/policy-search',json={'query':'출고 전 취소와 배송 지연 보상','top_k':4});r.raise_for_status()
    assert r.json()['embedding_mode']=='openai'
    print('OpenAI 임베딩 → Chroma 정책 검색: OK', [p['id'] for p in r.json()['hits']])
    done=False
    with c.stream('POST',f'/api/sessions/{sid}/messages',json={'content':'이전 안내와 달라 불편을 드려 죄송합니다. 주문과 이전 상담을 확인했습니다. 출고 전 취소 접수가 가능하며 취소 승인 후 카드 환불은 영업일 3~5일 소요됩니다. 배송비 3000원 환급을 접수할 수 있고, 추가 보상은 관리자 검토로 이관할 수 있습니다. 어떤 절차를 원하시는지 확인하겠습니다.'}) as r:
        r.raise_for_status();event=''
        for line in r.iter_lines():
            if line.startswith('event:'):event=line[6:].strip()
            elif line.startswith('data:'):
                data=json.loads(line[5:])
                if event=='token':print(data,end='',flush=True)
                elif event=='done':done=True
                elif event=='error':raise SystemExit(data['message'])
    if not done:raise SystemExit('정상 완료 이벤트가 없습니다. 훈련 기록에서 확인하세요.')
    print('\n고객 스트리밍: OK. 평가·코칭 실행 중…')
    r=c.post(f'/api/sessions/{sid}/finish');r.raise_for_status()
    report=r.json()['report']
    print('평가·코칭·근거 검증: OK / 총점:',report['total'])
    assert report['rag']['embedding_mode']=='openai'
    print('평가 정책 RAG:',[p['id'] for p in report['rag']['hits']])
    print('브라우저 훈련 기록에서 리포트를 확인하세요:',base)
