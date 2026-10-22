import os
import tempfile
from pathlib import Path
import sys
# Tests never call a paid provider or send traces.
os.environ['APP_MODE']='demo'
os.environ['LANGSMITH_TRACING']='false'
os.environ['ADMIN_TOKEN']='test-admin'
_temp=tempfile.TemporaryDirectory(prefix='rehearsal-tests-')
os.environ['DB_PATH']=str(Path(_temp.name)/'tests.db')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c:
        yield c
