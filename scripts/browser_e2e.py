"""Optional browser test. pip install playwright; playwright install chromium."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='rehearsal-browser-') as tmp:
    env=dict(os.environ,APP_MODE='demo',DB_PATH=str(Path(tmp)/'ui.db'),LANGSMITH_TRACING='false',ADMIN_TOKEN='e2e-admin')
    log=open(Path(tmp)/'server.log','w+')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port','8765'],env=env,stdout=log,stderr=log)
    try:
        with httpx.Client(trust_env=False) as client:
            for _ in range(100):
                try:
                    if client.get('http://127.0.0.1:8765/api/health').status_code==200:break
                except httpx.HTTPError:pass
                if server.poll() is not None:
                    log.seek(0);raise RuntimeError(log.read())
                time.sleep(.15)
            else:raise RuntimeError('서버 시작 시간 초과')
        with sync_playwright() as p:
            launch={'headless':True}
            if os.getenv('BROWSER_CONFIG'):
                cfg=json.loads(Path(os.environ['BROWSER_CONFIG']).read_text())
                launch.update(executable_path=cfg['path'],args=cfg['args'])
            browser=p.chromium.launch(**launch)
            page=browser.new_page(viewport={'width':1440,'height':1100})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8765')
            page.get_by_role('heading',name='좋은 응대는, 연습에서 시작돼요.').wait_for()
            assert page.locator('.scenario-card').count()==3
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(Path(tmp)/'home.png'),full_page=True)
            if os.getenv('SCREENSHOT_DIR'):
                dest=Path(os.environ['SCREENSHOT_DIR']);dest.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(dest/'home.png'),full_page=True)
            page.get_by_role('button',name='배송 지연 상담 연습하기').click()
            page.get_by_role('heading',name='오늘 온다더니, 아직 출고 전?').wait_for()
            for name in ['주문','상담 이력','회사 정책']:
                page.get_by_role('button',name=name,exact=True).click()
                page.get_by_role('button',name='자료 조회하기').click()
                page.locator('.verified').wait_for()
            page.get_by_label('상황에 맞는 정책 검색').fill('출고 전 취소와 카드 환불')
            page.get_by_role('button',name='관련 정책 검색',exact=True).click()
            page.get_by_text('데모 검색 · 품질 측정용 아님',exact=False).wait_for()
            assert page.locator('.policy-note').count()==4
            page.get_by_role('textbox',name='상담사 답변').fill('불편을 드려 죄송합니다. 주문과 이전 상담 내용을 확인했습니다. 출고 전이므로 취소 접수가 가능합니다. 취소 승인 후 영업일 3~5일이 소요됩니다. 추가 보상은 관리자 검토로 이관하겠습니다.')
            page.get_by_role('button',name='전송',exact=True).click()
            page.locator('.message.mine').wait_for()
            assert page.locator('.message.customer').count()==2
            if os.getenv('SCREENSHOT_DIR'):page.screenshot(path=str(dest/'training.png'),full_page=True)
            page.get_by_role('button',name='상담 종료하고 평가받기').click()
            page.get_by_role('heading',name='이번 연습이, 다음 응대를 바꿔요.').wait_for(timeout=30000)
            assert page.locator('.criterion-card').count()==4
            assert page.locator('.rewrite-card').count()>=1
            page.locator('.evidence-details').first.locator('summary').first.click()
            assert page.locator('.evidence-details').first.locator('blockquote').is_visible()
            if os.getenv('SCREENSHOT_DIR'):page.screenshot(path=str(dest/'report.png'),full_page=True)
            page.get_by_role('button',name='같은 상황에 재도전',exact=True).click()
            page.get_by_role('textbox',name='상담사 답변').fill('죄송합니다. 검토 접수 절차를 안내하겠습니다.')
            page.get_by_role('button',name='전송',exact=True).click()
            page.locator('.message.mine').wait_for()
            page.get_by_role('button',name='상담 종료하고 평가받기').click()
            page.locator('.comparison-card').wait_for()
            assert page.locator('.comparison-criteria>div').count()==4
            page.get_by_role('button',name='훈련 기록',exact=True).first.click()
            page.locator('.record-row').first.wait_for()
            assert page.locator('.record-row').count()==2
            page.get_by_role('button',name='관리자',exact=True).click()
            page.get_by_label('관리자 코드',exact=True).fill('e2e-admin')
            page.get_by_role('button',name='현황 확인',exact=True).click()
            page.locator('table tbody tr').first.wait_for()
            assert page.locator('table tbody tr').count()==4
            page.get_by_role('button',name='훈련 대시보드',exact=True).click()
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), '모바일 가로 넘침'
            if os.getenv('SCREENSHOT_DIR'):page.screenshot(path=str(dest/'mobile.png'),full_page=True)
            assert errors==[],errors
            browser.close()
        print('Browser E2E passed: home → MCP lookups → chat → evaluation → retry comparison → history → admin; mobile overflow: none; JS errors: none')
    finally:
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        log.close()
