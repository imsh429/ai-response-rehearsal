import asyncio
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.callbacks import UsageMetadataCallbackHandler
from . import db
from .config import MODE, MODEL, MAX_TURNS, RUBRIC_VERSION, PROMPT_VERSION, ADMIN_TOKEN, validate_settings
from .seed import SCENARIOS, scenario_by_id, snapshot
from .schemas import SessionRequest, MessageRequest
from .mcp_client import connect_business_tools
from .agents import TrainingEngine
from .schemas import PolicySearchRequest

log=logging.getLogger('rehearsal')
busy=set()

@asynccontextmanager
async def lifespan(app):
    validate_settings()
    db.initialize()
    async with connect_business_tools() as tools:
        app.state.tools=tools
        app.state.engine=TrainingEngine(tools)
        yield

app=FastAPI(title='응대 리허설',version='1.0.0',lifespan=lifespan)

def require_session(sid):
    s=db.session(sid)
    if not s:
        raise HTTPException(404,'상담 세션을 찾을 수 없습니다.')
    return s

def admin_auth(x_admin_token: str = Header(default='')):
    if not ADMIN_TOKEN or not hmac.compare_digest(x_admin_token,ADMIN_TOKEN):
        raise HTTPException(401,'관리자 코드가 올바르지 않습니다.')

def public_session(s):
    return {key:s[key] for key in ('id','scenario_id','title','mode','model','status','created_at','retry_of','rubric_version','prompt_version','report','run_id','elapsed_ms','error','messages','lookups')} | {'scenario_version':s['snapshot']['version']}

def create_session(snap,retry_of=None):
    sid=str(uuid4())
    with db.connection() as c:
        c.execute('INSERT INTO sessions(id,scenario_id,title,mode,status,created_at,retry_of,snapshot,rubric_version,prompt_version,model) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (sid,snap['id'],snap['title'],MODE,'active',db.now(),retry_of,db.dumps(snap),RUBRIC_VERSION,PROMPT_VERSION,MODEL if MODE=='openai' else 'rule-based-demo'))
        c.execute('INSERT INTO messages VALUES (?,?,?,?,?)',(str(uuid4()),sid,'assistant',snap['opening'],db.now()))
    return public_session(require_session(sid))

def begin_run(sid,kind):
    rid=str(uuid4())
    with db.connection() as c:
        c.execute('INSERT INTO runs(id,session_id,kind,mode,status,created_at) VALUES (?,?,?,?,?,?)',(rid,sid,kind,MODE,'running',db.now()))
    return rid

def finish_run(rid,started,status='success',error=None,usage=None):
    ms=round((time.monotonic()-started)*1000)
    with db.connection() as c:
        c.execute('UPDATE runs SET status=?,elapsed_ms=?,error=?,usage_json=? WHERE id=?',(status,ms,error,db.dumps(usage or {}),rid))
    return ms

def run_config(s,rid,usage):
    return {'run_id':rid,'run_name':'rehearsal_'+('evaluation' if s.get('status')=='evaluating' else 'customer'),
        'recursion_limit':12,'callbacks':[usage],
        'metadata':{'session_id':s['id'],'thread_id':s['id'],'scenario_id':s['scenario_id'],'mode':MODE,'retry_of':s['retry_of'],'rubric_version':s['rubric_version'],'prompt_version':s['prompt_version']},
        'tags':['rehearsal',MODE,s['scenario_id']]}

def friendly_error(exc):
    name=type(exc).__name__
    if name=='AuthenticationError':
        return 'OpenAI 인증 실패: backend/.env의 API 키를 확인하고 서버를 재시작하세요.'
    if name=='RateLimitError':
        return 'OpenAI 사용 한도 또는 API 크레딧을 확인하세요. 잠시 후 다시 시도할 수 있습니다.'
    if name in ('APITimeoutError','TimeoutError'):
        return 'AI 응답 시간이 초과됐습니다. 잠시 후 다시 시도하세요.'
    if name=='NotFoundError':
        return '설정한 OpenAI 모델에 접근할 수 없습니다. OPENAI_MODEL과 계정 권한을 확인하세요.'
    if name=='APIConnectionError':
        return 'OpenAI에 연결하지 못했습니다. 인터넷 연결을 확인하세요.'
    if isinstance(exc,ValueError) and str(exc).startswith(('평가의','개선 답변의','정책 평가는','AI 고객이')):
        return str(exc)
    return '요청을 완료하지 못했습니다. 입력·모델 설정을 확인한 뒤 다시 시도하세요. 오류 유형: '+name

@app.get('/api/health')
def health():
    return {'status':'ok','mode':MODE,'model':MODEL if MODE=='openai' else 'rule-based-demo','mcp':'connected','tracing':os.getenv('LANGSMITH_TRACING','false').lower()=='true','max_turns':MAX_TURNS}

@app.get('/api/scenarios')
def scenarios():
    keys=('id','title','subtitle','icon','difficulty','minutes','color','brief')
    return [{k:s[k] for k in keys} for s in SCENARIOS]

@app.post('/api/sessions',status_code=201)
def start_session(body:SessionRequest):
    return create_session(snapshot(body.scenario_id))

@app.get('/api/sessions')
def history():
    return db.list_sessions()

@app.get('/api/sessions/{sid}')
def get_session(sid:str):
    return public_session(require_session(sid))

@app.post('/api/sessions/{sid}/lookup/{kind}')
async def lookup(sid:str,kind:str,request:Request):
    s=require_session(sid)
    if kind not in ('order','history','policy'):
        raise HTTPException(404,'지원하지 않는 조회 항목입니다.')
    if s['status']!='active' or sid in busy:
        raise HTTPException(409,'응답 또는 평가가 끝난 후 조회하세요.')
    busy.add(sid)
    try:
        data=await request.app.state.tools.call('get_'+kind,sid)
        return {'kind':kind,'data':data}
    except Exception as e:
        raise HTTPException(503,friendly_error(e)) from None
    finally:
        busy.discard(sid)

@app.post('/api/sessions/{sid}/policy-search')
async def policy_search(sid:str, body:PolicySearchRequest, request:Request):
    s=require_session(sid)
    if not body.query.strip():
        raise HTTPException(422,'검색어를 입력하세요.')
    if s['status']!='active' or sid in busy:
        raise HTTPException(409,'응답 또는 평가가 끝난 후 검색하세요.')
    busy.add(sid)
    try:
        return await request.app.state.tools.call('search_policy',sid,query=body.query,top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(503,friendly_error(exc)) from None
    finally:
        busy.discard(sid)

@app.post('/api/sessions/{sid}/messages')
async def send_message(sid:str,body:MessageRequest,request:Request):
    s=require_session(sid)
    if s['status']!='active' or sid in busy:
        raise HTTPException(409,'진행 중인 응답 또는 평가를 먼저 마쳐 주세요.')
    if sum(m['role']=='user' for m in s['messages'])>=MAX_TURNS:
        raise HTTPException(409,'최대 20턴에 도달했습니다. 상담을 종료하고 평가받으세요.')
    busy.add(sid)
    rid=begin_run(sid,'customer')
    started=time.monotonic()
    usage=UsageMetadataCallbackHandler()
    user={'id':str(uuid4()),'session_id':sid,'role':'user','content':body.content,'created_at':db.now()}
    state={'operation':'chat','session_id':sid,'snapshot':s['snapshot'],'messages':s['messages']+[user]}
    queue=asyncio.Queue()

    async def produce():
        parts=[]
        try:
            async with asyncio.timeout(110):
                async for item in request.app.state.engine.graph.astream(state,config=run_config(s,rid,usage),stream_mode='custom'):
                    if item.get('event')=='token':
                        parts.append(item['data'])
                        await queue.put(item)
            text=''.join(parts).strip()
            if not text:
                raise ValueError('AI 고객이 빈 응답을 반환했습니다.')
            assistant={'id':str(uuid4()),'session_id':sid,'role':'assistant','content':text,'created_at':db.now()}
            # Commit the entire turn atomically, never a partial AI response.
            with db.connection() as c:
                for m in (user,assistant):
                    c.execute('INSERT INTO messages VALUES (?,?,?,?,?)',tuple(m[k] for k in ('id','session_id','role','content','created_at')))
                c.execute('UPDATE sessions SET error=NULL WHERE id=?',(sid,))
            finish_run(rid,started,usage=usage.usage_metadata)
            await queue.put({'event':'done','data':{'message':assistant,'user_message':user,'run_id':rid}})
        except asyncio.CancelledError:
            finish_run(rid,started,'cancelled','연결 중단',usage.usage_metadata)
            raise
        except Exception as exc:
            error=friendly_error(exc)
            finish_run(rid,started,'error',error,usage.usage_metadata)
            with db.connection() as c:
                c.execute('UPDATE sessions SET error=? WHERE id=?',(error,sid))
            await queue.put({'event':'error','data':{'message':error}})
        finally:
            await queue.put(None)

    async def events():
        task=asyncio.create_task(produce())
        try:
            while True:
                try:
                    item=await asyncio.wait_for(queue.get(),timeout=10)
                except TimeoutError:
                    yield ': heartbeat\n\n'
                    continue
                if item is None:
                    break
                yield 'event: '+item['event']+'\ndata: '+json.dumps(item['data'],ensure_ascii=False)+'\n\n'
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            busy.discard(sid)
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no'})

@app.post('/api/sessions/{sid}/finish')
async def finish(sid:str,request:Request):
    s=require_session(sid)
    if s['status']=='completed':
        return public_session(s)
    if s['status']!='active' or sid in busy:
        raise HTTPException(409,'진행 중인 요청이 있습니다.')
    if not any(m['role']=='user' for m in s['messages']):
        raise HTTPException(400,'상담사 답변을 한 번 이상 작성한 뒤 평가하세요.')
    busy.add(sid)
    rid=begin_run(sid,'evaluation');started=time.monotonic();usage=UsageMetadataCallbackHandler()
    s['status']='evaluating'
    with db.connection() as c:
        c.execute("UPDATE sessions SET status='evaluating',error=NULL WHERE id=?",(sid,))
    try:
        state={'operation':'evaluate','session_id':sid,'snapshot':s['snapshot'],'messages':s['messages']}
        async with asyncio.timeout(240):
            result=await request.app.state.engine.graph.ainvoke(state,config=run_config(s,rid,usage))
        ms=finish_run(rid,started,usage=usage.usage_metadata)
        with db.connection() as c:
            c.execute("UPDATE sessions SET status='completed',report=?,run_id=?,elapsed_ms=?,error=NULL WHERE id=?",(db.dumps(result['report']),rid,ms,sid))
        return public_session(require_session(sid))
    except asyncio.CancelledError:
        finish_run(rid,started,'cancelled','평가 중단',usage.usage_metadata)
        with db.connection() as c:
            c.execute("UPDATE sessions SET status='active',error='평가가 중단되었습니다. 다시 평가하세요.' WHERE id=?",(sid,))
        raise
    except Exception as exc:
        error=friendly_error(exc)
        finish_run(rid,started,'error',error,usage.usage_metadata)
        with db.connection() as c:
            c.execute("UPDATE sessions SET status='active',error=? WHERE id=?",(error,sid))
        raise HTTPException(502,error) from None
    finally:
        busy.discard(sid)

@app.post('/api/sessions/{sid}/retry',status_code=201)
def retry(sid:str):
    s=require_session(sid)
    if s['status']!='completed':
        raise HTTPException(409,'평가 완료 후 재도전할 수 있습니다.')
    # Keep scenario/policy/rubric/prompts/model comparable across attempts.
    if s['mode']!=MODE or s['rubric_version']!=RUBRIC_VERSION or s['prompt_version']!=PROMPT_VERSION or s['model']!=(MODEL if MODE=='openai' else 'rule-based-demo'):
        raise HTTPException(409,'모드·모델·평가 기준이 변경되어 직접 비교할 수 없습니다. 새 훈련을 시작하세요.')
    return create_session(s['snapshot'],sid)

@app.get('/api/sessions/{sid}/comparison')
def comparison(sid:str):
    s=require_session(sid)
    if not s['retry_of'] or not s['report']:
        return None
    prev=require_session(s['retry_of'])
    if not prev['report']:
        return None
    before={c['key']:c['score'] for c in prev['report']['criteria']}
    return {'previous_id':prev['id'],'previous_total':prev['report']['total'],'current_total':s['report']['total'],'delta':s['report']['total']-prev['report']['total'],
        'criteria':[{'key':c['key'],'before':before[c['key']],'after':c['score'],'delta':c['score']-before[c['key']]} for c in s['report']['criteria']]}

@app.get('/api/admin/overview')
def admin_overview(x_admin_token:str=Header(default='')):
    admin_auth(x_admin_token)
    with db.connection() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM runs ORDER BY rowid DESC LIMIT 100')]
    for r in rows:
        r['usage']=json.loads(r.pop('usage_json') or '{}')
    sessions=db.list_sessions();completed=[s for s in sessions if s['total'] is not None]
    return {'sessions':sessions,'runs':rows,'stats':{'sessions':len(sessions),'completed':len(completed),'average':round(sum(s['total'] for s in completed)/len(completed),1) if completed else 0,'errors':sum(r['status']=='error' for r in rows)},
        'tracing':os.getenv('LANGSMITH_TRACING','false').lower()=='true','langsmith_url':'https://smith.langchain.com','project':os.getenv('LANGSMITH_PROJECT','default')}

@app.get('/api/{rest:path}',include_in_schema=False)
def unknown_api(rest:str):
    raise HTTPException(404,'API 경로를 찾을 수 없습니다.')

DIST=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if DIST.exists():
    app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
