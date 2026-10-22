# 구조와 설계

## 실행 구조

Vue 3 → FastAPI → LangGraph → LangChain 에이전트 → OpenAI API.

FastAPI는 시작 시 MCP stdio 서버를 한 번 실행하고 연결을 유지합니다. 사람의 업무 조회와 평가 시 근거 수집은 이 MCP 연결을 사용합니다. 조회 도구는 세션에 고정된 주문·이력·정책 스냅샷만 읽습니다. 매 메시지마다 MCP 프로세스를 만들지 않습니다.

기본 실행은 `frontend/dist` 정적 파일과 `/api`를 FastAPI 한 프로세스에서 제공합니다. 개발 중에는 Vite 5173 → FastAPI 8000 프록시를 사용합니다.

## LangGraph 흐름

- `START → route`
- `operation=chat`: `customer_agent → END`
- `operation=evaluate`: `mcp_evidence → evaluation_agent → coaching_agent → validate_evidence → END`

고객·평가·코칭은 별도의 `create_agent` 인스턴스와 시스템 프롬프트를 사용합니다. 별도의 supervisor 모델 호출 없이 정해진 그래프 분기로 실행해 비용과 지연을 줄입니다. 모든 에이전트를 매 상담 턴 실행하지 않습니다.

고객 에이전트에는 고객 설정과 실제 대화만 전달합니다. 평가 정책·모범 답변·조회 로그는 전달하지 않습니다. 평가자는 원본 메시지, MCP 업무 근거, 상담사 조회 로그를 받습니다. 코치는 평가 결과와 같은 근거를 받습니다.

MCP 조회 자체는 LLM의 자유로운 도구 선택에 맡기지 않고 그래프와 업무 화면에서 명시적으로 실행합니다. 읽어야 할 데이터가 세 가지로 정해져 있으므로 재현성과 근거 완결성을 우선했습니다. MCP는 단순 함수 이름을 흉내 낸 것이 아니라 공식 Python SDK 기반 실제 JSON-RPC 서브프로세스 통신입니다. v1.26.0 API에 맞춰 고정했습니다.

## 파일 역할

| 경로 | 역할 |
|---|---|
| `run.py` | 프로젝트 최상위에서 서버 시작 |
| `backend/app/main.py` | API·SSE·동시 요청 제한·오류 복구·정적 화면 제공 |
| `backend/app/agents.py` | 세 에이전트, LangGraph, 프롬프트, 근거 검증 |
| `backend/app/mcp_server.py` | 읽기 전용 업무 도구 4개·Resource·Prompt |
| `backend/app/mcp_client.py` | 수명주기·직렬화된 MCP 호출·조회 기록 |
| `backend/app/rag.py` | OpenAI 임베딩·버전별 Chroma 검색·데모 벡터 |
| `backend/app/db.py` | SQLite 테이블·대화·조회·실행 기록 |
| `backend/app/seed.py` | 자체 작성 시나리오 3개·가상 주문·정책 |
| `backend/app/schemas.py` | 입력 및 평가·코칭 Pydantic 스키마 |
| `frontend/src/App.vue` | 대시보드·상담·리포트·기록·관리자 |
| `frontend/src/api.js` | REST 및 POST SSE 스트림 파서 |
| `frontend/src/style.css` | 밝은 UI·반응형 레이아웃 |

## 데이터

`sessions`: 모드·모델·재도전 부모·시나리오/정책 스냅샷·평가 버전·리포트.

`messages`: 고객과 상담사의 실제 발언. 완성된 한 턴의 상담사 입력과 고객 답변을 한 트랜잭션으로 저장합니다.

`lookups`: 어떤 세션에서 어떤 도구를 누가 조회했는지 기록. `trainee`와 `evaluator`를 분리합니다.

`runs`: 고객 응답/평가 실행, 성공·실패, 시간, 사용량, LangSmith와 연결할 루트 실행 ID.

사용량은 제공자 SDK의 실제 usage 메타데이터만 저장합니다. 임베딩은 별도 MCP 프로세스에서 호출하므로 검색 결과의 embedding_usage에 구분해 저장합니다. 추정 토큰이나 추정 비용을 실제 측정값처럼 표시하지 않습니다.

## 평가와 근거

각 항목은 25점입니다.

- 사실 확인: 주문·상담 이력·정책 조회는 각각 10·10·5점의 상한을 만듭니다. OpenAI 모드에서는 발언의 사실 정확성을 LLM이 판단하고 서버가 이 상한을 적용합니다. 자료를 열기만 했다고 무조건 25점을 주지 않습니다.
- 정책 준수: 정책 범위 안에서 안내했는지, 확인되지 않은 보장·권한 밖 약속이 있는지 평가.
- 해결안: 실행 가능한 선택지, 준비 사항, 후속 절차의 구체성.
- 의사소통: 불편 인정, 정확하고 간결한 설명, 확정 표현의 적절성.

서버가 실제 원문의 정확한 부분 문자열로 evidence_catalog를 만들고, 평가 모델은 E001 등의 근거 참조만 선택합니다. source_id와 원문 인용은 서버가 연결한 뒤 실제 근거와 다시 대조합니다. 코칭 원문도 M001 등의 상담사 참조로부터 서버가 직접 연결합니다. 존재하지 않는 참조나 출력 구조 오류에는 한 번만 자동 교정을 요청합니다. 정책 항목은 실제 정책 및 상담사 발언 둘 다 필요합니다. 코칭 원문은 상담사 메시지 전체와 정확히 일치해야 합니다. 점수 합계는 서버가 계산합니다.

이 검증은 근거의 존재와 인용 정확성을 보장합니다. LLM의 해석과 코칭 문장 전체의 의미적 정확성을 보장하지는 않습니다. 실제 기업의 품질 평가에는 전문가 교정 데이터와 캘리브레이션이 필요합니다. 데모 점수는 단순 규칙이며 품질 평가에 사용하지 않습니다.

재도전은 같은 스냅샷을 복사하고 메시지·조회 기록을 초기화합니다. 모드·모델명·평가/프롬프트 버전이 달라지면 직접 재도전을 거부합니다. 모델 별칭이 제공자 측에서 변경되는 경우까지 고정하지 않으므로 엄격한 실험에서는 모델 snapshot ID를 설정해야 합니다.

## 안정성

입력 길이/공백 검증, 최대 20턴, 세션별 동시 작업 차단, 조회 타임아웃, 고객 응답 110초/평가 240초 상한, SSE heartbeat, 클라이언트 중단 시 작업 취소, 실패한 부분 응답 미저장, 평가 실패 시 다시 시도 가능한 상태로 복구, 서버 재시작 시 평가 상태 복구를 구현했습니다.

관리자 API는 `X-Admin-Token`으로 확인하며 토큰은 브라우저 sessionStorage에만 보관합니다. 훈련 API에는 사용자별 인증을 구현하지 않았으므로 로컬 전용입니다. 로컬의 모든 훈련은 같은 훈련 기록 목록에서 보입니다.

메시지나 API 키 전체를 오류 로그로 출력하지 않습니다. 제공자 오류는 사용자에게 필요한 메시지로 변환합니다. 조회 도구는 주문/환불을 실제 변경하지 않습니다. 데모로 자동 대체하지 않아 실제 AI 실패를 숨기지 않습니다.

## API

| 메서드 | 경로 | 역할 |
|---|---|---|
| GET | `/api/health` | 모드·모델·MCP 연결·추적 설정 |
| GET | `/api/scenarios` | 시나리오 목록 |
| POST | `/api/sessions` | `{ "scenario_id": "delivery" }` 등으로 생성 |
| GET | `/api/sessions` | 최근 200개 훈련 |
| GET | `/api/sessions/{id}` | 메시지·조회·리포트 |
| POST | `/api/sessions/{id}/lookup/{kind}` | order / history / policy 조회 |
| POST | `/api/sessions/{id}/policy-search` | `{ "query": "검색어", "top_k": 4 }`, 정책 벡터 검색 |
| POST | `/api/sessions/{id}/messages` | `{ "content": "답변" }`, SSE |
| POST | `/api/sessions/{id}/finish` | 평가·코칭 후 결과 저장 |
| POST | `/api/sessions/{id}/retry` | 동일 조건 재도전 생성 |
| GET | `/api/sessions/{id}/comparison` | 직전 시도 대비 결과 |
| GET | `/api/admin/overview` | 관리자 토큰 필요, 실행·결과 현황 |

Swagger: `/docs` (같은 8000번 서버).

SSE 이벤트: `token`은 JSON 문자열, `done`은 저장된 두 메시지와 실행 ID, `error`는 안전한 오류 메시지입니다. 브라우저는 native EventSource 대신 fetch/ReadableStream으로 POST 응답을 읽고 UTF-8·프레임 분할을 처리합니다.

## 공식 문서

- https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow
- https://docs.langchain.com/oss/python/langgraph/streaming
- https://py.sdk.modelcontextprotocol.io/v1/
- https://docs.langchain.com/langsmith/trace-with-langgraph
- https://developers.openai.com/api/docs/models/gpt-5-mini
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://vuejs.org/guide/quick-start.html

## 정책 RAG와 MCP 확장

정책은 전체 corpus와 시나리오 정책 묶음을 구분합니다. 평가 그래프는 주문·이력 조회 뒤 최근 6개 메시지로 search_policy를 호출하고, 상위 4개 정책만 평가·코칭 근거에 주입합니다. 수동 get_policy 조회는 기존 시나리오 묶음을 유지합니다. 기존 세션에 corpus가 없으면 그 세션의 정책만 검색합니다.

Chroma 인스턴스는 MCP 프로세스에서 소유합니다. 임베딩 API 키는 검색을 위해 MCP 프로세스에도 전달합니다. 서버 부모의 mcp_business_tool trace가 반환 메타데이터를 기록하고, 자식 프로세스의 독립 LangSmith 추적은 끕니다. 실제 SDK 임베딩 사용량은 검색 반환값으로 보존합니다.

컬렉션 키는 문서 해시·제공자 모드·임베딩 모델에 따라 바뀌므로 서로 다른 버전의 원문과 벡터를 섞지 않습니다. 신규 문서만 인덱싱하며 기본 임베딩 함수를 비활성화해 자동 모델 다운로드를 피합니다. 검색 거리는 cosine 거리이며 신뢰 확률이 아닙니다.

Resource policy://{session_id}/{policy_id}는 스냅샷 원문을 읽습니다. Prompt policy_search_guide는 외부 클라이언트용 템플릿입니다. 둘 다 SDK 테스트로 동작을 확인했으며 운영 그래프는 Tools만 사용합니다.

독립 측정 스크립트는 backend/data/benchmark-chroma를 사용하므로 앱 MCP의 인덱스와 프로세스 소유권을 공유하지 않습니다.

상세한 기술 적용과 전체 Mermaid 흐름도는 [프로젝트 보고서](../PROJECT_REPORT.md)에 있습니다.
