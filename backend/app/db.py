import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DB_PATH

def now():
    return datetime.now(timezone.utc).isoformat()

def dumps(value):
    return json.dumps(value, ensure_ascii=False)

@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    finally:
        con.close()

def initialize():
    with connection() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, title TEXT NOT NULL,
          mode TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
          retry_of TEXT REFERENCES sessions(id), snapshot TEXT NOT NULL,
          rubric_version TEXT NOT NULL, prompt_version TEXT NOT NULL, model TEXT NOT NULL,
          report TEXT, run_id TEXT, elapsed_ms INTEGER, error TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id);
        CREATE TABLE IF NOT EXISTS lookups (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
          tool TEXT NOT NULL, actor TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          kind TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, elapsed_ms INTEGER, error TEXT, trace_url TEXT, usage_json TEXT
        );
        ''')
        c.execute("UPDATE sessions SET status='active', error='서버 재시작으로 평가가 중단되었습니다. 다시 평가하세요.' WHERE status='evaluating'")
        c.execute("UPDATE runs SET status='interrupted', error='서버 재시작' WHERE status='running'")

def session(sid):
    with connection() as c:
        row = c.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
    if row is None:
        return None
    s = dict(row)
    s['snapshot'] = json.loads(s['snapshot'])
    s['report'] = json.loads(s['report']) if s['report'] else None
    s['messages'] = messages(sid)
    s['lookups'] = lookups(sid)
    return s

def messages(sid):
    with connection() as c:
        return [dict(r) for r in c.execute('SELECT * FROM messages WHERE session_id=? ORDER BY rowid', (sid,))]

def lookups(sid):
    with connection() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM lookups WHERE session_id=? ORDER BY id', (sid,))]
    for r in rows:
        r['result'] = json.loads(r['result'])
    return rows

def record_lookup(sid, tool, actor, result):
    with connection() as c:
        c.execute('INSERT INTO lookups(session_id,tool,actor,result,created_at) VALUES (?,?,?,?,?)', (sid,tool,actor,dumps(result),now()))

def list_sessions():
    with connection() as c:
        rows = c.execute('SELECT id,scenario_id,title,mode,status,created_at,retry_of,report,error,model,elapsed_ms FROM sessions ORDER BY rowid DESC LIMIT 200').fetchall()
    result=[]
    for row in rows:
        d=dict(row); report=json.loads(d.pop('report')) if d['report'] else None
        d['total']=report['total'] if report else None
        result.append(d)
    return result
