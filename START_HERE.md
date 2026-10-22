# 전체 완성본 실행 방법 — macOS / VS Code

이 파일은 전체 프로젝트 ZIP의 실행 안내입니다. 이전의 부분 업데이트를 먼저 적용할 필요가 없습니다. 소스, 빌드된 Vue 화면, 테스트, 비교 측정 도구, 프로젝트 보고서를 포함했습니다. API 키·개인 훈련 DB·가상환경·node_modules는 포함하지 않았습니다.

## 1. 기존 서버 종료

기존 서버가 실행 중인 터미널에서 **Ctrl+C**를 누릅니다. 기존 프로젝트 폴더는 남겨 둡니다.

## 2. 압축 해제

ZIP을 Downloads에 다운로드했다면 VS Code 터미널에서 다음을 실행합니다.

```bash
mkdir -p ~/workspace
cd ~/workspace
unzip ~/Downloads/response-rehearsal-complete.zip
cd response-rehearsal-complete
```

이미 Finder로 압축을 풀었다면 그 폴더를 VS Code의 **파일 → 폴더 열기**로 엽니다. 루트에 `run.py`, `requirements.txt`, `backend`, `frontend`가 보여야 합니다. Finder로 먼저 압축을 풀었을 때는 위 압축 해제 명령 대신 실제 폴더로 이동하세요.

## 3. 가상환경과 설치

Python 3.11 이상이 필요합니다. 기존 `.venv`를 옮기지 않고 새 프로젝트 위치에 만듭니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 4. 기존 API 키 설정 복사

기존 프로젝트가 `~/workspace/response-rehearsal`에 있다면, 새 프로젝트 루트에서 다음을 실행합니다.

```bash
cp ../response-rehearsal/backend/.env backend/.env
```

이 명령은 기존 프로젝트의 `.env`를 읽어 새 프로젝트에 복사합니다. `backend/.env`를 열어 다음 설정을 확인하고 저장합니다.

```dotenv
APP_MODE=openai
OPENAI_API_KEY=기존에_사용하던_실제키
```

이미 실제 키가 입력되어 있다면 바꾸지 않습니다. 파일에 DB_PATH 또는 RAG_DB_PATH를 직접 지정해 둔 경우 새 프로젝트에서 사용할 경로인지 확인하세요. 기본 제공 설정에는 두 경로를 지정하지 않습니다.

기존 `.env`를 찾을 수 없는 경우에만 다음 명령으로 설정 파일을 만들고 실제 키를 입력합니다.

```bash
cp backend/.env.example backend/.env
```

`OPENAI_EMBEDDING_MODEL`을 추가하지 않아도 `text-embedding-3-small`이 기본입니다. 기존 OpenAI 키로 상담과 정책 임베딩을 함께 사용하며 실제 호출에 API 요금이 발생합니다.

## 5. 서버 실행

```bash
python scripts/check_setup.py
python run.py
```

브라우저에서 **http://127.0.0.1:8000** 을 엽니다. Vue 화면이 빌드되어 있으므로 기본 실행에 npm 명령이나 별도 프런트 서버는 필요하지 않습니다. 서버 터미널은 켜 둡니다.

## 6. 기능 확인

1. 새 배송 지연 훈련을 시작합니다.
2. 오른쪽 업무 자료에서 주문과 상담 이력을 조회합니다.
3. 회사 정책 탭에서 `출고 전 취소와 배송 지연 보상`을 검색합니다.
4. 의미 검색 결과가 표시되면 상담사 답변을 전송합니다.
5. 상담 종료 후 평가, 근거, 개선 답변을 확인합니다.
6. 같은 상황에 재도전하면 직전 결과와 비교합니다.

최초 검색에는 정책 임베딩과 Chroma 인덱스 생성 시간이 필요합니다. 새 설치에서는 훈련 기록을 새로 만듭니다. 기존 기록은 기존 프로젝트의 `backend/data`에 그대로 있습니다.

기존 기록까지 옮기려면 양쪽 서버를 종료한 상태에서 새 서버의 첫 실행 전에 기존 `backend/data` 폴더 전체를 새 프로젝트의 `backend/data`로 복사할 수 있습니다. 기존 세션은 자신의 정책 스냅샷을 유지하므로 새 20개 정책 RAG 확인은 새 훈련에서 합니다. 이전 프롬프트 버전의 세션은 직접 재도전이 제한될 수 있습니다.

## 다음부터 다시 실행

```bash
cd ~/workspace/response-rehearsal-complete
source .venv/bin/activate
python run.py
```

종료는 Ctrl+C입니다. 코드나 `.env` 변경 후에는 서버를 재시작합니다.

## 보고서·발표·실제 API 측정

- `PROJECT_REPORT.md`: 과제 필수 5개 항목을 갖춘 보고서. 소속·반·고유번호·이름·제출일·공개 URL을 채웁니다.
- `docs/PRESENTATION_NOTES.md`: 발표 10장 구성과 시연 메모.
- `docs/VALIDATION.md`: 자동 테스트·브라우저 검증 범위와 확인하지 못한 항목.
- `docs/BENCHMARK_RESULT.md`: 현재는 데모 연결 점검 결과. 실제 API 품질 측정과 구분합니다.

실제 측정은 프로젝트 루트에서 실행합니다. `--judge`는 12개 사례 × 2개 조건 × 반복 횟수만큼 정책 판정을 수행하고 유료 API를 호출합니다. 아래 예시는 1회 반복, 기본 24회 판정입니다. 모델의 구조화 응답 처리와 네트워크 재시도로 제공자 요청 수는 달라질 수 있습니다.

```bash
python scripts/benchmark_rag.py --repeat 1 --judge
python scripts/render_benchmark_report.py docs/results/rag-benchmark.json
```

3회 반복하려면 `--repeat 3`으로 바꿉니다. 실행 결과에 맞춰 보고서 4.5절의 데모 상태 설명을 갱신합니다. 실측 전에는 성능 향상이나 비용 절감을 단정하지 않습니다. 실제 측정 JSON과 결과 표를 보고서와 함께 제출하세요.

제출용 외부 링크는 공개 GitHub 저장소 등에 보고서를 올려 만들어야 합니다. 로컬 실행 주소와 ZIP 다운로드 링크는 제출용 공개 문서 URL을 대신하지 않습니다. 공개 링크를 만든 후 인증 없는 접근과 시크릿 브라우저에서 본문 접근을 확인합니다.

전체 설치·개발 모드·Windows 실행 안내는 `README.md`를 참고하세요. `UPDATE.md`는 이전 부분 업데이트용 안내이므로 이 전체 ZIP을 새 폴더에서 실행할 때는 이 문서의 순서를 따릅니다.
