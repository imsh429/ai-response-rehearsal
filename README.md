# 응대 리허설

신입 상담사가 까다로운 AI 고객과 상담을 연습하고, 실제 업무 자료와 대화에 근거한 평가를 받는 기업용 상담 훈련 MVP입니다.

**가장 빠른 실행:** 이 ZIP에는 Vue 화면의 빌드 결과까지 포함되어 있습니다. Python 의존성 설치 → `backend/.env`에 OpenAI API 키 입력 → `python run.py`만 하면 됩니다. 기본 실행에는 Node.js가 필요 없습니다.

**전체 ZIP 실행:** [START_HERE.md](START_HERE.md)의 순서대로 새 폴더에서 실행하세요. 제출용 보고서는 [PROJECT_REPORT.md](PROJECT_REPORT.md), 비교 결과는 [BENCHMARK_RESULT.md](docs/BENCHMARK_RESULT.md)에 있습니다. [UPDATE.md](UPDATE.md)는 이전 부분 업데이트용 안내입니다.

## 1. 준비

- Python **3.11 이상**. 검증 환경은 Python 3.12.14입니다.
- VS Code에서 압축 해제한 **`response-rehearsal` 폴더**를 엽니다. 탐색기 최상단에 `run.py`, `requirements.txt`, `backend`, `frontend`가 보여야 합니다.
- OpenAI API 키와 사용 가능한 API 크레딧이 필요합니다. 키는 [OpenAI API 설정](https://platform.openai.com/api-keys)에서 발급합니다. ChatGPT 구독과 API 이용 요금은 별개입니다.

## 2. macOS에서 실행

VS Code의 `터미널 → 새 터미널`을 엽니다. 현재 위치는 `response-rehearsal` 폴더여야 합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp backend/.env.example backend/.env
```

이어서 VS Code로 **`backend/.env`** 파일을 열고 다음 두 줄을 설정합니다.

```dotenv
APP_MODE=openai
OPENAI_API_KEY=본인의_OpenAI_API_키
```

`본인의_OpenAI_API_키`를 실제 키로 바꾸세요. 파일을 저장한 다음 실행합니다.

```bash
python scripts/check_setup.py
python run.py
```

브라우저에서 **http://127.0.0.1:8000** 을 엽니다. 터미널은 실행한 상태로 둡니다.

`python3`가 없거나 버전이 낮으면 Python 3.11 이상을 설치한 뒤 VS Code를 다시 열어 주세요. 여러 Python이 설치되어 있으면 첫 명령을 `python3.12 -m venv .venv`처럼 원하는 버전으로 실행하면 됩니다.

## 3. Windows PowerShell에서 실행

VS Code 터미널의 현재 위치가 `response-rehearsal` 폴더인지 확인합니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item backend\.env.example backend\.env
```

**`backend/.env`** 를 열고 `APP_MODE=openai`와 `OPENAI_API_KEY=실제키`를 입력한 뒤 저장합니다.

```powershell
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe run.py
```

브라우저에서 **http://127.0.0.1:8000** 을 엽니다.

가상환경 활성화 없이 가상환경의 Python을 직접 실행하므로 PowerShell 실행 정책을 바꿀 필요가 없습니다. `py`가 없으면 첫 명령의 `py -3`를 `python`으로 바꿔 보세요. `python --version`이 3.11 이상인지 확인하세요.

## 4. 다음부터 다시 실행

최초 설치와 `.env` 복사는 한 번만 합니다. **기존 `.env`를 다시 덮어쓰지 마세요.**

macOS:

```bash
source .venv/bin/activate
python run.py
```

Windows:

```powershell
.\.venv\Scripts\python.exe run.py
```

종료는 실행 중인 터미널에서 **Ctrl+C**입니다. 설정 파일이나 Python 코드를 바꿨으면 서버를 종료한 후 다시 켭니다. 기본 실행은 자동 새로고침이 아닙니다.

## 5. 화면에서 사용하는 순서

1. 시나리오를 선택합니다. 고객의 첫 메시지는 동일한 조건을 위해 고정되어 있습니다.
2. 오른쪽 **업무 자료**에서 주문·상담 이력·회사 정책 탭을 선택하고 각각 **자료 조회하기**를 누릅니다. 회사 정책에서는 검색어를 입력하고 **관련 정책 검색**으로 전체 20개 정책 중 관련 4개를 찾을 수도 있습니다. 탭을 여는 것만으로 조회되지는 않습니다.
3. 상담사 입장에서 직접 답변하고 전송합니다. AI 고객은 앞선 대화를 기억하며 반응합니다. 최대 20턴, 메시지당 2000자입니다.
4. **상담 종료하고 평가받기**를 누릅니다. 최소 한 번 답변해야 평가할 수 있습니다.
5. 네 항목 점수, 실제 발언·정책 인용, 개선 답변을 확인합니다. 평가와 코칭에는 모델에 따라 수 분이 걸릴 수 있습니다.
6. **같은 상황에 재도전**하고 다시 평가하면 직전 시도와 항목별 결과를 비교합니다. 업무 자료, 첫 메시지, 평가 기준을 유지하며 상담 내용과 조회 기록은 새로 시작합니다.
7. **훈련 기록**에서 진행 중인 상담을 이어가거나 완료된 리포트를 다시 볼 수 있습니다.

이 서비스는 실제 주문 변경·환불·보상 지급을 실행하지 않습니다. 가상 업무 데이터를 사용한 훈련입니다. 모든 시나리오의 훈련 기준일은 **2026-10-21**로 고정되어 있으며 컴퓨터의 오늘 날짜와 무관합니다.

## 6. OpenAI 설정

`backend/.env`:

```dotenv
APP_MODE=openai
OPENAI_API_KEY=실제키
OPENAI_MODEL=gpt-5-mini
OPENAI_REASONING_EFFORT=low
ADMIN_TOKEN=local-admin-2026
```

기본 모델은 GPT-5 mini입니다. 계정에서 사용할 수 있는 모델명으로 `OPENAI_MODEL`을 변경할 수 있습니다. 고객 응답에는 스트리밍, 평가·코칭에는 도구 호출 기반 구조화 응답을 사용하므로 해당 기능을 지원하는 모델이 필요합니다.

`OPENAI_REASONING_EFFORT`는 GPT-5 또는 o 계열에만 적용합니다. 다른 설정의 모델에서 미지원 오류가 발생하면 값을 비우고 재시작하세요. 모델을 바꾸면 비용과 응답 속도도 달라집니다. 평가·코칭은 각각 별도 모델 호출이며 형식 오류가 나면 결과를 저장하지 않고 다시 평가할 수 있게 합니다.

키는 백엔드에만 두며 프런트 코드나 브라우저 입력란에 넣지 않습니다. `.env`는 Git 제외 대상입니다. 실제 API 인증·과금은 본인의 키로 첫 메시지를 보낼 때 확인됩니다.

## 7. 관리자와 LangSmith

화면 왼쪽 **관리자**에서 `backend/.env`의 `ADMIN_TOKEN`을 입력합니다. 기본값은 **`local-admin-2026`** 입니다. 운영에 사용할 때는 변경하세요.

관리자 화면에서는 훈련 결과, 최근 100개 실행, 응답 소요 시간, 실제 제공자 토큰 사용량, 실패 사유를 확인합니다. 데모에서는 모델을 호출하지 않으므로 토큰은 `—`입니다. 기록과 통계는 최근 200개 상담을 기준으로 합니다.

LangSmith를 연결하려면 `.env`에 다음을 입력한 후 서버를 재시작합니다.

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=본인의_LangSmith_API_키
LANGSMITH_PROJECT=response-rehearsal
```

US 외 리전 계정이라면 LangSmith 설정에 나오는 API URL을 `LANGSMITH_ENDPOINT`로 추가합니다. 키가 여러 워크스페이스에 연결되어 있다면 `LANGSMITH_WORKSPACE_ID`도 추가할 수 있습니다.

[LangSmith](https://smith.langchain.com)에서 해당 프로젝트를 열고 관리자에 표시된 **실행 ID** 또는 `session_id` 메타데이터로 검색합니다. 고객·평가·코칭 노드와 MCP 근거 수집 과정을 볼 수 있습니다. 추적 데이터에는 훈련 대화와 가상 업무 자료가 포함됩니다. 관리자 화면 자체를 LangSmith가 대신 제공하는 구조는 아닙니다.

LangSmith 키가 없어도 `LANGSMITH_TRACING=false`로 전체 상담 기능을 사용할 수 있습니다.

## 8. API 키 없이 점검하는 데모 모드

`.env`의 `APP_MODE=demo`로 바꾸고 재시작합니다. 이 모드에서도 실제 MCP 서버·SQLite·LangGraph와 화면은 동작합니다. 단, AI 고객은 정해진 규칙으로 답하고 평가도 키워드 기반입니다. 결과를 실제 상담 역량 점수로 해석하지 마세요.

OpenAI 모드에서 오류가 난다고 데모로 자동 전환하지 않습니다. API 오류를 명확하게 표시하고 재시도하도록 합니다. 데모와 OpenAI 결과는 직접 재도전 비교할 수 없습니다.

## 9. Vue 코드를 수정할 때만 필요한 개발 모드

Node.js **22.12 이상 또는 24 이상**을 권장합니다. ZIP에 포함된 화면만 사용할 때는 이 과정이 필요 없습니다.

첫 번째 터미널은 위 안내대로 `python run.py`를 실행합니다.

두 번째 터미널:

```bash
cd frontend
npm ci
npm run dev
```

수정 중에는 **http://127.0.0.1:5173** 을 엽니다. `/api` 요청은 Vite가 8000번 백엔드로 전달합니다. API 키를 Vite 환경 변수에 넣지 마세요.

수정한 화면을 8000번 주소에도 반영하려면:

```bash
# frontend 폴더에서
npm run build
```

백엔드를 종료하고 다시 켠 뒤 8000번 페이지를 새로고침합니다. Python 코드까지 자동 재시작하고 싶다면 프로젝트 최상위에서 `python -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --host 127.0.0.1 --port 8000`으로 실행할 수 있습니다.

## 10. 테스트

프로젝트 최상위에서 macOS:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
```

Windows에서는 위 명령의 `python` 대신 `.\.venv\Scripts\python.exe`를 사용합니다.

테스트는 임시 데이터베이스와 데모 설정을 사용하며 OpenAI API에 과금하지 않습니다. 실제 MCP 서브프로세스를 실행합니다. OpenAI 연동 테스트도 실제 LangChain/OpenAI SDK에 모의 HTTP 응답을 연결해 실행합니다.

선택 브라우저 테스트:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/browser_e2e.py
```

검증 내용과 실제 키로 확인하지 못한 항목은 [docs/VALIDATION.md](docs/VALIDATION.md)에 정리했습니다.

## 11. 자주 발생하는 문제

| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError` | 가상환경의 Python으로 `pip install -r requirements.txt`를 실행했는지 확인 |
| `.env`를 수정했는데 적용되지 않음 | `backend/.env`인지 확인 후 서버 재시작. 셸 환경 변수가 같은 이름으로 있으면 그 값이 우선 |
| API 키 오류 | 앞뒤 공백 제거, 실제 API 키 확인, 서버 재시작 |
| 429 / 사용 한도 오류 | OpenAI API 프로젝트 크레딧·결제·요청 한도 확인 |
| 모델 접근 오류 | 계정에서 접근 가능한 모델로 `OPENAI_MODEL` 변경 후 재시작 |
| `Address already in use` | 기존 8000번 서버 종료. 다른 포트는 `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001`로 실행. 이 경우 8001번 주소로 접속 |
| 메인 화면이 404 | `frontend/dist` 포함 여부 확인. 없다면 `frontend`에서 `npm ci`, `npm run build` 후 서버 재시작 |
| MCP 오류 | 이 ZIP의 고정 버전 `mcp==1.26.0` 설치 여부 확인. `mcp`만 v2로 임의 업그레이드하지 않기 |
| 연결을 중단함 | 일부 AI 응답은 저장하지 않음. 새로고침으로 실제 저장된 대화를 확인 후 재전송 |
| 평가 오류 | 대화는 유지됨. 정책·발언 근거 검증에 실패한 경우에도 다시 평가 가능 |
| 서버 재시작 후 평가 중 표시 | 평가 진행 상태는 재시작 시 복구되며 다시 평가 가능 |

데이터는 `backend/data/rehearsal.db`에 저장됩니다. 완전 초기화가 필요하면 서버를 종료하고 `backend/data` 폴더를 다른 곳으로 옮긴 후 재시작하세요. 기존 훈련 기록이 없는 새 데이터베이스를 만듭니다.

## 12. 구현 범위

구현: Vue UI, FastAPI REST API, SSE, LangChain 기반 고객·평가·코칭 에이전트, LangGraph 분기 실행, MCP 읽기 전용 도구 4개·정책 Resource·안내 Prompt, OpenAI 임베딩·Chroma 정책 RAG, 고정 예제 Before/After 측정, SQLite 이력 저장, 근거·원문 검증, 재도전 비교, 관리자 실행 현황, 선택 LangSmith 추적.

현재 버전은 **단일 PC·단일 프로세스 로컬 MVP**입니다. 실제 기업 배포에는 사용자 로그인과 상담별 접근 권한, 기업별 데이터 분리, 관리자 인증 강화, HTTPS, 다중 프로세스 동시성 제어, 백업·보존 정책이 추가로 필요합니다. `--workers`를 늘리거나 기본 상태로 외부에 공개하지 마세요.

코드 구성과 설계 판단은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

## 13. 정책 RAG와 실험

새 훈련은 자체 작성 정책 20개를 스냅샷에 고정합니다. 평가자는 최근 대화로 관련 정책 4개를 검색하여 평가·코칭에 사용합니다. 상담사의 정책 검색도 조회로 기록됩니다. 실제 의미 검색에는 기존 OpenAI 키를 사용하며 `OPENAI_EMBEDDING_MODEL` 기본값은 `text-embedding-3-small`입니다. 인덱스는 `backend/data/chroma`, 독립 벤치마크 인덱스는 `backend/data/benchmark-chroma`에 저장합니다.

데모의 해시 벡터는 연결 점검용이며 의미 검색 성능으로 해석하지 않습니다. 검색 거리 역시 정답 확률이 아닙니다. 정책 검색과 모델 평가 품질은 실제 키로 측정해야 합니다. 명령과 비용이 발생하는 실행 범위는 [UPDATE.md](UPDATE.md)에 정리했습니다.
